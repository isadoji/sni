"""Acceso a datos: carga el CSV tidy + el GeoJSON y aplica los filtros."""
from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import pandas as pd

from . import config
from .filters import FilterState


class SNIRepository:
    """Fuente única de datos de la app: catálogo de opciones + filtrado."""

    def __init__(self, frame: pd.DataFrame, geojson: dict):
        self.df = frame
        self.geojson = geojson

    # -- construcción --------------------------------------------------------
    @classmethod
    def from_files(cls, csv_path: Path = config.TIDY_CSV,
                   geojson_path: Path = config.GEOJSON) -> "SNIRepository":
        df = pd.read_csv(csv_path)
        df["AÑO"] = df["AÑO"].astype(int)
        geo = json.loads(Path(geojson_path).read_text())
        return cls(df, geo)

    # -- catálogos de opciones (para los widgets) --------------------------
    @cached_property
    def years(self) -> list[int]:
        return sorted(self.df["AÑO"].unique())

    @cached_property
    def areas(self) -> list[str]:
        return sorted(self.df["AREA"].unique())

    @cached_property
    def niveles(self) -> list[str]:
        presentes = set(self.df["NIVEL"])
        return [n for n in config.ORDEN_NIVELES if n in presentes]

    @cached_property
    def generos(self) -> list[str]:
        return sorted(self.df["GENERO"].unique())

    @cached_property
    def regiones(self) -> list[str]:
        presentes = set(self.df["REGION"])
        return [r for r in config.ORDEN_REGIONES if r in presentes]

    def estados(self, regiones: list[str] | None = None) -> list[str]:
        sub = self.df if not regiones else self.df[self.df["REGION"].isin(regiones)]
        return sorted(sub["ENTIDAD"].unique())

    # -- filtrado ----------------------------------------------------------
    def filter(self, f: FilterState) -> pd.DataFrame:
        y0, y1 = f.year_range
        m = (
            self.df["AÑO"].between(y0, y1)
            & self.df["AREA"].isin(f.areas)
            & self.df["NIVEL"].isin(f.niveles)
            & self.df["GENERO"].isin(f.generos)
            & self.df["REGION"].isin(f.regiones)
            & self.df["ENTIDAD"].isin(f.estados)
        )
        return self.df[m]
