-- Soluciones del reto 3: consultas analíticas sobre el modelo en estrella.
-- Ejecutar después del pipeline:  sqlite3 salida/ventas.db < retos/soluciones/consultas.sql

-- 1. Importe por mes y categoría de producto
SELECT d.anio, d.mes, d.nombre_mes, p.categoria,
       ROUND(SUM(f.importe), 2) AS importe
FROM fact_ventas f
JOIN dim_fecha d    ON d.fecha = f.fecha
JOIN dim_producto p ON p.codigo_producto = f.codigo_producto
GROUP BY d.anio, d.mes, d.nombre_mes, p.categoria
ORDER BY d.anio, d.mes, importe DESC;

-- 2. Los 3 clientes que más han gastado, con su ciudad
SELECT c.id_cliente, c.nombre, c.ciudad,
       ROUND(SUM(f.importe), 2) AS importe,
       COUNT(*) AS ventas
FROM fact_ventas f
JOIN dim_cliente c ON c.id_cliente = f.id_cliente
GROUP BY c.id_cliente, c.nombre, c.ciudad
ORDER BY importe DESC
LIMIT 3;

-- 3. Ticket medio por canal
SELECT canal,
       COUNT(*) AS ventas,
       ROUND(AVG(importe), 2) AS ticket_medio
FROM fact_ventas
GROUP BY canal
ORDER BY ticket_medio DESC;

-- 4. Crecimiento del importe mes a mes (LAG)
WITH por_mes AS (
    SELECT d.anio, d.mes, SUM(f.importe) AS importe
    FROM fact_ventas f
    JOIN dim_fecha d ON d.fecha = f.fecha
    GROUP BY d.anio, d.mes
)
SELECT anio, mes,
       ROUND(importe, 2) AS importe,
       ROUND(100.0 * (importe - LAG(importe) OVER (ORDER BY anio, mes))
             / LAG(importe) OVER (ORDER BY anio, mes), 1) AS crecimiento_pct
FROM por_mes
ORDER BY anio, mes;

-- 5. Ranking de productos dentro de cada categoría (RANK)
SELECT p.categoria, p.nombre,
       ROUND(SUM(f.importe), 2) AS importe,
       RANK() OVER (PARTITION BY p.categoria ORDER BY SUM(f.importe) DESC) AS puesto
FROM fact_ventas f
JOIN dim_producto p ON p.codigo_producto = f.codigo_producto
GROUP BY p.categoria, p.nombre
ORDER BY p.categoria, puesto;

-- 6. Porcentaje del importe vendido en fin de semana
SELECT ROUND(100.0 * SUM(CASE WHEN d.es_fin_de_semana = 1 THEN f.importe ELSE 0 END) / SUM(f.importe), 1)
           AS pct_fin_de_semana
FROM fact_ventas f
JOIN dim_fecha d ON d.fecha = f.fecha;
