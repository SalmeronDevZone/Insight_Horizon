# 📅 Tabla de Fechas en Power BI (DAX)

Este proyecto contiene scripts en **DAX** para la creación de una **tabla de fechas personalizada** en Power BI.  
Una tabla de fechas bien estructurada es fundamental para realizar análisis de tiempo (Time Intelligence) y asegurar la correcta relación entre las tablas de hechos.

---

## 🧩 Objetivo

Crear una tabla de fechas completa, flexible y reutilizable, que permita:

- Analizar métricas por año, mes, trimestre, semana, día, etc.
- Soportar funciones de inteligencia de tiempo (`TOTALYTD`, `SAMEPERIODLASTYEAR`, etc.).
- Servir como **tabla puente** entre múltiples tablas de hechos que compartan campos de fecha.

---

## ✅ Importancia de marcarla como **Tabla de Fechas**

Una vez creada, **es esencial marcarla como “Tabla de fechas”** dentro de Power BI:

1. En la vista de datos, selecciona la tabla de calendario.  
2. En la cinta de opciones, elige **"Marcar como tabla de fechas"**.  
3. Selecciona la columna de tipo fecha principal (`[Date]`).

> 🔹 Esto permite que Power BI y DAX reconozcan esta tabla como la fuente oficial para los cálculos de tiempo, habilitando correctamente las funciones de inteligencia temporal.

---

## ⚠️ Desactivar la función nativa de detección automática

Power BI, por defecto, **crea tablas de fechas automáticas** para cada campo de fecha.  
Esto puede generar **duplicación de tablas**, **errores de relación** o **baja eficiencia** en modelos grandes.

Para evitarlo:

1. Ve a **Archivo > Opciones y configuración > Opciones > Carga de datos**.  
2. Desactiva la opción:  
   > “Auto Date/Time for new files”  
3. Así garantizas que solo se use **tu tabla de fechas personalizada** en el modelo.

---

## 🔗 Uso como tabla puente entre tablas de hechos

Una **tabla de fechas centralizada** puede servir como **tabla puente** cuando tienes **varias tablas de hechos** (por ejemplo, *Ventas* y *Pedidos*) que comparten campos de fecha.



