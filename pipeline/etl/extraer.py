"""Extracción: lectura de CSV y huella (checksum) de cada fichero para cargas idempotentes."""
import csv
import hashlib
from pathlib import Path


def checksum(ruta: Path) -> str:
    """SHA-256 del contenido: si el fichero no cambia, no se vuelve a cargar."""
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_csv(ruta: Path) -> list[dict[str, str]]:
    """Lee un CSV con cabecera. utf-8-sig tolera el BOM que añade Excel."""
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        lector = csv.DictReader(f)
        return [{(k or "").strip(): (v or "") for k, v in fila.items()} for fila in lector]
