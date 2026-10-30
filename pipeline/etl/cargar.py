"""Carga en SQLite: capas bronze/silver, cuarentena y modelo en estrella (gold)."""
import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from .calidad import Rechazo

# Los importes viajan como Decimal; SQLite los guarda en columnas NUMERIC.
sqlite3.register_adapter(Decimal, str)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS control_ficheros (
    archivo     TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,
    filas       INTEGER NOT NULL,
    validas     INTEGER NOT NULL,
    rechazadas  INTEGER NOT NULL,
    duplicados  INTEGER NOT NULL,
    cargado_en  TEXT NOT NULL
);

-- Bronze: copia literal de lo recibido, para poder reprocesar y auditar.
CREATE TABLE IF NOT EXISTS bronze_pedidos (
    archivo     TEXT NOT NULL,
    num_fila    INTEGER NOT NULL,
    contenido   TEXT NOT NULL,
    ingerido_en TEXT NOT NULL,
    PRIMARY KEY (archivo, num_fila)
);

-- Silver: pedidos limpios y tipados. Un id_venta que llega de nuevo actualiza el anterior.
CREATE TABLE IF NOT EXISTS silver_pedidos (
    id_venta        TEXT PRIMARY KEY,
    fecha           TEXT NOT NULL,
    id_cliente      TEXT NOT NULL,
    codigo_producto TEXT NOT NULL,
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC NOT NULL CHECK (precio_unitario >= 0),
    canal           TEXT NOT NULL,
    archivo         TEXT NOT NULL,
    actualizado_en  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cuarentena (
    archivo   TEXT NOT NULL,
    num_fila  INTEGER NOT NULL,
    contenido TEXT NOT NULL,
    motivos   TEXT NOT NULL,
    PRIMARY KEY (archivo, num_fila)
);

-- Gold: modelo en estrella listo para analítica.
CREATE TABLE IF NOT EXISTS dim_cliente (
    id_cliente TEXT PRIMARY KEY,
    nombre     TEXT NOT NULL,
    email      TEXT NOT NULL,
    ciudad     TEXT NOT NULL,
    fecha_alta TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_producto (
    codigo_producto TEXT PRIMARY KEY,
    nombre          TEXT NOT NULL,
    categoria       TEXT NOT NULL,
    precio_catalogo NUMERIC
);

CREATE TABLE IF NOT EXISTS dim_fecha (
    fecha            TEXT PRIMARY KEY,
    anio             INTEGER NOT NULL,
    trimestre        INTEGER NOT NULL,
    mes              INTEGER NOT NULL,
    nombre_mes       TEXT NOT NULL,
    dia              INTEGER NOT NULL,
    dia_semana       INTEGER NOT NULL,  -- 1 = lunes ... 7 = domingo (ISO 8601)
    es_fin_de_semana INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_ventas (
    id_venta        TEXT PRIMARY KEY,
    fecha           TEXT NOT NULL REFERENCES dim_fecha (fecha),
    id_cliente      TEXT NOT NULL REFERENCES dim_cliente (id_cliente),
    codigo_producto TEXT NOT NULL REFERENCES dim_producto (codigo_producto),
    canal           TEXT NOT NULL,
    cantidad        INTEGER NOT NULL,
    precio_unitario NUMERIC NOT NULL,
    importe         NUMERIC NOT NULL
);
"""

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar(ruta) -> sqlite3.Connection:
    conexion = sqlite3.connect(ruta)
    conexion.execute("PRAGMA foreign_keys = ON")
    conexion.executescript(ESQUEMA)
    return conexion


def checksum_cargado(conexion: sqlite3.Connection, archivo: str) -> str | None:
    fila = conexion.execute("SELECT checksum FROM control_ficheros WHERE archivo = ?", (archivo,)).fetchone()
    return fila[0] if fila else None


def cargar_dimensiones(conexion: sqlite3.Connection, clientes: list[dict], productos: list[dict]) -> None:
    """Upsert de los maestros: los cambios del origen se reflejan (SCD tipo 1)."""
    conexion.executemany(
        """INSERT INTO dim_cliente (id_cliente, nombre, email, ciudad, fecha_alta)
           VALUES (:id_cliente, :nombre, :email, :ciudad, :fecha_alta)
           ON CONFLICT (id_cliente) DO UPDATE SET
               nombre = excluded.nombre, email = excluded.email,
               ciudad = excluded.ciudad, fecha_alta = excluded.fecha_alta""",
        clientes,
    )
    conexion.executemany(
        """INSERT INTO dim_producto (codigo_producto, nombre, categoria, precio_catalogo)
           VALUES (:codigo_producto, :nombre, :categoria, :precio_catalogo)
           ON CONFLICT (codigo_producto) DO UPDATE SET
               nombre = excluded.nombre, categoria = excluded.categoria,
               precio_catalogo = excluded.precio_catalogo""",
        productos,
    )


def cargar_fichero(
    conexion: sqlite3.Connection,
    archivo: str,
    huella: str,
    filas: list[dict[str, str]],
    validas: list[dict],
    rechazadas: list[Rechazo],
    duplicados: int,
) -> None:
    """Carga un fichero de pedidos en bronze, silver y cuarentena. Reprocesarlo sustituye lo anterior."""
    momento = ahora()
    conexion.execute("DELETE FROM bronze_pedidos WHERE archivo = ?", (archivo,))
    conexion.execute("DELETE FROM cuarentena WHERE archivo = ?", (archivo,))
    conexion.executemany(
        "INSERT INTO bronze_pedidos (archivo, num_fila, contenido, ingerido_en) VALUES (?, ?, ?, ?)",
        [(archivo, n, json.dumps(fila, ensure_ascii=False), momento) for n, fila in enumerate(filas, start=2)],
    )
    conexion.executemany(
        """INSERT INTO silver_pedidos
               (id_venta, fecha, id_cliente, codigo_producto, cantidad, precio_unitario, canal, archivo, actualizado_en)
           VALUES (:id_venta, :fecha, :id_cliente, :codigo_producto, :cantidad, :precio_unitario, :canal, :archivo, :momento)
           ON CONFLICT (id_venta) DO UPDATE SET
               fecha = excluded.fecha, id_cliente = excluded.id_cliente,
               codigo_producto = excluded.codigo_producto, cantidad = excluded.cantidad,
               precio_unitario = excluded.precio_unitario, canal = excluded.canal,
               archivo = excluded.archivo, actualizado_en = excluded.actualizado_en""",
        [{**v, "archivo": archivo, "momento": momento} for v in validas],
    )
    conexion.executemany(
        "INSERT INTO cuarentena (archivo, num_fila, contenido, motivos) VALUES (?, ?, ?, ?)",
        [(archivo, r.num_fila, json.dumps(r.fila, ensure_ascii=False), "; ".join(r.motivos)) for r in rechazadas],
    )
    conexion.execute(
        """INSERT INTO control_ficheros (archivo, checksum, filas, validas, rechazadas, duplicados, cargado_en)
           VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (archivo) DO UPDATE SET
               checksum = excluded.checksum, filas = excluded.filas, validas = excluded.validas,
               rechazadas = excluded.rechazadas, duplicados = excluded.duplicados, cargado_en = excluded.cargado_en""",
        (archivo, huella, len(filas), len(validas), len(rechazadas), duplicados, momento),
    )


def construir_gold(conexion: sqlite3.Connection) -> None:
    """Regenera dim_fecha y fact_ventas a partir de silver: siempre el mismo resultado (idempotente)."""
    rango = conexion.execute("SELECT MIN(fecha), MAX(fecha) FROM silver_pedidos").fetchone()
    conexion.execute("DELETE FROM fact_ventas")
    if rango[0] is None:
        return
    inicio, fin = date.fromisoformat(rango[0]), date.fromisoformat(rango[1])
    dias = [inicio + timedelta(days=n) for n in range((fin - inicio).days + 1)]
    conexion.executemany(
        """INSERT OR IGNORE INTO dim_fecha
               (fecha, anio, trimestre, mes, nombre_mes, dia, dia_semana, es_fin_de_semana)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month, MESES[d.month - 1], d.day, d.isoweekday(), int(d.isoweekday() >= 6))
            for d in dias
        ],
    )
    conexion.execute(
        """INSERT INTO fact_ventas (id_venta, fecha, id_cliente, codigo_producto, canal, cantidad, precio_unitario, importe)
           SELECT id_venta, fecha, id_cliente, codigo_producto, canal, cantidad, precio_unitario,
                  ROUND(cantidad * precio_unitario, 2)
           FROM silver_pedidos"""
    )
