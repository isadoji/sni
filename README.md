# Estadística del sistema nacional de investigadores

https://conacyt.mx/sistema-nacional-de-investigadores/archivo-historico/

## Contenido

- `sni2025.ipynb` — clasificación por género y desglose por nivel y área de conocimiento (Biología y Química, Físico-Matemáticas, Ingenierías, Ciencias Sociales) del padrón SNI 2025.
- `sni2021.ipynb` — análisis del padrón SNI 2021.
- `sni_historico_genero.ipynb` — serie histórica 2015-2025 de investigadores por año y género, con desglose por nivel (C, 1, 2, 3, E) y por área de conocimiento (Físico-Matemáticas, Ciencias Sociales). Fuente: [Archivo histórico del SNII](https://secihti.mx/snii/archivo-historico-del-snii/).
  Al final incluye, para cada año de la serie, un panel de gráficos de telaraña (spider web) por nivel (C, 1, 2, 3, E) que compara las 8 áreas de conocimiento y género. La escala radial de cada nivel es la misma en todos los años (el máximo de la serie), para que se vea el crecimiento. El SNI cambió su taxonomía de áreas de 7 a 9 en 2022 (división de *Humanidades y Ciencias de la Conducta*, renombres de otras dos áreas, y la nueva área *Interdisciplinaria*); `area_canonica()` fusiona esos cambios en una taxonomía de 8 ejes comparable en toda la serie, documentada en el propio notebook.
- `permanencia/` — permanencia y promoción por sexo en las convocatorias 2023 y 2024. Las personas cuya vigencia vence en *t* se siguen en el padrón de *t+1* por CVU (renovado / promovido / bajó / emérito / no está / prorrogado). El sexo se toma del grado del padrón 2023 (DR./DRA.), no del diccionario de nombres, que clasifica como mujer al 12.3 % de los hombres y como hombre al 4.3 % de las mujeres (neto, +6 pp de mujeres). Script `permanencia.py`; reporte `reporte_permanencia.pdf`, generado por `gen_reporte.py` (`/usr/bin/python3`, después nbconvert con el kernel `sni-base`). Resultado (2026-11-18): a igual nivel, área y año, las mujeres siguen en el SNII +2.2 pp [+0.6, +3.8] y se promueven igual (−0.5 pp [−2.9, +1.9]). Reciben más prórrogas sin evaluación (+2.6 pp; nivel III 18 % contra 9 %). El ingreso de personas nuevas no se puede medir: no hay lista de solicitantes rechazados.
- `datasets/` — padrones anuales (`SNI<año>.xlsx`), catálogo de nombres de mujeres (`mujeres.csv`) usado para la clasificación de género (solo como último recurso: la app y los notebooks asignan el género con `SexoResolver`, por título, CVU y nombre en otros años; el catálogo solo sobrestimaba a las mujeres ~6 pp, ver la nota de género en `app/README.md`), y `resumen_area_nivel_genero_por_anio.csv` (conteos por año/área canónica/nivel/género, usado por los spider webs).
- `fig_sni/` — gráficas generadas por los notebooks, incluyendo `spider_nivel_area_genero_<año>.jpg` (2015-2025) para cada año de la serie histórica.

## Dashboards

- **App interactiva (Streamlit) — en vivo:** <https://sni-explorer.onrender.com>
- **Dashboard estático (Plotly.js, sin backend)**, publicado en el portafolio:
  <https://isadoji.github.io/sni-dashboard.html>

## App interactiva (`app/`)

Explorador *SNI Explorer* en [Streamlit](https://streamlit.io) sobre la serie
histórica 2015-2025. **Versión 2** (en Render desde 2026-11-18): una sola fila de
botones de año sobre el mapa (controla el mapa y los spider web) y el mapa de México
como selector de estados, con escala de color fija en los años individuales; sin
selección muestra KPIs nacionales y las gráficas de evolución, nivel, área, % de mujeres y de hombres por estado (de mayor a menor % de mujeres) e investigadores por 10 000 habitantes por estado (población de CONAPO);
con uno o varios estados, sus KPIs y un spider web nivel × área × género por estado.
La barra lateral muestra la fuente, las autoras (Isabel Domínguez Jiménez y María
Elena Tejeda Yeomans), el enlace al código y cómo citar. La **versión 1** (filtros
por año, área, nivel, género, región y entidad) queda de respaldo en
`app/streamlit_app_v1.py` (tag `app-v1`); detalles en `app/README.md`. Desplegada en Render como servicio web gratuito
(la instancia free se suspende tras un rato de inactividad, así que la primera
visita puede tardar ~50 s en despertar).

### Estructura

```
app/
├── streamlit_app.py          # entrada v2: DashboardV2().run()
├── streamlit_app_v1.py       # entrada v1 (respaldo)
├── assets/                   # logo SNI Explorer
├── build_dataset.py          # CLI del ETL -> data/sni_tidy.csv
├── requirements.txt
├── render.yaml               # (en la raíz del repo) Blueprint de Render
├── .streamlit/config.toml
├── data/
│   ├── sni_tidy.csv          # generado por build_dataset.py (SE VERSIONA)
│   └── mexico_estados.geojson
└── sni_dashboard/            # un módulo = una responsabilidad
    ├── config.py             # rutas, catálogos, YearConfig por año
    ├── normalize.py          # GenderClassifier · AreaClassifier · EntidadNormalizer · RegionMapper
    ├── etl.py                # PadronReader (1 año) · DatasetBuilder (agrega + guarda)
    ├── data.py               # SNIRepository: carga + catálogos de opciones + filter()
    ├── filters.py            # FilterState (dataclass) · SidebarController
    ├── charts.py             # Metrics (KPIs) · ChartBuilder (figuras Plotly)
    ├── app.py                # v1 Dashboard
    └── app_v2.py             # v2 DashboardV2 + MapaSelector
```

`app/data/sni_tidy.csv` (AÑO × AREA × NIVEL × GENERO × ENTIDAD × REGION → N,
~16 200 filas, 333 326 investigadores) **se versiona**, así que la app y el
deploy **no** necesitan los `.xlsx` ni volver a correr el ETL.

### Correr en local

```bash
cd app
pip install -r requirements.txt

# (opcional) regenerar el dataset desde los padrones ../datasets/SNI*.xlsx
python build_dataset.py --check        # --check compara sin sobrescribir
python build_dataset.py                # escribe data/sni_tidy.csv

# levantar la app  ->  http://localhost:8501
streamlit run streamlit_app.py
```

### Montar en Render

El repo trae `render.yaml` en la raíz (Blueprint): web service `sni-explorer`,
plan *free*, `rootDir: app`, build `pip install -r requirements.txt`, start
`streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`.
`autoDeploy` está activado, así que cada push a `main` vuelve a desplegar solo.

**Con Blueprint (recomendado):**

1. En <https://dashboard.render.com> → **New → Blueprint**.
2. Conecta la cuenta de GitHub y elige el repo `isadoji/sni`, branch `main`.
3. Render lee `render.yaml`, muestra el servicio `sni-explorer`; dale un nombre
   al Blueprint y **Deploy Blueprint**.
4. Al terminar queda en `https://<nombre-servicio>.onrender.com`.

**Manual (sin Blueprint):** New → **Web Service** → repo `isadoji/sni` →
Root Directory `app`, Runtime `Python 3`,
Build `pip install -r requirements.txt`,
Start `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`.

Ver también [`app/README.md`](app/README.md) para las notas de datos
(padrón 2022 en la hoja `2022`, inferencia de género, homologación de áreas 7→9→8,
normalización de entidad y bucket *Sin dato / Extranjero*).
