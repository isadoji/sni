#!/usr/bin/env python
"""CLI del ETL: genera ``data/sni_tidy.csv`` desde los padrones .xlsx.

    python build_dataset.py            # escribe el CSV
    python build_dataset.py --check    # además imprime totales por año y entidad
    python build_dataset.py -o ruta    # CSV en otra ruta
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sni_dashboard import config
from sni_dashboard.etl import DatasetBuilder


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", type=Path, default=config.TIDY_CSV,
                    help=f"ruta del CSV de salida (def: {config.TIDY_CSV})")
    ap.add_argument("--check", action="store_true",
                    help="imprime un reporte de control tras generar el CSV")
    args = ap.parse_args()

    print(f"Leyendo padrones de {config.DATASETS_DIR} …")
    builder = DatasetBuilder()
    builder.build()
    ruta = builder.save(args.output)
    print(f"\nEscrito {ruta}  "
          f"({len(builder.tidy)} filas, {builder.tidy['N'].sum()} investigadores)")

    if args.check:
        print("\n" + builder.report())


if __name__ == "__main__":
    main()
