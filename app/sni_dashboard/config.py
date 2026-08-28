"""Rutas, catálogos y parámetros compartidos por el ETL y la app."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent          # .../sni/app
REPO_DIR = APP_DIR.parent                                  # .../sni
DATASETS_DIR = REPO_DIR / "datasets"                       # padrones .xlsx (solo ETL)
DATA_DIR = APP_DIR / "data"                                # artefactos de la app
TIDY_CSV = DATA_DIR / "sni_tidy.csv"
GEOJSON = DATA_DIR / "mexico_estados.geojson"
MUJERES_CSV = DATASETS_DIR / "mujeres.csv"

SIN_DATO = "Sin dato / Extranjero"
ORDEN_NIVELES = ["C", "1", "2", "3", "E"]

AREAS_CANONICAS = [
    "FÍSICO-MATEMÁTICAS Y CIENCIAS DE LA TIERRA",
    "BIOLOGÍA Y QUÍMICA",
    "MEDICINA Y CIENCIAS DE LA SALUD",
    "HUMANIDADES Y CIENCIAS DE LA CONDUCTA",
    "CIENCIAS SOCIALES",
    "BIOTECNOLOGÍA Y CIENCIAS AGROPECUARIAS",
    "INGENIERÍAS",
    "INTERDISCIPLINARIA",
]

# nombres canónicos = exactamente los "properties.name" del GeoJSON
ESTADOS_CANONICOS = [
    "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
    "Chiapas", "Chihuahua", "Ciudad de México", "Coahuila", "Colima", "Durango",
    "Guanajuato", "Guerrero", "Hidalgo", "Jalisco", "Michoacán", "Morelos",
    "México", "Nayarit", "Nuevo León", "Oaxaca", "Puebla", "Querétaro",
    "Quintana Roo", "San Luis Potosí", "Sinaloa", "Sonora", "Tabasco",
    "Tamaulipas", "Tlaxcala", "Veracruz", "Yucatán", "Zacatecas",
]

# --- 8 regiones geográficas de México ------------------------------------------
REGION_POR_ESTADO = {
    "Baja California": "Noroeste", "Baja California Sur": "Noroeste",
    "Chihuahua": "Noroeste", "Durango": "Noroeste", "Sinaloa": "Noroeste",
    "Sonora": "Noroeste",
    "Coahuila": "Noreste", "Nuevo León": "Noreste", "Tamaulipas": "Noreste",
    "Colima": "Occidente", "Jalisco": "Occidente", "Michoacán": "Occidente",
    "Nayarit": "Occidente",
    "Hidalgo": "Oriente", "Puebla": "Oriente", "Tlaxcala": "Oriente",
    "Veracruz": "Oriente",
    "Aguascalientes": "Centronorte", "Guanajuato": "Centronorte",
    "Querétaro": "Centronorte", "San Luis Potosí": "Centronorte",
    "Zacatecas": "Centronorte",
    "Ciudad de México": "Centrosur", "México": "Centrosur", "Morelos": "Centrosur",
    "Chiapas": "Suroeste", "Guerrero": "Suroeste", "Oaxaca": "Suroeste",
    "Campeche": "Sureste", "Quintana Roo": "Sureste", "Tabasco": "Sureste",
    "Yucatán": "Sureste",
}
ORDEN_REGIONES = ["Noroeste", "Noreste", "Occidente", "Oriente", "Centronorte",
                  "Centrosur", "Suroeste", "Sureste", SIN_DATO]

COLOR_GENERO = {"MUJER": "#2ca25f", "HOMBRE": "#8856a7"}


@dataclass(frozen=True)
class YearConfig:
    """Cómo leer el padrón de un año concreto."""
    year: int
    file: str
    skiprows: int
    name_col: str
    modo: str                       # 'dado' | 'apellidos_nombre'
    nivel_col: str
    area_col: str
    estado_col: str
    emerito_col: str | None = None

    @property
    def path_name(self) -> str:
        return self.file


# 2022 se excluye: el archivo oficial no es utilizable.
YEAR_CONFIGS: list[YearConfig] = [
    YearConfig(2015, "SNI2015.xlsx", 4, "NOMBRE", "dado", "NIVEL", "AREA", "ESTADO"),
    YearConfig(2016, "SNI2016.xlsx", 4, "NOMBRE", "dado", "NIVEL", "AREA", "ESTADO"),
    YearConfig(2017, "SNI2017.xlsx", 4, "NOMBRE", "dado", "NIVEL", "AREA", "ESTADO"),
    YearConfig(2018, "SNI2018.xlsx", 0, "NOMBRE", "dado", "NIVEL", "AREA", "ESTADO"),
    YearConfig(2019, "SNI2019.xlsx", 0, "NOMBRE", "dado", "NIVEL", "AREA", "ESTADO"),
    YearConfig(2020, "SNI2020.xlsx", 0, "Nombre del Investigador", "apellidos_nombre",
               "Categoría", "Área del Conocimiento", "Entidad Federativa"),
    YearConfig(2021, "SNI2021.xlsx", 0, "NOMBRE DEL INVESTIGADOR(A)", "apellidos_nombre",
               "CATEGORÍA", "ÁREA DEL CONOCIMIENTO", "ENTIDAD FEDERATIVA"),
    YearConfig(2023, "SNI2023_official.xlsx", 0, "NOMBRE DEL INVESTIGADOR",
               "apellidos_nombre", "NIVEL", "ÁREA DEL CONOCIMIENTO",
               "ENTIDAD FEDERATIVA DE ADSCRIPCIÓN", emerito_col="EMÉRITO"),
    YearConfig(2024, "SNI2024_official.xlsx", 0, "NOMBRE DEL INVESTIGADOR",
               "apellidos_nombre", "NIVEL", "ÁREA DE CONOCIMIENTO",
               "ENTIDAD DE ACREDITACIÓN"),
    YearConfig(2025, "SNI2025_CLASIFICADO.xlsx", 0, "NOMBRE DEL INVESTIGADOR",
               "apellidos_nombre", "NIVEL", "ÁREA DE CONOCIMIENTO",
               "ENTIDAD DE ACREDITACIÓN"),
]
