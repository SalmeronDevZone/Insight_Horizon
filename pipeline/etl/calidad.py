"""Calidad de datos: normaliza los valores de origen y separa las filas válidas de las que van a cuarentena."""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from .config import CANALES, FORMATOS_FECHA

CENTIMOS = Decimal("0.01")


@dataclass
class Rechazo:
    num_fila: int
    fila: dict[str, str]
    motivos: list[str]


@dataclass
class Resultado:
    validas: list[dict] = field(default_factory=list)
    rechazadas: list[Rechazo] = field(default_factory=list)
    duplicados: int = 0


# ------------------------------------------------------------------ conversiones


def parsear_fecha(texto: str) -> date | None:
    texto = texto.strip()
    for formato in FORMATOS_FECHA:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def parsear_decimal(texto: str) -> Decimal | None:
    """Acepta '24.50' y '24,50' (coma decimal de Excel en español)."""
    texto = texto.strip().replace(",", ".")
    if not texto:
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    return valor.quantize(CENTIMOS) if valor.is_finite() else None


def parsear_entero(texto: str) -> int | None:
    texto = texto.strip()
    try:
        return int(texto)
    except ValueError:
        return None


def normalizar_canal(texto: str) -> str | None:
    return CANALES.get(texto.strip().lower())


# ------------------------------------------------------------------ datos maestros


def normalizar_cliente(fila: dict[str, str]) -> dict:
    return {
        "id_cliente": fila["id_cliente"].strip().upper(),
        "nombre": " ".join(fila["nombre"].split()),
        "email": fila["email"].strip().lower(),
        "ciudad": fila["ciudad"].strip().title(),
        "fecha_alta": fila["fecha_alta"].strip(),
    }


def normalizar_producto(fila: dict[str, str]) -> dict:
    return {
        "codigo_producto": fila["codigo_producto"].strip().upper(),
        "nombre": " ".join(fila["nombre"].split()),
        "categoria": fila["categoria"].strip(),
        "precio_catalogo": parsear_decimal(fila["precio_catalogo"]),
    }


# ------------------------------------------------------------------ pedidos


def validar_pedidos(filas: list[dict[str, str]], clientes: set[str], productos: set[str]) -> Resultado:
    """Normaliza cada pedido y aplica las reglas de calidad.

    - Una fila con al menos un problema va a cuarentena con todos sus motivos (no sólo el primero).
    - Si un id_venta se repite en el mismo fichero, gana la última aparición y se cuenta como duplicado.
    """
    resultado = Resultado()
    por_id: dict[str, dict] = {}
    for num_fila, fila in enumerate(filas, start=2):  # la fila 1 es la cabecera
        motivos = []
        id_venta = fila.get("id_venta", "").strip().upper()
        fecha = parsear_fecha(fila.get("fecha", ""))
        id_cliente = fila.get("id_cliente", "").strip().upper()
        codigo = fila.get("codigo_producto", "").strip().upper()
        cantidad = parsear_entero(fila.get("cantidad", ""))
        precio = parsear_decimal(fila.get("precio_unitario", ""))
        canal = normalizar_canal(fila.get("canal", ""))

        if not id_venta:
            motivos.append("id_venta vacío")
        if fecha is None:
            motivos.append("fecha inválida")
        if id_cliente not in clientes:
            motivos.append("cliente desconocido")
        if codigo not in productos:
            motivos.append("producto desconocido")
        if cantidad is None or cantidad <= 0:
            motivos.append("cantidad inválida")
        if precio is None or precio < 0:
            motivos.append("precio inválido")
        if canal is None:
            motivos.append("canal desconocido")

        if motivos:
            resultado.rechazadas.append(Rechazo(num_fila, fila, motivos))
            continue
        if id_venta in por_id:
            resultado.duplicados += 1
        por_id[id_venta] = {
            "id_venta": id_venta,
            "fecha": fecha.isoformat(),
            "id_cliente": id_cliente,
            "codigo_producto": codigo,
            "cantidad": cantidad,
            "precio_unitario": precio,
            "canal": canal,
        }
    resultado.validas = list(por_id.values())
    return resultado
