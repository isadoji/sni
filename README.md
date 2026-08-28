# Estadística del sistema nacional de investigadores

https://conacyt.mx/sistema-nacional-de-investigadores/archivo-historico/

## Contenido

- `sni2025.ipynb` — clasificación por género y desglose por nivel y área de conocimiento (Biología y Química, Físico-Matemáticas, Ingenierías, Ciencias Sociales) del padrón SNI 2025.
- `sni2021.ipynb` — análisis del padrón SNI 2021.
- `sni_historico_genero.ipynb` — serie histórica 2015-2025 (excluye 2022, archivo oficial no utilizable) de investigadores por año y género, con desglose por nivel (C, 1, 2, 3, E) y por área de conocimiento (Físico-Matemáticas, Ciencias Sociales). Fuente: [Archivo histórico del SNII](https://secihti.mx/snii/archivo-historico-del-snii/).
  Al final incluye, para cada año de la serie, un panel de gráficos de telaraña (spider web) por nivel (C, 1, 2, 3, E) que compara las 8 áreas de conocimiento y género. El SNI cambió su taxonomía de áreas de 7 a 9 en 2023 (división de *Humanidades y Ciencias de la Conducta*, renombres de otras dos áreas, y la nueva área *Interdisciplinaria*); `area_canonica()` fusiona esos cambios en una taxonomía de 8 ejes comparable en toda la serie, documentada en el propio notebook.
- `datasets/` — padrones anuales (`SNI<año>.xlsx`), catálogo de nombres de mujeres (`mujeres.csv`) usado para la clasificación de género, y `resumen_area_nivel_genero_por_anio.csv` (conteos por año/área canónica/nivel/género, usado por los spider webs).
- `fig_sni/` — gráficas generadas por los notebooks, incluyendo `spider_nivel_area_genero_<año>.jpg` (2015-2021, 2023-2025) para cada año de la serie histórica.

## Dashboard

Dashboard interactivo (Plotly.js, sin backend) con estos mismos datos, publicado en el portafolio: https://isadoji.github.io/sni-dashboard.html

## App interactiva (`app/`)

Explorador en Streamlit con filtros por **año, área, nivel, género, región y
entidad federativa** y mapa coroplético de México por estado. Proyecto modular
(`sni_dashboard/`, una clase por tarea) listo para desplegar en Render con el
`render.yaml` de la raíz. Ver [`app/README.md`](app/README.md).

```bash
cd app && pip install -r requirements.txt
python build_dataset.py --check     # genera app/data/sni_tidy.csv
streamlit run streamlit_app.py
```
