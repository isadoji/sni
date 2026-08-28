"""Normalizadores: una clase por dimensión a homologar.

- ``GenderClassifier``  : nombre de pila            -> MUJER / HOMBRE / DESCONOCIDO
- ``AreaClassifier``    : área cruda (código/texto) -> 1 de las 8 áreas canónicas
- ``EntidadNormalizer`` : entidad federativa cruda  -> 1 de los 32 estados / "Sin dato"
- ``RegionMapper``      : estado canónico           -> 1 de las 8 regiones
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

from . import config


class GenderClassifier:
    """Infiere el género por el nombre de pila usando el catálogo de nombres de mujer."""

    def __init__(self, mujeres_csv: Path | str = config.MUJERES_CSV):
        serie = pd.read_csv(mujeres_csv)["nombre"].str.strip().str.lower()
        self._mujeres: set[str] = set(serie)

    def classify(self, nombre) -> str:
        if pd.isna(nombre):
            return "DESCONOCIDO"
        for parte in str(nombre).strip().lower().split():
            if parte in self._mujeres:
                return "MUJER"
        return "HOMBRE"

    def classify_series(self, s: pd.Series) -> pd.Series:
        return s.apply(self.classify)


class AreaClassifier:
    """Homologa la taxonomía de áreas (7 ejes hasta 2022, 9 desde 2023) a 8 ejes."""

    CANONICAS = config.AREAS_CANONICAS

    _POR_CODIGO = {
        "1": "FÍSICO-MATEMÁTICAS Y CIENCIAS DE LA TIERRA",
        "2": "BIOLOGÍA Y QUÍMICA",
        "3": "MEDICINA Y CIENCIAS DE LA SALUD",
        "4": "HUMANIDADES Y CIENCIAS DE LA CONDUCTA",
        "5": "CIENCIAS SOCIALES",
        "6": "BIOTECNOLOGÍA Y CIENCIAS AGROPECUARIAS",
        "7": "INGENIERÍAS",
    }
    _POR_TEXTO = [
        (("FÍSICO-MATEMÁTICAS", "FISICO-MATEMATICAS"),
         "FÍSICO-MATEMÁTICAS Y CIENCIAS DE LA TIERRA"),
        (("BIOLOGÍA Y QUÍMICA", "BIOLOGIA Y QUIMICA"), "BIOLOGÍA Y QUÍMICA"),
        (("MEDICINA",), "MEDICINA Y CIENCIAS DE LA SALUD"),
        (("HUMANIDADES", "CIENCIAS DE LA CONDUCTA"),
         "HUMANIDADES Y CIENCIAS DE LA CONDUCTA"),
        (("CIENCIAS SOCIALES",), "CIENCIAS SOCIALES"),
        (("BIOTECNOLOGÍA", "BIOTECNOLOGIA", "AGROPECUARIAS", "AGRICULTURA"),
         "BIOTECNOLOGÍA Y CIENCIAS AGROPECUARIAS"),
        (("INGENIERÍAS", "INGENIERIAS"), "INGENIERÍAS"),
        (("INTERDISCIPLINARIA",), "INTERDISCIPLINARIA"),
    ]

    def classify(self, valor) -> str | None:
        v = str(valor).strip().upper()
        codigo = v[:-2] if v.endswith(".0") else v
        if codigo in self._POR_CODIGO:
            return self._POR_CODIGO[codigo]
        for claves, canon in self._POR_TEXTO:
            if any(k in v for k in claves):
                return canon
        return None

    def classify_series(self, s: pd.Series) -> pd.Series:
        return s.apply(self.classify)


class EntidadNormalizer:
    """Lleva cualquier variante de nombre de entidad a los 32 nombres del GeoJSON."""

    SIN_DATO = config.SIN_DATO

    # el ORDEN importa: reglas más específicas primero (CDMX y BCS antes que MÉXICO/BC)
    _RULES: list[tuple[str, str]] = [
        ("DISTRITO FEDERAL", "Ciudad de México"),
        ("CIUDAD DE MEXICO", "Ciudad de México"),
        ("CDMX", "Ciudad de México"),
        ("BAJA CALIFORNIA SUR", "Baja California Sur"),
        ("BAJA CALIFORNIA", "Baja California"),
        ("AGUASCALIENTES", "Aguascalientes"),
        ("CAMPECHE", "Campeche"),
        ("CHIAPAS", "Chiapas"),
        ("CHIHUAHUA", "Chihuahua"),
        ("COAHUILA", "Coahuila"),
        ("COLIMA", "Colima"),
        ("DURANGO", "Durango"),
        ("GUANAJUATO", "Guanajuato"),
        ("GUERRERO", "Guerrero"),
        ("HIDALGO", "Hidalgo"),
        ("JALISCO", "Jalisco"),
        ("MICHOACAN", "Michoacán"),
        ("MORELOS", "Morelos"),
        ("NAYARIT", "Nayarit"),
        ("NUEVO LEON", "Nuevo León"),
        ("OAXACA", "Oaxaca"),
        ("PUEBLA", "Puebla"),
        ("QUERETARO", "Querétaro"),
        ("QUINTANA ROO", "Quintana Roo"),
        ("SAN LUIS POTOSI", "San Luis Potosí"),
        ("SINALOA", "Sinaloa"),
        ("SONORA", "Sonora"),
        ("TABASCO", "Tabasco"),
        ("TAMAULIPAS", "Tamaulipas"),
        ("TLAXCALA", "Tlaxcala"),
        ("VERACRUZ", "Veracruz"),
        ("YUCATAN", "Yucatán"),
        ("ZACATECAS", "Zacatecas"),
        ("ESTADO DE MEXICO", "México"),
        ("EDO DE MEXICO", "México"),
        ("MEXICO EDO", "México"),
        ("MEXICO DE", "México"),
        ("MEXICO", "México"),
    ]
    _SIN_DATO_KEYS = {
        "", "NAN", "NO DISPONIBLE", "ND", "SIN INSTITUCION", "SIN ENTIDAD",
        "SIN ENTIDAD DE ACREDITACION", "SIN ENTIDAD DE ADSCRIPCION",
        "EXTERIOR", "EXTRANJERO", "NO APLICA", "NA",
    }
    # mojibake cp437/latin1 visto en SNI2015.xlsx
    _MOJIBAKE = str.maketrans({"╔": "E", "╙": "O", "╤": "N", "╧": "I",
                               "┌": "U", "┴": "A"})

    @classmethod
    def _norm(cls, s: str) -> str:
        s = str(s).strip().upper().translate(cls._MOJIBAKE)
        s = "".join(c for c in unicodedata.normalize("NFD", s)
                    if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^A-Z ]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    def normalize(self, valor) -> str:
        n = self._norm(valor)
        if not n or n in self._SIN_DATO_KEYS:
            return self.SIN_DATO
        for pat, canon in self._RULES:
            if pat in n:
                return canon
        return self.SIN_DATO

    def normalize_series(self, s: pd.Series) -> pd.Series:
        return s.apply(self.normalize)


class RegionMapper:
    """Agrupa los 32 estados en 8 regiones geográficas."""

    POR_ESTADO = config.REGION_POR_ESTADO
    SIN_DATO = config.SIN_DATO

    def region_of(self, estado: str) -> str:
        return self.POR_ESTADO.get(estado, self.SIN_DATO)

    def map_series(self, s: pd.Series) -> pd.Series:
        return s.map(self.POR_ESTADO).fillna(self.SIN_DATO)
