"""Estado de los filtros y el control de barra lateral que lo produce."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:                       # evita import circular en runtime
    from .data import SNIRepository


@dataclass(frozen=True)
class FilterState:
    """Selección del usuario. Inmutable: se recrea en cada rerun."""
    year_range: tuple[int, int]
    areas: list[str]
    niveles: list[str]
    generos: list[str]
    regiones: list[str]
    estados: list[str]

    @property
    def is_empty(self) -> bool:
        return not (self.areas and self.niveles and self.generos
                    and self.regiones and self.estados)


class SidebarController:
    """Dibuja la barra lateral y devuelve un ``FilterState``. Única responsabilidad."""

    def __init__(self, repo: "SNIRepository"):
        self.repo = repo

    @staticmethod
    def _multiselect(label: str, options: list, key: str,
                     default: list | None = None) -> list:
        return st.multiselect(label, options,
                              default=options if default is None else default,
                              key=key)

    def render(self) -> FilterState:
        st.sidebar.title("Filtros")
        years = self.repo.years
        year_range = st.sidebar.select_slider(
            "Año", options=years, value=(years[0], years[-1]))
        if isinstance(year_range, int):        # un solo año seleccionable
            year_range = (year_range, year_range)

        areas = self._multiselect("Área de conocimiento", self.repo.areas, "f_area")
        niveles = self._multiselect("Nivel", self.repo.niveles, "f_nivel")
        generos = self._multiselect("Género", self.repo.generos, "f_genero")
        regiones = self._multiselect(
            "Región (8 regiones geográficas)", self.repo.regiones, "f_region")

        estados_disp = self.repo.estados(regiones)
        estados = self._multiselect(
            "Entidad federativa", estados_disp, "f_estado", default=estados_disp)

        st.sidebar.caption(
            "Fuente: [Archivo histórico del SNII]"
            "(https://secihti.mx/snii/archivo-historico-del-snii/). "
            "2022 excluido (archivo oficial no utilizable). El género se infiere "
            "por nombre de pila; las áreas se homologan a 8 ejes comparables en "
            "toda la serie."
        )
        return FilterState(tuple(year_range), areas, niveles, generos,
                           regiones, estados)
