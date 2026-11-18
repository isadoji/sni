"""ETL: de los padrones .xlsx al CSV "tidy".

- ``PadronReader``    : lee UN padrón anual y devuelve su tabla larga normalizada.
- ``DatasetBuilder``  : combina todos los años, resuelve el sexo (``SexoResolver``, que
                        necesita ver todos los años a la vez), agrega a conteos y guarda el CSV.

Las columnas de identidad (CVU, nombre) solo viven en memoria: el CSV es de conteos.

``generos_por_anio()`` expone el sexo resuelto por fila del padrón, para que los notebooks
(``sni_historico_genero.ipynb``, ``sni2025.ipynb``) usen exactamente la misma clasificación.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from . import config
from .config import YearConfig
from .normalize import (AreaClassifier, EntidadNormalizer, GenderClassifier, RegionMapper,
                        SexoResolver, sin_acentos)

COLS = ["AÑO", "AREA", "NIVEL", "GENERO", "ENTIDAD", "REGION"]
IDENT = ["cvu", "nombre", "pila", "sexo_titulo"]


class PadronReader:
    """Lee el padrón de un año y lo deja como tabla larga: una fila por investigador."""

    def __init__(
        self,
        datasets_dir: Path = config.DATASETS_DIR,
        *,
        gender: GenderClassifier | None = None,
        area: AreaClassifier | None = None,
        entidad: EntidadNormalizer | None = None,
        region: RegionMapper | None = None,
    ):
        self.datasets_dir = Path(datasets_dir)
        self.gender = gender or GenderClassifier()
        self.area = area or AreaClassifier()
        self.entidad = entidad or EntidadNormalizer()
        self.region = region or RegionMapper()

    def _nombre_pila(self, df: pd.DataFrame, cfg: YearConfig) -> pd.Series:
        col = df[cfg.name_col].astype(str)
        if cfg.modo == "apellidos_nombre":       # "APELLIDOS, NOMBRE" -> "NOMBRE"
            return col.apply(lambda x: x.split(",", 1)[1] if "," in x else x)
        return col

    def _nivel(self, df: pd.DataFrame, cfg: YearConfig) -> pd.Series:
        nivel = df[cfg.nivel_col].astype(str).str.strip().str.upper()
        if cfg.emerito_col:                       # 2023: Emérito en columna aparte
            es_em = df[cfg.emerito_col].astype(str).str.strip().str.upper() == "EMÉRITO"
            nivel = nivel.where(~es_em, "E")
        return nivel.where(nivel.isin(config.ORDEN_NIVELES))

    def _ident(self, df: pd.DataFrame, cfg: YearConfig) -> pd.DataFrame:
        """Columnas para resolver el sexo: CVU, nombre completo y de pila normalizados, título."""
        pila = self._nombre_pila(df, cfg).map(sin_acentos)
        if cfg.modo == "apellidos_nombre":
            completo = df[cfg.name_col].astype(str).str.replace(",", " ")
        else:
            completo = df[list(cfg.apellido_cols) + [cfg.name_col]].fillna("").astype(str).agg(" ".join, axis=1)
        cvu = (pd.to_numeric(df[cfg.cvu_col], errors="coerce").astype("Int64")
               if cfg.cvu_col else pd.Series(pd.NA, index=df.index, dtype="Int64"))
        tit = (SexoResolver.sexo_titulo(df[cfg.titulo_col]) if cfg.titulo_col
               else pd.Series(None, index=df.index, dtype=object))
        return pd.DataFrame({"cvu": cvu, "nombre": completo.map(sin_acentos).replace("", None),
                             "pila": pila.replace("", None), "sexo_titulo": tit})

    def read(self, cfg: YearConfig) -> pd.DataFrame:
        df = pd.read_excel(self.datasets_dir / cfg.file, skiprows=cfg.skiprows)
        entidad = self.entidad.normalize_series(df[cfg.estado_col])
        out = pd.DataFrame({
            "AÑO": cfg.year,
            "AREA": self.area.classify_series(df[cfg.area_col]),
            "NIVEL": self._nivel(df, cfg),
            "ENTIDAD": entidad,
            "REGION": self.region.map_series(entidad),
        })
        out["FILA"] = df.index                   # fila del .xlsx leído (con skiprows)
        return pd.concat([out, self._ident(df, cfg)], axis=1)


class DatasetBuilder:
    """Combina todos los años y agrega a ``AÑO×AREA×NIVEL×GENERO×ENTIDAD×REGION -> N``."""

    def __init__(self, reader: PadronReader | None = None,
                 year_configs: list[YearConfig] | None = None):
        self.reader = reader or PadronReader()
        self.year_configs = year_configs or config.YEAR_CONFIGS
        self._tidy: pd.DataFrame | None = None

    def build(self, verbose: bool = True) -> pd.DataFrame:
        partes = []
        for cfg in self.year_configs:
            if not (self.reader.datasets_dir / cfg.file).exists():
                print(f"  ! falta {cfg.file}; se omite {cfg.year}", file=sys.stderr)
                continue
            larga = self.reader.read(cfg)
            partes.append(larga)
            if verbose:
                print(f"  {cfg.year}: {len(larga):>6} registros")

        detalle = pd.concat(partes, ignore_index=True)
        resolver = SexoResolver(self.reader.gender).fit(detalle[IDENT])
        detalle["GENERO"], detalle["FUENTE_SEXO"] = resolver.resolve(detalle[IDENT])
        self.fuente_sexo = pd.crosstab(detalle["AÑO"], detalle["FUENTE_SEXO"])
        if verbose:
            print("\nFuente del sexo por año:\n" + self.fuente_sexo.to_string())
        self.sexo_por_fila = detalle[["AÑO", "FILA", "GENERO", "FUENTE_SEXO"]]
        detalle = detalle.drop(columns=IDENT + ["FILA", "FUENTE_SEXO"]).dropna(subset=["AREA", "NIVEL"])
        self._tidy = (detalle
                      .groupby(COLS, observed=True)
                      .size()
                      .reset_index(name="N")
                      .sort_values(COLS)
                      .reset_index(drop=True))
        return self._tidy

    @property
    def tidy(self) -> pd.DataFrame:
        if self._tidy is None:
            self.build()
        return self._tidy

    def save(self, path: Path = config.TIDY_CSV) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.tidy.to_csv(path, index=False)
        return path

    def report(self) -> str:
        t = self.tidy
        lineas = ["Total por año:",
                  t.groupby("AÑO")["N"].sum().to_string(),
                  "", "Total por entidad:",
                  t.groupby("ENTIDAD")["N"].sum()
                   .sort_values(ascending=False).to_string()]
        sin = t.loc[t["ENTIDAD"] == config.SIN_DATO, "N"].sum()
        lineas += ["", f"'{config.SIN_DATO}': {sin} ({100 * sin / t['N'].sum():.1f}%)"]
        return "\n".join(lineas)


def generos_por_anio(verbose: bool = False) -> dict[int, pd.Series]:
    """{año: Serie GENERO (MUJER/HOMBRE)} indexada por la fila de
    ``pd.read_excel(datasets/<cfg.file>, skiprows=cfg.skiprows)``. Lee todos los años
    porque el sexo de un año se apoya en el CVU y el nombre de los demás."""
    b = DatasetBuilder()
    b.build(verbose=verbose)
    return {a: g.set_index("FILA")["GENERO"] for a, g in b.sexo_por_fila.groupby("AÑO")}
