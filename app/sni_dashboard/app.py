"""Composición: arma el repositorio, la barra lateral y la página."""
from __future__ import annotations

import streamlit as st

from . import config
from .charts import ChartBuilder
from .data import SNIRepository
from .filters import SidebarController


@st.cache_resource(show_spinner="Cargando padrón…")
def _load_repository() -> SNIRepository:
    return SNIRepository.from_files()


class Dashboard:
    """Punto de entrada de la app. Orquesta repo -> filtros -> figuras."""

    TITLE = "🔬 Padrón del Sistema Nacional de Investigadores"
    SUBTITLE = ("Serie histórica 2015-2025 · filtra por año, área, nivel, "
                "género, región y entidad")

    def __init__(self, repo: SNIRepository | None = None):
        self.repo = repo or _load_repository()

    # -- secciones --------------------------------------------------------
    def _header(self) -> None:
        st.title(self.TITLE)
        st.caption(self.SUBTITLE)

    def _kpis(self, charts: ChartBuilder) -> None:
        k = charts.metrics.kpis()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Investigadores", f"{k.total:,}")
        c2.metric("Mujeres", f"{k.mujeres:,}", f"{k.pct_mujeres:.1f}%")
        c3.metric("Hombres", f"{k.hombres:,}", f"{100 - k.pct_mujeres:.1f}%")
        c4.metric("Entidades con registro", k.entidades)

    def _mapa(self, charts: ChartBuilder) -> None:
        st.subheader("Mapa por entidad federativa")
        metrica = st.radio("Métrica", charts.METRICAS_MAPA, horizontal=True,
                           label_visibility="collapsed")
        st.plotly_chart(charts.mapa(metrica), use_container_width=True)
        k = charts.metrics.kpis()
        if k.sin_dato:
            pct = 100 * k.sin_dato / k.total if k.total else 0
            st.caption(f"{k.sin_dato:,} registros ({pct:.1f}%) sin entidad o en "
                       f"el extranjero — no se muestran en el mapa.")

    def _desgloses(self, charts: ChartBuilder) -> None:
        izq, der = st.columns(2)
        with izq:
            st.subheader("Evolución por año y género")
            st.plotly_chart(charts.serie_anual(), use_container_width=True)
            st.subheader("Por nivel")
            st.plotly_chart(charts.por_nivel(), use_container_width=True)
        with der:
            st.subheader("Por área de conocimiento")
            st.plotly_chart(charts.por_area(), use_container_width=True)
            st.subheader("Por región")
            st.plotly_chart(charts.por_region(), use_container_width=True)

    def _tabla(self, charts: ChartBuilder, dff) -> None:
        with st.expander("Ver / descargar datos filtrados"):
            st.dataframe(charts.tabla(), use_container_width=True, height=360)
            st.download_button("Descargar CSV",
                               dff.to_csv(index=False).encode("utf-8"),
                               "sni_filtrado.csv", "text/csv")

    # -- orquestación ----------------------------------------------------
    def run(self) -> None:
        st.set_page_config(page_title="Padrón SNI/SNII — explorador",
                           page_icon="🔬", layout="wide")
        self._header()

        state = SidebarController(self.repo).render()
        if state.is_empty:
            st.warning("Selecciona al menos una opción en cada filtro.")
            return

        dff = self.repo.filter(state)
        if dff.empty:
            st.warning("Ningún registro cumple los filtros seleccionados.")
            return

        charts = ChartBuilder(dff, self.repo.geojson)
        self._kpis(charts)
        self._mapa(charts)
        self._desgloses(charts)
        self._tabla(charts, dff)
