"""Normalizadores: una clase por dimensión a homologar.

- ``GenderClassifier``  : nombre de pila            -> MUJER / HOMBRE / DESCONOCIDO
                         (solo respaldo: clasifica como hombre todo nombre que no conoce)
- ``SexoResolver``      : título, CVU y nombre      -> MUJER / HOMBRE, con su fuente
- ``AreaClassifier``    : área cruda (código/texto) -> 1 de las 8 áreas canónicas
- ``EntidadNormalizer`` : entidad federativa cruda  -> 1 de los 32 estados / "Sin dato"
- ``RegionMapper``      : estado canónico           -> 1 de las 8 regiones
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
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


def sin_acentos(x: str) -> str:
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^A-Z ]", " ", x.upper()).split())


class SexoResolver:
    """Asigna el sexo con la fuente más directa disponible, en este orden:

    1. ``titulo``: el título del propio registro tiene género (DR./DRA., MTRO./MTRA.).
    2. ``cvu``: el mismo CVU aparece con título con género en otro año (2019, 2021, 2023).
    3. ``nombre``: el mismo nombre completo aparece con título con género en otro año, con un
       solo sexo (los nombres con ambos sexos se descartan).
    4. ``pila_titulos``: el nombre de pila (completo, luego el primero) aparece con título con
       género al menos ``MIN_N`` veces en el padrón y ≥ ``UMBRAL`` de las veces con el mismo sexo.
    5. ``diccionario``: ``GenderClassifier`` (catálogo de nombres de mujer). Último recurso.

    El diccionario solo clasifica como hombre al 16.5 % de las mujeres (validado contra el
    título en 2023); por eso va al final.
    """

    TITULOS = {"DR.": "HOMBRE", "DR": "HOMBRE", "MTRO.": "HOMBRE", "MTRO": "HOMBRE",
               "DRA.": "MUJER", "DRA": "MUJER", "DRA,": "MUJER", "MTRA.": "MUJER", "MTRA": "MUJER"}
    MIN_N, UMBRAL = 5, 0.95

    def __init__(self, fallback: GenderClassifier | None = None):
        self.fallback = fallback or GenderClassifier()
        self.por_cvu: dict = {}
        self.por_nombre: dict = {}
        self.por_pila: dict = {}

    @classmethod
    def sexo_titulo(cls, s: pd.Series) -> pd.Series:
        return s.astype(str).str.strip().str.upper().map(cls.TITULOS)

    @staticmethod
    def _unico(df: pd.DataFrame, llave: str) -> dict:
        g = df.dropna(subset=[llave]).groupby(llave)["sexo_titulo"].agg(["nunique", "first"])
        return g.loc[g["nunique"] == 1, "first"].to_dict()

    def fit(self, ident: pd.DataFrame) -> "SexoResolver":
        """``ident``: columnas cvu, nombre (completo normalizado), pila, sexo_titulo."""
        t = ident.dropna(subset=["sexo_titulo"])
        self.por_cvu = self._unico(t, "cvu")
        self.por_nombre = self._unico(t, "nombre")
        pilas = pd.concat([t[["pila", "sexo_titulo"]],
                           t.assign(pila=t["pila"].str.split().str[0])[["pila", "sexo_titulo"]]])
        c = pilas.dropna().groupby("pila")["sexo_titulo"].value_counts().unstack(fill_value=0)
        n = c.sum(axis=1)
        top = c.idxmax(axis=1)
        ok = (n >= self.MIN_N) & (c.max(axis=1) / n >= self.UMBRAL)
        self.por_pila = top[ok].to_dict()
        return self

    def resolve(self, ident: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        sexo = ident["sexo_titulo"].copy()
        fuente = pd.Series(np.where(sexo.notna(), "titulo", None), index=ident.index, dtype=object)
        pasos = [("cvu", ident["cvu"].map(self.por_cvu)),
                 ("nombre", ident["nombre"].map(self.por_nombre)),
                 ("pila_titulos", ident["pila"].map(self.por_pila)
                  .fillna(ident["pila"].str.split().str[0].map(self.por_pila)))]
        for nom, cand in pasos:
            usar = sexo.isna() & cand.notna()
            sexo[usar], fuente[usar] = cand[usar], nom
        resto = sexo.isna()
        sexo[resto] = self.fallback.classify_series(ident.loc[resto, "pila"])
        fuente[resto] = "diccionario"
        return sexo, fuente


class AreaClassifier:
    """Homologa la taxonomía de áreas (7 ejes hasta 2021, 9 desde 2022) a 8 ejes."""

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
