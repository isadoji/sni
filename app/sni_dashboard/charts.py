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
        # sin esto plotly ve "1","2","3" como números, hace el eje lineal y omite C y E
        fig.update_xaxes(type="category", categoryorder="array",
                         categoryarray=config.ORDEN_NIVELES)
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

    def pct_genero_por_estado(self) -> go.Figure:
        """% de mujeres y de hombres dentro del SNII de cada estado (suman 100 %), ordenado
        de mayor a menor % de mujeres. Al ser una proporción interna, compara la brecha entre
        estados sin importar su tamaño. Sin *Sin dato / Extranjero*."""
        d = self.dff[self.dff["ENTIDAD"] != config.SIN_DATO]
        t = d.groupby(["ENTIDAD", "GENERO"])["N"].sum().unstack(fill_value=0)
        t = t.reindex(columns=["MUJER", "HOMBRE"], fill_value=0)
        t = t[t.sum(axis=1) > 0]
        total = t.sum(axis=1)
        pct = t.div(total, axis=0) * 100
        orden = pct["MUJER"].sort_values(ascending=False).index.tolist()
        fig = go.Figure()
        for g in ["MUJER", "HOMBRE"]:
            fig.add_bar(y=orden, x=pct.loc[orden, g], orientation="h", name=g,
                        marker_color=self._COLOR[g], marker_line_width=0,
                        customdata=list(zip(t.loc[orden, g], total.loc[orden])),
                        hovertemplate="%{y}<br>" + g.capitalize() + "s: %{x:.1f} %"
                                      " (%{customdata[0]:,} de %{customdata[1]:,})<extra></extra>")
        fig.add_vline(x=50, line_dash="dash", line_color="gray")
        fig.update_layout(barmode="stack", height=22 * len(orden) + 80, margin=dict(t=10),
                          yaxis=dict(autorange="reversed"),
                          xaxis=dict(range=[0, 100], ticksuffix=" %",
                                     title="% del SNII del estado"),
                          legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0,
                                      traceorder="normal"))
        return fig

    def por_100mil_habitantes(self) -> go.Figure:
        """Investigadores del SNII (ambos sexos) por cada 100 000 habitantes del estado,
        de mayor a menor. Población de CONAPO del mismo año (``config.POBLACION_CSV``);
        con varios años es el promedio de las tasas anuales (no la suma de personas,
        que contaría a la misma persona una vez por año)."""
        d = self.dff[self.dff["ENTIDAD"] != config.SIN_DATO]
        n = d.groupby(["ENTIDAD", "AÑO"])["N"].sum().reset_index()
        pob = pd.read_csv(config.POBLACION_CSV)
        n = n.merge(pob, on=["ENTIDAD", "AÑO"], how="inner")
        n["TASA"] = n["N"] / n["POB"] * 1e5
        t = n.groupby("ENTIDAD").agg(TASA=("TASA", "mean"), N=("N", "mean"),
                                     POB=("POB", "mean")).sort_values("TASA", ascending=False)
        anios = sorted(n["AÑO"].unique())
        nota = (f"promedio anual {anios[0]}–{anios[-1]}" if len(anios) > 1 else str(anios[0]))
        fig = go.Figure(go.Bar(
            y=t.index, x=t["TASA"], orientation="h", marker_color="#4a6fa5",
            marker_line_width=0, customdata=list(zip(t["N"], t["POB"])),
            hovertemplate="%{y}: %{x:.1f} por 100 000 hab.<br>" + nota +
                          ": %{customdata[0]:,.0f} investigadores, "
                          "%{customdata[1]:,.0f} habitantes<extra></extra>"))
        fig.update_layout(height=22 * len(t) + 80, margin=dict(t=35),
                          yaxis=dict(autorange="reversed"),
                          xaxis=dict(title="Investigadores por 100 000 habitantes"))
        return fig

    def tabla(self) -> pd.DataFrame:
        return (self.dff.pivot_table(
            index=["AÑO", "ENTIDAD", "REGION", "AREA", "NIVEL"],
            columns="GENERO", values="N", aggfunc="sum", fill_value=0)
            .reset_index())
