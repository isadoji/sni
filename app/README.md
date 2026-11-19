# Explorador interactivo del padrón SNI/SNII

App de [Streamlit](https://streamlit.io) sobre la serie histórica 2015-2025.

## Versiones

- **Versión 2 (la que corre en Render desde 2026-11-18)**, `streamlit_app.py` →
  `sni_dashboard/app_v2.py`. Sin filtros en la barra lateral (solo la fuente):
  el año se elige con **botones sobre el mapa** (*2015–2025* = toda la serie, o un
  año), siempre con ambos géneros. El **mapa es el selector de entidades**: siempre
  muestra las 32 entidades con el mismo encuadre. Métricas del mapa: investigadores,
  % mujeres, % hombres, con **escala de color fija en los años individuales**
  para que se vea el cambio: investigadores de 0 a 3 000 (máximo de los estados sin
  la Ciudad de México, Jalisco 2 756, redondeado a 500; la CDMX, hasta 14 312, queda
  en el color más oscuro, «3,000+»); % mujeres 25–46.3 y % hombres 50–74.1 (mínimo
  redondeado a 5 y máximo de los estados en todos los años individuales). En
  *2015–2025* (suma de todos los años) la escala va de 0 al máximo de esa vista. Clic en el punto de un estado lo agrega y otro clic lo quita;
  recuadro o lazo agregan varios; el botón *Ver todo el país* borra la selección. La
  selección se conserva al cambiar de año o de métrica.
  - Sin selección: KPIs nacionales y las gráficas de evolución por año y género,
    nivel y área, y abajo, a todo lo ancho, **% de mujeres y de hombres por estado**
    (proporción dentro del SNII de cada estado, suman 100 %, ordenada de mayor a menor
    % de mujeres, línea en 50 %; el tooltip da los conteos). Compara la brecha sin
    importar el tamaño del estado; en *2015–2025* es la proporción de la suma. Sin
    *Sin dato / Extranjero*. La v1 conserva la gráfica por región.
  - Con uno o más estados: KPIs de la selección y, por cada estado, un spider web
    nivel × área × género (como el de la página principal del portafolio: mismo
    orden de ejes y etiquetas), en paneles 3 × 2, del año elegido con los botones
    sobre el mapa (una sola selección de año para toda la página). En los años
    individuales la escala radial de cada nivel es fija en todos los años para ese
    estado; en *2015–2025* se suman todos los años con su propia escala. La
    evolución anual por área y por nivel queda en un desplegable.
  - Barra lateral: fuente de datos y, debajo, autoras (Isabel Domínguez Jiménez,
    María Elena Tejeda Yeomans), enlace al código y cómo citar.
  - Logo *SNII Explorer* en `assets/logo.png` e `assets/icono.png` (favicon y
    barra lateral).
  - El mapa son polígonos en ejes cartesianos (lon, lat) con un punto por estado,
    no un coroplético geo: en Streamlit un coroplético geo no emite selección. La
    selección la guarda la app en `session_state` (no plotly): cada evento suma o
    quita estados, la figura los dibuja con `selectedpoints` y la key del widget
    cambia para que el siguiente evento llegue limpio (al redibujar, plotly olvida
    su propia selección y Shift+clic ya no suma). Usa `dragmode="pan"` con ejes
    fijos (con `dragmode="select"` un clic borra la selección en vez de seleccionar).
- **Versión 1 (respaldo)**, `streamlit_app_v1.py` → `sni_dashboard/app.py`: barra
  con filtros por año, área, nivel, género, región y entidad, mapa coroplético y
  desgloses. Tag git `app-v1`. Para volver a ella en Render, cambiar el start
  command a `streamlit run streamlit_app_v1.py ...` o copiar ese archivo sobre
  `streamlit_app.py`.

## Estructura (un módulo = una responsabilidad)

```
app/
├── streamlit_app.py          # entrada v2: DashboardV2().run()
├── streamlit_app_v1.py       # entrada v1 (respaldo): Dashboard().run()
├── assets/                   # logo.png, icono.png (SNI Explorer)
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
    ├── app.py                # v1 Dashboard: compone repo -> filtros -> figuras
    └── app_v2.py             # v2 DashboardV2 + MapaSelector (mapa como selector)
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
streamlit run streamlit_app.py        # v2
streamlit run streamlit_app_v1.py     # v1 (respaldo)
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

- **2022** (incluido desde 2026-11-19): `SNI2022.xlsx` tiene tres hojas; `Hoja1` y
  `Hoja2` son una tabla dinámica de una sola institución (CICESE, ~257 registros) y el
  padrón nacional completo (36 624 registros) está en la hoja `2022`
  (`YearConfig.sheet`). Antes solo se leía la primera hoja y 2022 se excluía por error.
  No trae título: el sexo sale del CVU en otros años (98.7 %). El nivel viene como texto
  largo (*Investigador(a) Nacional Nivel I*, *Candidato(a)…*) y los eméritos como `EM`
  en la columna `EMÉRITO` (nivel E, igual que 2023). Ya usa las 9 áreas nuevas.
  Agregarlo no cambió ningún conteo de los demás años.
- El **género** (2026-11-18) lo asigna `SexoResolver` (`normalize.py`) en este orden:
  1. el título del registro (DR./DRA., MTRO./MTRA.; columna NOBILIS o GRADO ACADÉMICO, ~98 % de 2015–2021 y 2023);
  2. el mismo CVU con título en otro año (2019, 2021, 2023);
  3. el mismo nombre completo con título en otro año, si siempre tiene el mismo sexo;
  4. el nombre de pila visto con título ≥5 veces y ≥95 % con un sexo;
  5. el catálogo `datasets/mujeres.csv`, solo como último recurso (~2 % de 2024 y 2025).

  2022, 2024 y 2025 no traen título; se resuelven sobre todo por CVU. Validado ocultando el
  título de 2023: acierto 99.1 %, % de mujeres 39.31 contra 39.30 real. El catálogo
  solo, usado hasta esta fecha, clasificaba como mujer al 12.3 % de los hombres
  (contiene «juan» y «jesus»; bastaba una palabra del nombre en la lista) y sobrestimaba
  a las mujeres ~6 pp en todos los años (2025: 46.4 % → 40.6 %). La columna GENERO de
  `SNI2025_CLASIFICADO.xlsx` no se usa.
- La **taxonomía de áreas** cambió de 7 a 9 ejes en 2022; se homologa a 8 ejes
  comparables en toda la serie (misma lógica que `sni_historico_genero.ipynb`).
- **Entidad**: se normaliza a los 32 nombres del GeoJSON; los registros sin
  entidad o en el extranjero (~6.6 %) van al bucket `Sin dato / Extranjero` y no
  aparecen en el mapa.
- **8 regiones geográficas**: Noroeste, Noreste, Occidente, Oriente, Centronorte,
  Centrosur, Suroeste, Sureste (reparto en `config.REGION_POR_ESTADO`).
