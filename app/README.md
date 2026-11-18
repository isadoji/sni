# Explorador interactivo del padrón SNI/SNII

App de [Streamlit](https://streamlit.io) sobre la serie histórica 2015-2025.
Filtros por **año, área de conocimiento, nivel, género, región y entidad
federativa**, con mapa coroplético de México por estado y desgloses.

## Estructura (un módulo = una responsabilidad)

```
app/
├── streamlit_app.py          # entrada: Dashboard().run()
├── build_dataset.py          # CLI del ETL -> data/sni_tidy.csv
├── requirements.txt
├── .streamlit/config.toml
├── data/
│   ├── sni_tidy.csv          # generado por build_dataset.py (se versiona)
│   └── mexico_estados.geojson
└── sni_dashboard/
    ├── config.py             # rutas, catálogos, YearConfig por año
    ├── normalize.py          # GenderClassifier · AreaClassifier · EntidadNormalizer · RegionMapper
    ├── etl.py                # PadronReader (1 año) · DatasetBuilder (agrega + guarda)
    ├── data.py               # SNIRepository: carga + catálogos de opciones + filter()
    ├── filters.py            # FilterState (dataclass) · SidebarController (dibuja la barra)
    ├── charts.py             # Metrics (KPIs) · ChartBuilder (figuras Plotly)
    └── app.py                # Dashboard: compone repo -> filtros -> figuras
```

Flujo: `PadronReader` lee cada `SNI<año>.xlsx` y lo normaliza con las 4 clases de
`normalize.py`; `DatasetBuilder` concatena, descarta filas sin área/nivel y agrega
a `AÑO × AREA × NIVEL × GENERO × ENTIDAD × REGION → N`. La app carga ese CSV en
`SNIRepository`, `SidebarController` produce un `FilterState`, y `ChartBuilder`
arma el mapa y las gráficas del subconjunto filtrado.

## Uso local

```bash
cd app
pip install -r requirements.txt

# 1. (re)generar el dataset desde los padrones ../datasets/SNI*.xlsx
python build_dataset.py --check

# 2. levantar la app
streamlit run streamlit_app.py
```

## Despliegue en Render

El repo trae `render.yaml` en la raíz (Blueprint). En Render:
**New → Blueprint → conecta el repo** y confirma. Queda un servicio web *free*
que corre `streamlit run streamlit_app.py` con `rootDir: app`.

Manual (sin Blueprint): New → Web Service, Root Directory `app`,
Build `pip install -r requirements.txt`,
Start `streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0`.

`data/sni_tidy.csv` se versiona, así que el deploy **no** necesita los `.xlsx` ni
volver a correr el ETL.

## Notas de datos

- **2022 se excluye**: el archivo oficial no es utilizable.
- El **género** (2026-11-18) lo asigna `SexoResolver` (`normalize.py`) en este orden:
  1. el título del registro (DR./DRA., MTRO./MTRA.; columna NOBILIS o GRADO ACADÉMICO, ~98 % de 2015–2023);
  2. el mismo CVU con título en otro año (2019, 2021, 2023);
  3. el mismo nombre completo con título en otro año, si siempre tiene el mismo sexo;
  4. el nombre de pila visto con título ≥5 veces y ≥95 % con un sexo;
  5. el catálogo `datasets/mujeres.csv`, solo como último recurso (~2 % de 2024 y 2025).

  2024 y 2025 no traen título; se resuelven sobre todo por CVU. Validado ocultando el
  título de 2023: acierto 99.1 %, % de mujeres 39.31 contra 39.30 real. El catálogo
  solo, usado hasta esta fecha, clasificaba como mujer al 12.3 % de los hombres
  (contiene «juan» y «jesus»; bastaba una palabra del nombre en la lista) y sobrestimaba
  a las mujeres ~6 pp en todos los años (2025: 46.4 % → 40.6 %). La columna GENERO de
  `SNI2025_CLASIFICADO.xlsx` no se usa.
- La **taxonomía de áreas** cambió de 7 a 9 ejes en 2023; se homologa a 8 ejes
  comparables en toda la serie (misma lógica que `sni_historico_genero.ipynb`).
- **Entidad**: se normaliza a los 32 nombres del GeoJSON; los registros sin
  entidad o en el extranjero (~6.6 %) van al bucket `Sin dato / Extranjero` y no
  aparecen en el mapa.
- **8 regiones geográficas**: Noroeste, Noreste, Occidente, Oriente, Centronorte,
  Centrosur, Suroeste, Sureste (reparto en `config.REGION_POR_ESTADO`).
