"""Orquestación del pipeline.

Uso (desde la carpeta pipeline/):
    python -m etl.pipeline                     # datos/raw -> salida/ventas.db
    python -m etl.pipeline --raw otra/carpeta --db /tmp/ventas.db
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from . import calidad, cargar, extraer
from .config import DB_PATH, FICHERO_CLIENTES, FICHERO_PRODUCTOS, PATRON_PEDIDOS, RAW_DIR

log = logging.getLogger("etl")


def ejecutar(raw_dir: Path = RAW_DIR, db_path: Path = DB_PATH) -> dict:
    """Ejecuta el pipeline completo y devuelve un resumen de la ejecución."""
    raw_dir, db_path = Path(raw_dir), Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    resumen = {"procesados": [], "omitidos": [], "filas": 0, "validas": 0, "rechazadas": 0, "duplicados": 0}

    conexion = cargar.conectar(db_path)
    try:
        clientes = [calidad.normalizar_cliente(f) for f in extraer.leer_csv(raw_dir / FICHERO_CLIENTES)]
        productos = [calidad.normalizar_producto(f) for f in extraer.leer_csv(raw_dir / FICHERO_PRODUCTOS)]
        with conexion:
            cargar.cargar_dimensiones(conexion, clientes, productos)
        ids_clientes = {c["id_cliente"] for c in clientes}
        ids_productos = {p["codigo_producto"] for p in productos}

        for ruta in sorted(raw_dir.glob(PATRON_PEDIDOS)):
            huella = extraer.checksum(ruta)
            anterior = cargar.checksum_cargado(conexion, ruta.name)
            if anterior == huella:
                log.info("%s ya estaba cargado: se omite", ruta.name)
                resumen["omitidos"].append(ruta.name)
                continue
            if anterior is not None:
                log.warning("%s ha cambiado desde la última carga: se reprocesa", ruta.name)

            filas = extraer.leer_csv(ruta)
            res = calidad.validar_pedidos(filas, ids_clientes, ids_productos)
            # Cada fichero en su propia transacción: o se carga entero o no se carga.
            with conexion:
                cargar.cargar_fichero(conexion, ruta.name, huella, filas, res.validas, res.rechazadas, res.duplicados)
            for r in res.rechazadas:
                log.warning("%s fila %d a cuarentena: %s", ruta.name, r.num_fila, ", ".join(r.motivos))
            log.info(
                "%s: %d filas, %d válidas, %d en cuarentena, %d duplicadas",
                ruta.name, len(filas), len(res.validas), len(res.rechazadas), res.duplicados,
            )
            resumen["procesados"].append(ruta.name)
            resumen["filas"] += len(filas)
            resumen["validas"] += len(res.validas)
            resumen["rechazadas"] += len(res.rechazadas)
            resumen["duplicados"] += res.duplicados

        with conexion:
            cargar.construir_gold(conexion)
        ventas, importe = conexion.execute("SELECT COUNT(*), ROUND(COALESCE(SUM(importe), 0), 2) FROM fact_ventas").fetchone()
        resumen["ventas_gold"] = ventas
        resumen["importe_total"] = importe
        resumen["en_cuarentena"] = conexion.execute("SELECT COUNT(*) FROM cuarentena").fetchone()[0]
    finally:
        conexion.close()
    return resumen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline ETL de ventas (CSV -> SQLite, arquitectura medallion)")
    parser.add_argument("--raw", type=Path, default=RAW_DIR, help="carpeta con los CSV de origen")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="base de datos SQLite de destino")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s", datefmt="%H:%M:%S")

    resumen = ejecutar(args.raw, args.db)
    informe = args.db.with_name("informe_calidad.json")
    informe.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Resumen: %s", json.dumps(resumen, ensure_ascii=False))
    log.info("Informe de calidad en %s", informe)
    return 0


if __name__ == "__main__":
    sys.exit(main())
