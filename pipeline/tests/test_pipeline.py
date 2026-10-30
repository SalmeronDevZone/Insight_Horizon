"""Pruebas del pipeline. Ejecutar desde la carpeta pipeline/:  python -m unittest -v"""
import logging
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from etl import calidad
from etl.config import RAW_DIR
from etl.pipeline import ejecutar

logging.disable(logging.CRITICAL)

CLIENTES = {"C01", "C02"}
PRODUCTOS = {"P001"}


def pedido(**cambios) -> dict[str, str]:
    fila = {
        "id_venta": "V1",
        "fecha": "2025-01-10",
        "id_cliente": "C01",
        "codigo_producto": "P001",
        "cantidad": "1",
        "precio_unitario": "10.00",
        "canal": "web",
    }
    fila.update(cambios)
    return fila


class TestCalidad(unittest.TestCase):
    def test_fechas_en_los_dos_formatos_de_origen(self):
        self.assertEqual(calidad.parsear_fecha("2025-01-15"), date(2025, 1, 15))
        self.assertEqual(calidad.parsear_fecha("15/01/2025"), date(2025, 1, 15))
        self.assertIsNone(calidad.parsear_fecha("2025-13-01"))
        self.assertIsNone(calidad.parsear_fecha(""))

    def test_decimales_con_coma_o_punto(self):
        self.assertEqual(calidad.parsear_decimal("24,50"), Decimal("24.50"))
        self.assertEqual(calidad.parsear_decimal(" 79.9 "), Decimal("79.90"))
        self.assertIsNone(calidad.parsear_decimal("abc"))
        self.assertIsNone(calidad.parsear_decimal("NaN"))

    def test_canal_normalizado(self):
        self.assertEqual(calidad.normalizar_canal("WEB "), "web")
        self.assertEqual(calidad.normalizar_canal("Store"), "tienda")
        self.assertIsNone(calidad.normalizar_canal("fax"))

    def test_una_fila_valida_sale_tipada(self):
        res = calidad.validar_pedidos([pedido(precio_unitario="10,5", canal=" App")], CLIENTES, PRODUCTOS)
        self.assertEqual(res.rechazadas, [])
        self.assertEqual(res.validas[0]["precio_unitario"], Decimal("10.50"))
        self.assertEqual(res.validas[0]["canal"], "app")

    def test_se_informan_todos_los_motivos_de_rechazo(self):
        mala = pedido(id_cliente="C99", codigo_producto="P999", cantidad="0", precio_unitario="-1", canal="fax", fecha="ayer")
        res = calidad.validar_pedidos([mala], CLIENTES, PRODUCTOS)
        self.assertEqual(res.validas, [])
        self.assertEqual(
            res.rechazadas[0].motivos,
            ["fecha inválida", "cliente desconocido", "producto desconocido", "cantidad inválida", "precio inválido", "canal desconocido"],
        )
        self.assertEqual(res.rechazadas[0].num_fila, 2)

    def test_duplicados_en_el_mismo_fichero_gana_la_ultima_aparicion(self):
        res = calidad.validar_pedidos([pedido(cantidad="1"), pedido(cantidad="3")], CLIENTES, PRODUCTOS)
        self.assertEqual(res.duplicados, 1)
        self.assertEqual(len(res.validas), 1)
        self.assertEqual(res.validas[0]["cantidad"], 3)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.raw = self.tmp / "raw"
        self.raw.mkdir()
        self.db = self.tmp / "ventas.db"
        for nombre in ("clientes.csv", "productos.csv"):
            shutil.copy(RAW_DIR / nombre, self.raw)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copiar(self, *nombres):
        for nombre in nombres:
            shutil.copy(RAW_DIR / nombre, self.raw)

    def consulta(self, sql, *params):
        conexion = sqlite3.connect(self.db)
        try:
            return conexion.execute(sql, params).fetchall()
        finally:
            conexion.close()

    def test_resultado_con_los_datos_de_ejemplo(self):
        self.copiar("pedidos_2025-01.csv", "pedidos_2025-02.csv")
        r = ejecutar(self.raw, self.db)
        self.assertEqual(r["filas"], 38)
        self.assertEqual(r["validas"], 29)
        self.assertEqual(r["rechazadas"], 7)
        self.assertEqual(r["duplicados"], 2)
        self.assertEqual(r["ventas_gold"], 28)  # 29 válidas, pero V0003 llega dos veces (corrección)
        self.assertEqual(r["importe_total"], 5110.12)
        self.assertEqual(r["en_cuarentena"], 7)

    def test_es_idempotente(self):
        self.copiar("pedidos_2025-01.csv", "pedidos_2025-02.csv")
        primera = ejecutar(self.raw, self.db)
        segunda = ejecutar(self.raw, self.db)
        self.assertEqual(segunda["procesados"], [])
        self.assertEqual(segunda["omitidos"], ["pedidos_2025-01.csv", "pedidos_2025-02.csv"])
        self.assertEqual(segunda["ventas_gold"], primera["ventas_gold"])
        self.assertEqual(segunda["importe_total"], primera["importe_total"])
        self.assertEqual(self.consulta("SELECT COUNT(*) FROM bronze_pedidos")[0][0], 38)

    def test_carga_incremental(self):
        self.copiar("pedidos_2025-01.csv")
        self.assertEqual(ejecutar(self.raw, self.db)["ventas_gold"], 15)
        self.copiar("pedidos_2025-02.csv")
        r = ejecutar(self.raw, self.db)
        self.assertEqual(r["procesados"], ["pedidos_2025-02.csv"])
        self.assertEqual(r["omitidos"], ["pedidos_2025-01.csv"])
        self.assertEqual(r["ventas_gold"], 28)

    def test_correccion_tardia_actualiza_la_venta(self):
        self.copiar("pedidos_2025-01.csv")
        ejecutar(self.raw, self.db)
        self.assertEqual(self.consulta("SELECT cantidad FROM fact_ventas WHERE id_venta = 'V0003'"), [(1,)])
        self.copiar("pedidos_2025-02.csv")
        ejecutar(self.raw, self.db)
        self.assertEqual(self.consulta("SELECT cantidad, importe FROM fact_ventas WHERE id_venta = 'V0003'"), [(2, 119.98)])

    def test_un_fichero_modificado_se_reprocesa(self):
        self.copiar("pedidos_2025-01.csv")
        ejecutar(self.raw, self.db)
        with open(self.raw / "pedidos_2025-01.csv", "a", encoding="utf-8") as f:
            f.write("V0099,2025-01-31,C01,P001,1,79.90,web\n")
        r = ejecutar(self.raw, self.db)
        self.assertEqual(r["procesados"], ["pedidos_2025-01.csv"])
        self.assertEqual(r["ventas_gold"], 16)
        self.assertEqual(self.consulta("SELECT COUNT(*) FROM cuarentena")[0][0], 5)  # no se duplica la cuarentena

    def test_integridad_del_modelo_en_estrella(self):
        self.copiar("pedidos_2025-01.csv", "pedidos_2025-02.csv")
        ejecutar(self.raw, self.db)
        huerfanas = self.consulta(
            """SELECT COUNT(*) FROM fact_ventas f
               LEFT JOIN dim_cliente c USING (id_cliente)
               LEFT JOIN dim_producto p USING (codigo_producto)
               LEFT JOIN dim_fecha d USING (fecha)
               WHERE c.id_cliente IS NULL OR p.codigo_producto IS NULL OR d.fecha IS NULL"""
        )
        self.assertEqual(huerfanas, [(0,)])
        self.assertEqual(self.consulta("SELECT COUNT(*) FROM fact_ventas WHERE importe != ROUND(cantidad * precio_unitario, 2)"), [(0,)])
        self.assertEqual(self.consulta("SELECT ciudad FROM dim_cliente WHERE id_cliente = 'C02'"), [("Sevilla",)])

    def test_sin_pedidos_no_falla(self):
        r = ejecutar(self.raw, self.db)
        self.assertEqual((r["ventas_gold"], r["importe_total"]), (0, 0))


if __name__ == "__main__":
    unittest.main()
