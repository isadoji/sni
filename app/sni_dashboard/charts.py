"""Cálculo de indicadores y construcción de figuras a partir del frame filtrado."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from . import config

_METRICAS_MAPA = ["Investigadores", "% mujeres", "% del total nacional"]


@dataclass
class Kpis:
    total: int
    mujeres: int
    hombres: int
    pct_mujeres: float
    entidades: int
    sin_dato: int


class Metrics:
    """Calcula los indicadores agregados. Solo números, nada de presentación."""

    def __init__(self, dff: pd.DataFrame):
        self.dff = dff

    def kpis(self) -> Kpis:
        total = int(self.dff["N"].sum())
        mujeres = int(self.dff.loc[self.dff["GENERO"] == "MUJER", "N"].sum())
        con_estado = self.dff[self.dff["ENTIDAD"] != config.SIN_DATO]
        return Kpis(
            total=total,
            mujeres=mujeres,
            hombres=total - mujeres,
            pct_mujeres=100 * mujeres / total if total else 0.0,
            entidades=con_estado["ENTIDAD"].nunique(),
            sin_dato=int(self.dff.loc[self.dff["ENTIDAD"] == config.SIN_DATO, "N"].sum()),
        )

    def por_entidad(self) -> pd.DataFrame:
        base = self.dff[self.dff["ENTIDAD"] != config.SIN_DATO]
        g = base.groupby("ENTIDAD").apply(
            lambda d: pd.Series({
                "Investigadores": int(d["N"].sum()),
                "Mujeres": int(d.loc[d["GENERO"] == "MUJER", "N"].sum()),
            }), include_groups=False).reset_index()
        g["% mujeres"] = (100 * g["Mujeres"] / g["Investigadores"]).round(1)
        tot = g["Investigadores"].sum()
        g["% del total nacional"] = (100 * g["Investigadores"] / tot).round(2) if tot else 0
        return g


class ChartBuilder:
    """Construye las figuras Plotly. Una función pública por gráfico."""

    METRICAS_MAPA = _METRICAS_MAPA
    _COLOR = config.COLOR_GENERO

    def __init__(self, dff: pd.DataFrame, geojson: dict):
        self.dff = dff
        self.geojson = geojson
        self.metrics = Metrics(dff)

    def mapa(self, metrica: str = "Investigadores") -> go.Figure:
        g = self.metrics.por_entidad()
        escala = "Greens" if metrica == "% mujeres" else "Blues"
        fig = px.choropleth(
            g, geojson=self.geojson, locations="ENTIDAD",
            featureidkey="properties.name", color=metrica,
            color_continuous_scale=escala,
            hover_data=["Investigadores", "Mujeres", "% mujeres",
                        "% del total nacional"],
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=520)
        return fig

    def serie_anual(self) -> go.Figure:
        s = self.dff.groupby(["AÑO", "GENERO"])["N"].sum().reset_index()
        fig = px.line(s, x="AÑO", y="N", color="GENERO", markers=True,
                      color_discrete_map=self._COLOR, labels={"N": "Investigadores"})
        fig.update_layout(height=380, margin=dict(t=10))
        return fig

    def por_nivel(self) -> go.Figure:
        d = self.dff.groupby(["NIVEL", "GENERO"])["N"].sum().reset_index()
        d["NIVEL"] = pd.Categorical(d["NIVEL"], config.ORDEN_NIVELES, ordered=True)
        fig = px.bar(d.sort_values("NIVEL"), x="NIVEL", y="N", color="GENERO",
                     barmode="group", color_discrete_map=self._COLOR,
                     labels={"N": "Investigadores"})
        fig.update_layout(height=340, margin=dict(t=10))
        return fig

    def por_area(self) -> go.Figure:
        d = self.dff.groupby(["AREA", "GENERO"])["N"].sum().reset_index()
        orden = d.groupby("AREA")["N"].sum().sort_values().index.tolist()
        fig = px.bar(d, x="N", y="AREA", color="GENERO", orientation="h",
                     barmode="stack", color_discrete_map=self._COLOR,
                     category_orders={"AREA": orden},
                     labels={"N": "Investigadores", "AREA": ""})
        fig.update_layout(height=380, margin=dict(t=10))
        return fig

    def por_region(self) -> go.Figure:
        d = self.dff.groupby(["REGION", "GENERO"])["N"].sum().reset_index()
        d["REGION"] = pd.Categorical(d["REGION"], config.ORDEN_REGIONES, ordered=True)
        fig = px.bar(d.sort_values("REGION"), x="N", y="REGION", color="GENERO",
                     orientation="h", barmode="stack", color_discrete_map=self._COLOR,
                     labels={"N": "Investigadores", "REGION": ""})
        fig.update_layout(height=340, margin=dict(t=10))
        return fig

    def tabla(self) -> pd.DataFrame:
        return (self.dff.pivot_table(
            index=["AÑO", "ENTIDAD", "REGION", "AREA", "NIVEL"],
            columns="GENERO", values="N", aggfunc="sum", fill_value=0)
            .reset_index())
