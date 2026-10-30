# Notebooks de análisis

Ejercicios resueltos a partir del libro **«Arquitectura e ingeniería de datos para principiantes»**. Cada recurso empieza por el número de capítulo: `05_dataset_correlacion_csv` es el conjunto de datos de correlación del capítulo 5.

| Notebook | Qué hace | Librerías |
| --- | --- | --- |
| `05_Análisis_de_Correlación_Notebook.ipynb` | Coeficientes de correlación de Pearson entre ventas e inversión en publicidad, con mapa de calor | pandas, NumPy, Matplotlib, seaborn |
| `07_Análisis_de_Optimizacion_Notebook.ipynb` | Optimización con restricciones | GEKKO |
| `07_Programacion_No_Linear_Notebook.ipynb` | Programación no lineal: mezcla de producción que maximiza el beneficio de una fábrica de muebles | GEKKO, NumPy |
| `07_Simulacion_Pendulo.ipynb` | Simulación de un péndulo resolviendo su ecuación diferencial | SciPy, Matplotlib |
| `07_recomendacion_knn.ipynb` | Sistema de recomendación con k vecinos más próximos (k-NN) | scikit-learn, pandas, seaborn |
| `07_simulacion_montecarlo.ipynb` | Simulación de Montecarlo | NumPy, Matplotlib |
| `10_01_select_general.sql` | Estructura base de una consulta SQL | SQL |

Datos: `05_dataset_correlacion_csv.csv` y su versión Excel (`05_dataset_correlacion_xlsx.xlsx`).

## Abrirlos

```bash
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter lab
```
