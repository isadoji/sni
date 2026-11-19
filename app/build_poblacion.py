"""Población por entidad y año (2015–2025) desde las proyecciones municipales de CONAPO.

Entrada: ../datasets/pobproy_quinq1.csv (CONAPO; municipio × sexo × año, 1990–2040).
Salida:  data/poblacion_entidad.csv (ENTIDAD, AÑO, POB), suma de municipios y de ambos
sexos, con los nombres de entidad del GeoJSON. Uso: python build_poblacion.py
"""
from __future__ import annotations

import sys

import pandas as pd

from sni_dashboard import config

FUENTE = config.APP_DIR.parent / "datasets" / "pobproy_quinq1.csv"
SALIDA = config.DATA_DIR / "poblacion_entidad.csv"
NOMBRES = {"Coahuila de Zaragoza": "Coahuila", "Michoacán de Ocampo": "Michoacán",
           "Veracruz de Ignacio de la Llave": "Veracruz"}


def main() -> int:
    d = pd.read_csv(FUENTE, usecols=["NOM_ENT", "ANO", "POB_TOTAL"])
    d = d[d["ANO"].between(2015, 2025)]
    d["ENTIDAD"] = d["NOM_ENT"].replace(NOMBRES)
    out = (d.groupby(["ENTIDAD", "ANO"])["POB_TOTAL"].sum().reset_index()
           .rename(columns={"ANO": "AÑO", "POB_TOTAL": "POB"}))
    falta = set(out["ENTIDAD"]) ^ (set(pd.read_csv(config.TIDY_CSV)["ENTIDAD"]) - {config.SIN_DATO})
    if falta:
        print("Nombres que no coinciden:", sorted(falta)); return 1
    if out.groupby("AÑO").size().ne(32).any():
        print("Algún año no tiene 32 entidades"); return 1
    out.to_csv(SALIDA, index=False)
    print(f"{SALIDA}: {len(out)} filas; total nacional 2025 = {out[out['AÑO']==2025]['POB'].sum():,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
