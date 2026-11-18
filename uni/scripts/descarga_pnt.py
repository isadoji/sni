#!/usr/bin/env python3
"""Descarga los microdatos de remuneraciones de la PNT para las UPE.

Por cada universidad y ejercicio:
  1. Lista las obligaciones del sujeto obligado (paginado de 10 en 10, páginas desde 0)
     y se queda con los formatos de remuneraciones (general y docente).
  2. Descarga todas las páginas (size=100, páginas desde 0) de cada formato.

Salida (reanudable; las páginas ya bajadas se saltan):
  {out}/raw_json/{siglas}/{anio}/obligaciones.json.gz        listado completo, para auditoría
  {out}/raw_json/{siglas}/{anio}/{idFormato}/meta.json        etiqueta, idObligacion, totales, estado
  {out}/raw_json/{siglas}/{anio}/{idFormato}/p00000.json.gz   respuesta cruda de cada página
  {out}/logs/descarga_{fecha}.log

Solo depende de `requests` (en el cluster: `condaon` y el entorno base).

Ejemplos:
  python descarga_pnt.py --unis UAS,UAT --max-paginas 3        # prueba corta
  python descarga_pnt.py --inventario                          # solo lista formatos y totales
  python descarga_pnt.py                                       # todo, 2021-2025
  python descarga_pnt.py --anios 2015-2026 --excluir UdeG
"""
import argparse
import csv
import datetime as dt
import gzip
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

BASE = "https://consultapublicamx.plataformadetransparencia.org.mx/sabg/api/v1/obligaciones"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
PAGE_SIZE = 100          # el servidor rechaza size > 100 con 400
OBL_PAGE_SIZE = 10       # el listado de obligaciones rechaza size > 10
BACKOFF = [5, 15, 45, 120, 300, 600]
AQUI = Path(__file__).resolve().parent
CSV_UNIS = AQUI.parent / "pnt_remuneraciones_UPE.csv"

log = logging.getLogger("pnt")


class Abortar(Exception):
    pass


def es_remuneracion(ob):
    """Formatos de sueldos: general (obligación 7) y docente (248). Excluye el tabulador."""
    titulo = (ob.get("formato") or {}).get("titulo", "").lower()
    desc = (ob.get("descripcion") or "").lower()
    if "tabulador" in titulo:
        return False
    return "remunera" in titulo or "sueldo" in desc or ob.get("idObligacion") in (7, 248)


class Cliente:
    def __init__(self, pausa):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json"})
        self.pausa = pausa
        self.fallos_seguidos = 0

    def get(self, url, params):
        for intento, espera in enumerate([0] + BACKOFF):
            if espera:
                log.warning("  reintento %d en %ds", intento, espera)
                time.sleep(espera)
            try:
                r = self.s.get(url, params=params, timeout=120)
                time.sleep(self.pausa)
                if r.status_code == 400:
                    raise Abortar(f"400 en {url} {params}: {r.text[:200]}")
                if r.status_code != 200:
                    log.warning("  HTTP %s %s", r.status_code, r.text[:120].replace("\n", " "))
                    continue
                try:
                    d = r.json()
                except ValueError:
                    log.warning("  respuesta no JSON (¿Cloudflare?): %s", r.text[:120].replace("\n", " "))
                    continue
                self.fallos_seguidos = 0
                return d
            except requests.RequestException as e:
                log.warning("  error de red: %s", e)
        self.fallos_seguidos += 1
        if self.fallos_seguidos >= 3:
            raise Abortar("3 peticiones seguidas fallaron tras todos los reintentos")
        return None


def escribir_atomico(path, data, comprimir):
    tmp = path.with_suffix(path.suffix + ".tmp")
    raw = json.dumps(data, ensure_ascii=False).encode()
    if comprimir:
        raw = gzip.compress(raw, compresslevel=6)
    tmp.write_bytes(raw)
    os.replace(tmp, path)


def listar_obligaciones(cli, u, anio):
    params = dict(entidad=u["id_entidad"], idSujetoObligado=u["id_sujeto_pnt"], ejercicio=anio, size=OBL_PAGE_SIZE)
    d = cli.get(BASE, {**params, "page": 0})
    if d is None:
        return None
    obs = list(d.get("obligaciones") or [])
    total_pages = (d.get("paginacion") or {}).get("totalPages") or 0
    for p in range(1, total_pages):
        dp = cli.get(BASE, {**params, "page": p})
        if dp is None:
            return None
        obs += dp.get("obligaciones") or []
    esperado = (d.get("paginacion") or {}).get("total")
    if esperado is not None and len(obs) != esperado:
        log.warning("  obligaciones: %d recibidas vs %s esperadas", len(obs), esperado)
    return obs


def bajar_formato(cli, u, anio, ob, dir_anio, max_paginas):
    idf = ob["formato"]["id"]
    d_f = dir_anio / str(idf)
    d_f.mkdir(parents=True, exist_ok=True)
    meta_p = d_f / "meta.json"
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    if meta.get("completo"):
        log.info("  %s: completo (%s registros), salto", idf, meta.get("total"))
        return meta

    url = f"{BASE}/{idf}/registros/tabla"
    params = dict(idSujetoObligado=u["id_sujeto_pnt"], ejercicio=anio, idObligacion=ob["idObligacion"],
                  idCarga=0, entidad=u["id_entidad"], size=PAGE_SIZE)
    meta.update(siglas=u["siglas"], anio=anio, idFormato=idf, idObligacion=ob["idObligacion"],
                titulo=ob["formato"].get("titulo"), descripcion=ob.get("descripcion"),
                totalRegistros_listado=ob.get("totalRegistros"))
    meta.setdefault("inicio", dt.datetime.now().isoformat(timespec="seconds"))

    p, total_pages, n_reg, t0 = 0, None, 0, time.time()
    while total_pages is None or p < total_pages:
        if max_paginas is not None and p >= max_paginas:
            log.info("  %s: alto en --max-paginas=%d", idf, max_paginas)
            break
        fp = d_f / f"p{p:05d}.json.gz"
        if fp.exists() and total_pages is not None:
            npp = meta.setdefault("n_por_pagina", {})
            if str(p) not in npp:      # corte antes de guardar meta: contar desde el archivo
                npp[str(p)] = len(json.loads(gzip.decompress(fp.read_bytes())).get("registros") or [])
            n_reg += npp[str(p)]
            p += 1
            continue
        d = cli.get(url, {**params, "page": p})
        if d is None:
            log.error("  %s: página %d falló; queda incompleto", idf, p)
            break
        pag = d.get("paginacion") or {}
        if total_pages is None:
            total_pages = pag.get("totalPages") or 0
            if meta.get("total") not in (None, pag.get("total")):
                log.warning("  %s: el total cambió de %s a %s desde la última corrida",
                            idf, meta.get("total"), pag.get("total"))
            meta.update(total=pag.get("total"), totalPages=total_pages,
                        columnas=d.get("columnas"))
            log.info("  %s '%s': %s registros, %d páginas", idf, meta["titulo"], meta["total"], total_pages)
            if fp.exists():          # página 0 ya estaba: no reescribir
                n_reg += meta.get("n_por_pagina", {}).get("0", len(d.get("registros") or []))
                p += 1
                continue
        regs = d.get("registros") or []
        escribir_atomico(fp, d, comprimir=True)
        meta.setdefault("n_por_pagina", {})[str(p)] = len(regs)
        n_reg += len(regs)
        p += 1
        if p % 50 == 0:
            escribir_atomico(meta_p, meta, comprimir=False)
            vel = p / max(time.time() - t0, 1e-9)
            log.info("    %s: página %d/%d (%.2f pág/s)", idf, p, total_pages, vel)

    n_bajados = sum(meta.get("n_por_pagina", {}).values())
    paginas_ok = total_pages is not None and all((d_f / f"p{i:05d}.json.gz").exists() for i in range(total_pages))
    meta["completo"] = bool(paginas_ok and n_bajados == meta.get("total"))
    if paginas_ok and not meta["completo"]:
        log.warning("  %s: páginas completas pero %d registros vs total %s", idf, n_bajados, meta.get("total"))
    meta["n_registros_bajados"] = n_bajados
    meta["fin"] = dt.datetime.now().isoformat(timespec="seconds")
    escribir_atomico(meta_p, meta, comprimir=False)
    return meta


def rango_anios(s):
    out = []
    for parte in s.split(","):
        if "-" in parte:
            a, b = map(int, parte.split("-"))
            out += range(a, b + 1)
        else:
            out.append(int(parte))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="/storage/isadoji/sni/uni/data")
    ap.add_argument("--unis", help="siglas separadas por coma (por defecto, todas las del CSV)")
    ap.add_argument("--excluir", default="", help="siglas a excluir, separadas por coma")
    ap.add_argument("--anios", default="2021-2025", help="p. ej. 2021-2025 o 2017,2021-2025")
    ap.add_argument("--pausa", type=float, default=1.0, help="segundos entre peticiones")
    ap.add_argument("--max-paginas", type=int, default=None, help="tope de páginas por formato (pruebas)")
    ap.add_argument("--inventario", action="store_true", help="solo listar formatos y totales")
    a = ap.parse_args()

    out = Path(a.out)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    logfile = out / "logs" / f"descarga_{dt.datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(logfile), logging.StreamHandler(sys.stdout)])

    with open(CSV_UNIS, newline="") as f:
        unis = list(csv.DictReader(f))
    if a.unis:
        pedidas = [s.strip() for s in a.unis.split(",")]
        unis = [u for u in unis if u["siglas"] in pedidas]
        faltan = set(pedidas) - {u["siglas"] for u in unis}
        if faltan:
            sys.exit(f"Siglas desconocidas: {faltan}")
    excl = {s.strip() for s in a.excluir.split(",") if s.strip()}
    unis = [u for u in unis if u["siglas"] not in excl]
    anios = rango_anios(a.anios)
    log.info("Inicio: %d universidades x %s -> %s (log %s)", len(unis), anios, out, logfile)

    cli = Cliente(a.pausa)
    resumen = []
    try:
        for u in unis:
            for anio in anios:
                log.info("== %s %d", u["siglas"], anio)
                dir_anio = out / "raw_json" / u["siglas"] / str(anio)
                dir_anio.mkdir(parents=True, exist_ok=True)
                obs = listar_obligaciones(cli, u, anio)
                if obs is None:
                    log.error("  no se pudo listar obligaciones")
                    resumen.append((u["siglas"], anio, None, "error listado", None))
                    continue
                escribir_atomico(dir_anio / "obligaciones.json.gz", obs, comprimir=True)
                rem = [o for o in obs if es_remuneracion(o)]
                if not rem:
                    log.info("  sin formatos de remuneraciones")
                    resumen.append((u["siglas"], anio, None, "sin formato", 0))
                    continue
                for o in rem:
                    log.info("  formato %s (obl. %s) '%s': %s registros",
                             o["formato"]["id"], o["idObligacion"], o["formato"].get("titulo"), o.get("totalRegistros"))
                    if a.inventario:
                        resumen.append((u["siglas"], anio, o["formato"]["id"], "inventario", o.get("totalRegistros")))
                        continue
                    m = bajar_formato(cli, u, anio, o, dir_anio, a.max_paginas)
                    resumen.append((u["siglas"], anio, o["formato"]["id"],
                                    "completo" if m.get("completo") else "incompleto", m.get("n_registros_bajados")))
    except Abortar as e:
        log.error("ABORTO: %s", e)
    except KeyboardInterrupt:
        log.error("Interrumpido; se puede reanudar con el mismo comando")

    tsv = out / "logs" / (logfile.stem + "_resumen.tsv")
    with open(tsv, "w") as f:
        f.write("siglas\tanio\tidFormato\testado\tregistros\n")
        for r in resumen:
            f.write("\t".join("" if x is None else str(x) for x in r) + "\n")
    log.info("Fin. Resumen en %s", tsv)


if __name__ == "__main__":
    main()
