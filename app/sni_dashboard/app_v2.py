"""Versión 2 del explorador: el mapa es el selector de entidades.

- Barra lateral: solo Año y Género (sin Área, Nivel, Región ni Entidad).
- El mapa siempre muestra las 32 entidades con el mismo encuadre; seleccionar
  estados no lo reescala ni borra los demás.
- Sin selección: KPIs nacionales + las 4 gráficas (evolución, nivel, área, región).
- Con uno o más estados: KPIs de esa selección + evolución por área y por nivel.

La versión 1 sigue en ``app.py`` (``streamlit_app_v1.py``).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.colors as pc
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import config
from .app import Dashboard, _load_repository
from .charts import ChartBuilder
from .filters import FilterState

# Orden fijo de colores por entidad (área / nivel): el color sigue a la categoría,
# no a su posición, aunque cambie la selección.
_PALETA = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
           "#8c564b", "#e377c2", "#17becf"]


_METRICAS = ["Investigadores", "% mujeres", "% hombres"]
_ESCALA = {"Investigadores": "Blues", "% mujeres": "Greens", "% hombres": "Purples"}


class MapaSelector:
    """Mapa fijo de las 32 entidades que devuelve los estados seleccionados.

    Los estados se dibujan como polígonos en ejes cartesianos (lon, lat) y cada
    uno lleva un punto en su interior: la selección de Streamlit (clic, Shift+clic,
    recuadro, lazo) funciona sobre esos puntos. Un coroplético geo no emite
    selección en Streamlit, por eso no se usa aquí.
    """

    def __init__(self, repo, dff_base: pd.DataFrame):
        self.repo = repo
        self.charts = ChartBuilder(dff_base, repo.geojson)
        self.formas = self._formas(repo.geojson)

    @staticmethod
    @st.cache_data(show_spinner=False)
    def _formas_cache(geo_json: str) -> dict:
        import json
        out = {}
        for f in json.loads(geo_json)["features"]:
            geom = f["geometry"]
            polys = ([geom["coordinates"]] if geom["type"] == "Polygon"
                     else geom["coordinates"])
            xs, ys = [], []
            for poly in polys:
                anillo = poly[0]
                xs += [c[0] for c in anillo] + [None]
                ys += [c[1] for c in anillo] + [None]
            mayor = max(polys, key=lambda p: len(p[0]))[0]
            out[f["properties"]["name"]] = (xs, ys, _punto_interior(mayor))
        return out

    def _formas(self, geo: dict) -> dict:
        import json
        return self._formas_cache(json.dumps(geo))

    def figura(self, metrica: str, sel: list[str]) -> tuple[go.Figure, list[str]]:
        orden = list(self.formas)
        g = (self.charts.metrics.por_entidad().set_index("ENTIDAD")
             .reindex(orden).fillna(0))
        g["Hombres"] = g["Investigadores"] - g["Mujeres"]
        g["% hombres"] = (100 * g["Hombres"] / g["Investigadores"].where(
            g["Investigadores"] > 0)).round(1).fillna(0)
        escala = _ESCALA[metrica]
        v = g[metrica].astype(float)
        vmax = v.max() or 1.0
        colores = pc.sample_colorscale(escala, list((v / vmax).clip(0, 1) * 0.85 + 0.05))
        fig = go.Figure()
        # La selección vive en session_state y se dibuja con selectedpoints.
        for (xs, ys, _), color in zip(self.formas.values(), colores):
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode="lines", fill="toself", fillcolor=color,
                line=dict(color="#444", width=0.6),
                hoverinfo="skip", showlegend=False))
        cx = [self.formas[n][2][0] for n in orden]
        cy = [self.formas[n][2][1] for n in orden]
        custom = g[["Investigadores", "Mujeres", "% mujeres",
                    "Hombres", "% hombres"]].to_numpy()
        fig.add_trace(go.Scatter(
            x=cx, y=cy, mode="markers", text=orden, customdata=custom,
            name="entidades", showlegend=False,
            selectedpoints=[orden.index(n) for n in sel] if sel else None,
            marker=dict(size=13, color=v, colorscale=escala, cmin=0, cmax=vmax,
                        line=dict(color="white", width=1.5),
                        colorbar=dict(title=metrica, thickness=14)),
            selected=dict(marker=dict(color="#d62728", size=18)),
            unselected=dict(marker=dict(opacity=0.35)),
            hovertemplate=("<b>%{text}</b><br>Investigadores %{customdata[0]:,}"
                           "<br>Mujeres %{customdata[1]:,} (%{customdata[2]}%)"
                           "<br>Hombres %{customdata[3]:,} (%{customdata[4]}%)<extra></extra>")))
        # Encuadre fijo: ejes en grados, sin zoom; misma escala en x e y a ~23° N.
        # dragmode="pan" con ejes fijos: el mapa no se mueve y el clic selecciona
        # (con dragmode="select" un clic solo borra la selección).
        fig.update_xaxes(visible=False, range=[-118.6, -86.5], fixedrange=True)
        fig.update_yaxes(visible=False, range=[14.3, 33.0], fixedrange=True,
                         scaleanchor="x", scaleratio=1 / 0.92)
        fig.update_layout(height=560, margin=dict(l=0, r=0, t=10, b=0),
                          plot_bgcolor="rgba(0,0,0,0)", dragmode="pan",
                          clickmode="event+select", uirevision="mapa")
        return fig, orden

    def render(self) -> list[str]:
        metrica = st.radio("Métrica", _METRICAS, horizontal=True,
                           label_visibility="collapsed")
        actual = st.session_state.setdefault("_sel_estados", [])
        fig, orden = self.figura(metrica, actual)
        # Cambiar la key es la única forma de borrar la selección de un plotly_chart.
        ver = st.session_state.setdefault("_mapa_ver", 0)
        ev = st.plotly_chart(fig, use_container_width=True, key=f"mapa_sel_{ver}",
                             on_select="rerun",
                             selection_mode=("points", "box", "lasso"),
                             config={"displaylogo": False,
                                     "modeBarButtonsToRemove": ["zoom2d", "pan2d",
                                         "zoomIn2d", "zoomOut2d", "autoScale2d",
                                         "resetScale2d"]})
        sel = []
        for p in (ev.selection.get("points", []) if ev else []):
            idx = p.get("point_index", p.get("point_number"))
            if p.get("curve_number") == len(fig.data) - 1 and idx is not None:
                n = orden[idx]
                if n not in sel:
                    sel.append(n)
        # La selección la lleva la app, no plotly: cada evento suma sus estados (un
        # clic sobre un estado ya elegido lo quita) y se cambia la key para que el
        # siguiente evento llegue limpio. Los eventos vacíos (al redibujar por año o
        # métrica) se ignoran.
        if sel:
            if len(sel) == 1 and sel[0] in actual:
                nuevo = [n for n in actual if n != sel[0]]
            else:
                nuevo = actual + [n for n in sel if n not in actual]
            st.session_state["_sel_estados"] = nuevo
            st.session_state["_mapa_ver"] = ver + 1
            st.rerun()
        sel = actual
        info, boton = st.columns([5, 1], vertical_alignment="center")
        if sel:
            info.markdown("**Selección:** " + ", ".join(sel))
            if boton.button("Ver todo el país", use_container_width=True):
                st.session_state["_mapa_ver"] = ver + 1
                st.session_state["_sel_estados"] = []
                st.rerun()
        else:
            info.caption("Clic en el punto de un estado para agregarlo (otro clic lo "
                         "quita); también recuadro o lazo (barra del mapa).")
        return sel


def _punto_interior(anillo: list) -> tuple[float, float]:
    """Punto dentro del polígono: centroide de área; si cae fuera, el punto medio
    del segmento horizontal más largo que cruza el polígono a esa latitud."""
    xs = [c[0] for c in anillo]; ys = [c[1] for c in anillo]
    a = cx = cy = 0.0
    for i in range(len(anillo) - 1):
        cr = xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
        a += cr; cx += (xs[i] + xs[i + 1]) * cr; cy += (ys[i] + ys[i + 1]) * cr
    if a == 0:
        return sum(xs) / len(xs), sum(ys) / len(ys)
    cx /= 3 * a; cy /= 3 * a
    cortes = sorted(xs[i] + (cy - ys[i]) * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i])
                    for i in range(len(anillo) - 1)
                    if (ys[i] <= cy < ys[i + 1]) or (ys[i + 1] <= cy < ys[i]))
    tramos = list(zip(cortes[::2], cortes[1::2]))
    if not tramos or any(x0 <= cx <= x1 for x0, x1 in tramos):
        return cx, cy
    x0, x1 = max(tramos, key=lambda t: t[1] - t[0])
    return (x0 + x1) / 2, cy


ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO, ICONO = ASSETS / "logo.png", ASSETS / "icono.png"


class DashboardV2(Dashboard):
    TITLE = "Padrón del Sistema Nacional de Investigadoras e Investigadores"
    SUBTITLE = ("Serie histórica 2015-2025 · selecciona uno o varios estados en el "
                "mapa para ver su evolución por área y por nivel")

    def _header(self) -> None:
        st.logo(str(LOGO), icon_image=str(ICONO), size="large")
        izq, der = st.columns([1, 3], vertical_alignment="center")
        izq.image(str(LOGO), use_container_width=True)
        der.title(self.TITLE)
        der.caption(self.SUBTITLE)

    TODOS = "2015–2025"

    def _anio(self) -> int | None:
        """Botones de año sobre el mapa (como en el portafolio). None = toda la serie."""
        years = list(self.repo.years)
        v = st.segmented_control("Año", options=[self.TODOS, *years],
                                 default=self.TODOS, key="anio_mapa",
                                 label_visibility="collapsed")
        return None if v in (None, self.TODOS) else int(v)

    def _sidebar(self) -> None:
        st.sidebar.caption(
            "Fuente: [Archivo histórico del SNII]"
            "(https://secihti.mx/snii/archivo-historico-del-snii/). "
            "2022 excluido (archivo oficial no utilizable). Género por título, CVU "
            "y nombre en otros años; áreas homologadas a 8 ejes comparables.")

    def _estado(self, yr, generos, estados) -> FilterState:
        r = self.repo
        return FilterState(yr, r.areas, r.niveles, generos, r.regiones,
                           estados or r.estados())

    @staticmethod
    def _evolucion(dff: pd.DataFrame, col: str, orden: list[str],
                   titulo_col: str) -> go.Figure:
        d = dff.groupby(["AÑO", col, "GENERO"])["N"].sum().reset_index()
        d["GENERO"] = d["GENERO"].map({"MUJER": "Mujeres", "HOMBRE": "Hombres"})
        fig = px.line(d, x="AÑO", y="N", color=col, facet_col="GENERO",
                      markers=True,
                      category_orders={col: orden, "GENERO": ["Mujeres", "Hombres"]},
                      color_discrete_sequence=_PALETA,
                      labels={"N": "Investigadores", col: titulo_col, "AÑO": "Año"})
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.update_layout(height=430, margin=dict(t=30),
                          legend=dict(orientation="h", y=-0.2))
        return fig

    def _spiders(self, sel: list[str], anio_mapa: int | None,
                 generos: list[str]) -> None:
        """Telarañas nivel × área × género, una fila por estado seleccionado.

        La escala radial de cada nivel es fija dentro de cada estado: el máximo de
        todos los años, áreas y géneros de ese estado, para que al cambiar de año
        se vea el crecimiento (igual que en el dashboard del portafolio).
        """
        st.subheader("Spider web: nivel × área × género")
        anios = list(self.repo.years)
        inicial = anio_mapa or anios[-1]
        # la clave depende del año del mapa: al cambiarlo, el spider lo sigue
        anio = st.segmented_control("Año del spider web", options=anios,
                                    default=inicial, key=f"anio_spider_{anio_mapa}",
                                    label_visibility="collapsed")
        if anio is None:  # se des-seleccionó el botón activo
            anio = inicial
        st.caption("Investigadores por área de conocimiento y género en cada nivel. "
                   "La escala de cada nivel es la misma en todos los años para ese "
                   "estado. *Interdisciplinaria* vale 0 antes de 2023 (no existía).")
        df = self.repo.df
        sub = df[df["ENTIDAD"].isin(sel) & df["GENERO"].isin(generos)]
        areas = [a for a in _ORDEN_SPIDER if a in self.repo.areas]
        niveles = self.repo.niveles
        for estado in sel:
            d = sub[sub["ENTIDAD"] == estado]
            t = d.groupby(["AÑO", "NIVEL", "AREA", "GENERO"])["N"].sum()
            tope = t.groupby(level="NIVEL").max()
            st.plotly_chart(_figura_spider(t, anio, areas, niveles, generos, tope,
                                           estado),
                            use_container_width=True, key=f"spider_{estado}")

    def run(self) -> None:
        st.set_page_config(page_title="SNI Explorer · padrón SNI/SNII",
                           page_icon=str(ICONO), layout="wide")
        self._header()
        self._sidebar()
        generos = list(self.repo.generos)
        kpi_slot = st.container()
        st.subheader("Mapa por entidad federativa")
        anio_mapa = self._anio()
        years = self.repo.years
        yr = (anio_mapa, anio_mapa) if anio_mapa else (years[0], years[-1])

        base = self.repo.filter(self._estado(yr, generos, None))
        sel = MapaSelector(self.repo, base).render()

        dff = self.repo.filter(self._estado(yr, generos, sel)) if sel else base
        charts = ChartBuilder(dff, self.repo.geojson)
        with kpi_slot:
            self._kpis(charts)

        if not sel:
            k = charts.metrics.kpis()
            if k.sin_dato:
                st.caption(f"{k.sin_dato:,} registros ({100 * k.sin_dato / k.total:.1f}%) "
                           "sin entidad o en el extranjero: no se muestran en el mapa.")
            self._desgloses(charts)
        else:
            self._spiders(sel, anio_mapa, generos)
            with st.expander("Evolución por área y por nivel (series anuales)"):
                st.plotly_chart(self._evolucion(dff, "AREA", sorted(self.repo.areas),
                                                "Área"), use_container_width=True)
                st.plotly_chart(self._evolucion(dff, "NIVEL", self.repo.niveles,
                                                "Nivel"), use_container_width=True)
        self._tabla(charts, dff)


# Mismo orden de ejes que el spider web del portafolio (sni-dashboard.html).
_ORDEN_SPIDER = [
    "FÍSICO-MATEMÁTICAS Y CIENCIAS DE LA TIERRA", "BIOLOGÍA Y QUÍMICA",
    "MEDICINA Y CIENCIAS DE LA SALUD", "HUMANIDADES Y CIENCIAS DE LA CONDUCTA",
    "CIENCIAS SOCIALES", "BIOTECNOLOGÍA Y CIENCIAS AGROPECUARIAS", "INGENIERÍAS",
    "INTERDISCIPLINARIA",
]

_CORTO = {
    "BIOLOGÍA Y QUÍMICA": "Biología y Química",
    "BIOTECNOLOGÍA Y CIENCIAS AGROPECUARIAS": "Biotec. y Agropec.",
    "CIENCIAS SOCIALES": "C. Sociales",
    "FÍSICO-MATEMÁTICAS Y CIENCIAS DE LA TIERRA": "Físico-Mat.",
    "HUMANIDADES Y CIENCIAS DE LA CONDUCTA": "Human. y C. Conducta",
    "INGENIERÍAS": "Ingenierías",
    "INTERDISCIPLINARIA": "Interdisciplinaria",
    "MEDICINA Y CIENCIAS DE LA SALUD": "Medicina",
}


def _figura_spider(t: pd.Series, anio: int, areas: list[str], niveles: list[str],
                   generos: list[str], tope: pd.Series, estado: str) -> go.Figure:
    from plotly.subplots import make_subplots
    ncol = 3
    nfil = -(-len(niveles) // ncol)
    specs = [[{"type": "polar"} if f * ncol + c < len(niveles) else None
              for c in range(ncol)] for f in range(nfil)]
    fig = make_subplots(rows=nfil, cols=ncol, specs=specs,
                        subplot_titles=[f"Nivel {n}" for n in niveles],
                        horizontal_spacing=0.16, vertical_spacing=0.16)
    pos = {j: divmod(j - 1, ncol) for j in range(1, len(niveles) + 1)}
    etiquetas = [_CORTO.get(a, a.title()) for a in areas]
    for j, nivel in enumerate(niveles, start=1):
        for genero, nombre in (("HOMBRE", "Hombres"), ("MUJER", "Mujeres")):
            if genero not in generos:
                continue
            try:
                v = t.loc[(anio, nivel)].xs(genero, level="GENERO")
            except KeyError:
                v = pd.Series(dtype=float)
            r = [float(v.get(a, 0)) for a in areas]
            color = config.COLOR_GENERO[genero]
            fig.add_trace(go.Scatterpolar(
                r=r + r[:1], theta=etiquetas + etiquetas[:1], name=nombre,
                legendgroup=genero, showlegend=(j == 1), mode="lines+markers",
                line=dict(color=color, width=2), marker=dict(size=5),
                fill="toself", fillcolor=_rgba(color, 0.15),
                hovertemplate=f"{nombre}<br>%{{theta}}: %{{r:,.0f}}<extra>Nivel {nivel}</extra>"),
                row=pos[j][0] + 1, col=pos[j][1] + 1)
        mx = float(tope.get(nivel, 0)) or 1.0
        fig.update_polars(dict(radialaxis=dict(range=[0, mx * 1.05], tickfont=dict(size=8),
                                               ),
                               angularaxis=dict(tickfont=dict(size=10))),
                          row=pos[j][0] + 1, col=pos[j][1] + 1)
    fig.update_layout(title=dict(text=f"{estado} · {anio}", x=0, font=dict(size=15)),
                      height=330 * nfil + 60, margin=dict(l=70, r=70, t=80, b=30),
                      legend=dict(x=0.84, y=0.25, xanchor="center", yanchor="middle",
                                  font=dict(size=13)))
    fig.update_annotations(font_size=12, yshift=18)
    return fig


def _rgba(hex_color: str, a: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"
