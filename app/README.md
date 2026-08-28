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
- El **género** se infiere por nombre de pila con el catálogo `datasets/mujeres.csv`.
- La **taxonomía de áreas** cambió de 7 a 9 ejes en 2023; se homologa a 8 ejes
  comparables en toda la serie (misma lógica que `sni_historico_genero.ipynb`).
- **Entidad**: se normaliza a los 32 nombres del GeoJSON; los registros sin
  entidad o en el extranjero (~6.6 %) van al bucket `Sin dato / Extranjero` y no
  aparecen en el mapa.
- **8 regiones geográficas**: Noroeste, Noreste, Occidente, Oriente, Centronorte,
  Centrosur, Suroeste, Sureste (reparto en `config.REGION_POR_ESTADO`).
