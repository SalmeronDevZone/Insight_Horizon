# Retos sobre el pipeline

Ocho ejercicios para llevar el pipeline al nivel de un entorno real. Están ordenados de menos a más difícil. Cada uno trae pistas y un **criterio de aceptación**: escribe la prueba en `tests/` y no des el reto por terminado hasta que `python -m unittest` salga en verde.

| # | Reto | Nivel | Qué practicas |
| --- | --- | --- | --- |
| 1 | Rechazar ventas con fecha futura | 🟢 Fácil | Reglas de calidad |
| 2 | Contrato de datos en la cabecera | 🟢 Fácil | Fallar rápido, validación de esquema |
| 3 | Consultas analíticas sobre gold | 🟡 Medio | SQL analítico, funciones de ventana |
| 4 | Métricas de calidad por ejecución | 🟡 Medio | Observabilidad de datos |
| 5 | Exportar gold particionado | 🟡 Medio | Particionado tipo data lake |
| 6 | Ejecución programada en GitHub Actions | 🟡 Medio | Orquestación, CI/CD |
| 7 | Borrados en origen | 🔴 Difícil | CDC, borrado lógico |
| 8 | SCD tipo 2 en `dim_cliente` | 🔴 Difícil | Modelado dimensional, historial |

---

## 1. Rechazar ventas con fecha futura 🟢

Una venta con fecha posterior a hoy es un error del sistema de origen.

- **Pista:** `calidad.validar_pedidos` ya acumula motivos; añade `"fecha futura"`.
- **Aceptación:** una fila con fecha de mañana acaba en `cuarentena` con ese motivo, y las de los datos de ejemplo siguen siendo válidas.

## 2. Contrato de datos en la cabecera 🟢

Si el origen cambia el formato (renombra o quita una columna), hoy el pipeline falla con un `KeyError` poco claro.

- **Pista:** define las columnas obligatorias de cada fichero en `config.py` y compruébalas en `extraer.leer_csv` antes de procesar nada.
- **Aceptación:** con un CSV sin la columna `canal`, el pipeline lanza un error que nombra el fichero y la columna que falta, y **no escribe nada** en la base de datos.

## 3. Consultas analíticas sobre gold 🟡

Escribe estas consultas sobre el modelo en estrella (`salida/ventas.db`):

1. Importe por mes y categoría de producto.
2. Los 3 clientes que más han gastado, con su ciudad.
3. Ticket medio (importe por venta) por canal.
4. Crecimiento del importe de febrero respecto a enero, en %.
5. Ranking de productos dentro de cada categoría (`RANK()`).
6. Porcentaje del importe que se vende en fin de semana.

- **Pista:** `sqlite3 salida/ventas.db` o cualquier cliente SQL. Para el 4 y el 5, funciones de ventana (`LAG`, `RANK`).
- **Soluciones:** [`soluciones/consultas.sql`](soluciones/consultas.sql). Inténtalo antes de mirarlas.

## 4. Métricas de calidad por ejecución 🟡

Hoy el informe de calidad se sobrescribe en cada ejecución.

- **Pista:** crea una tabla `ejecuciones` (inicio, fin, ficheros, filas, rechazadas, % de rechazo) y rellénala al final de `pipeline.ejecutar`.
- **Aceptación:** después de dos ejecuciones hay dos filas, y se emite un `WARNING` si el % de rechazo de una ejecución supera el 10 %. Con los datos de ejemplo es un 18,4 %, así que debe avisar.

## 5. Exportar gold particionado 🟡

Los data lakes guardan los hechos particionados por fecha para leer sólo lo necesario.

- **Pista:** genera `salida/gold/fact_ventas/anio=2025/mes=01/ventas.csv`, uno por mes.
- **Aceptación:** al reprocesar no quedan particiones viejas, y la suma de filas de todas las particiones es igual a `COUNT(*)` de `fact_ventas`.

## 6. Ejecución programada en GitHub Actions 🟡

- **Pista:** el workflow [`.github/workflows/pipeline.yml`](../../.github/workflows/pipeline.yml) ya pasa las pruebas en cada push. Añade un disparador `schedule` (cron) y guarda la base de datos como artefacto.
- **Aceptación:** en la pestaña *Actions* aparece una ejecución programada con los artefactos `informe-calidad` y `ventas-db`.

## 7. Borrados en origen 🔴

Si un fichero se reprocesa y ya no trae una venta que sí traía antes, hoy esa venta se queda en silver para siempre.

- **Pista:** compara los `id_venta` de silver que vinieron de ese archivo con los del fichero nuevo. Mejor un borrado lógico (columna `eliminado`) que un `DELETE`: así se puede auditar.
- **Aceptación:** al quitar una línea de `pedidos_2025-01.csv` y reprocesar, la venta desaparece de `fact_ventas`, pero sigue en silver marcada como eliminada.

## 8. SCD tipo 2 en `dim_cliente` 🔴

Ahora, si un cliente se muda, se pierde la ciudad anterior (SCD tipo 1). Negocio quiere analizar las ventas por la ciudad que tenía el cliente **cuando compró**.

- **Pista:** añade `clave_cliente` (clave subrogada), `valido_desde`, `valido_hasta` y `es_actual`. Un cambio cierra la versión vigente y abre una nueva. `fact_ventas` debe guardar la `clave_cliente` vigente en la fecha de la venta.
- **Aceptación:** si cambias la ciudad de `C01` en `clientes.csv` y reprocesas, `dim_cliente` tiene dos versiones de `C01` y las ventas anteriores al cambio siguen apuntando a la ciudad antigua.
