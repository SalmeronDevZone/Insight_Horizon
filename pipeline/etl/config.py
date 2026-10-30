"""Configuración del pipeline: rutas por defecto y valores de referencia."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RAW_DIR = RAIZ / "datos" / "raw"
DB_PATH = RAIZ / "salida" / "ventas.db"

FICHERO_CLIENTES = "clientes.csv"
FICHERO_PRODUCTOS = "productos.csv"
PATRON_PEDIDOS = "pedidos_*.csv"

# Formatos de fecha que llegan de los sistemas de origen (se normalizan a ISO 8601).
FORMATOS_FECHA = ("%Y-%m-%d", "%d/%m/%Y")

# Sinónimos de canal que se aceptan y su valor normalizado.
CANALES = {
    "web": "web",
    "online": "web",
    "tienda": "tienda",
    "store": "tienda",
    "app": "app",
}
