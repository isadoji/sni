#!/usr/bin/env python3
"""Permanencia y promoción en el SNII por sexo, 2023→2024 y 2024→2025.

Idea: el padrón del año t dice cuándo vence la vigencia de cada persona. Quien vence el 31 de
diciembre de t tuvo que pasar por la convocatoria de ese año. En el padrón de t+1 se ve el
resultado, enlazando por CVU:

    renovado      está en t+1 con vigencia nueva (inicio el 1 de enero de t+1), mismo nivel
    promovido     ídem, nivel más alto (C→1, 1→2, 2→3)
    bajó          ídem, nivel más bajo
    emérito       pasó de 3 a emérito (convocatoria aparte)
    no está       no aparece en t+1: no aprobado, no solicitó, se jubiló, murió o salió del país
    prorrogado    está en t+1 con la vigencia VIEJA (inicio ≤ t): le extendieron la fecha sin
                  evaluarle (casi siempre 1 o 2 años). No se cuenta como evaluación; se reporta aparte.
    extensión 15 años  vigencia vieja y fin ≥ t+10 o categoría «EXTENSIÓN 15 AÑOS»: tampoco es
                  evaluación; se reporta aparte.

«No está» mezcla rechazos con quien no solicitó: el padrón no permite separarlos.

Además, la «promoción anticipada»: personas vigentes que NO vencían en t pero aparecen en t+1
con vigencia nueva y nivel más alto (pidieron promoción antes de tiempo). Sin el número de
solicitudes no hay tasa de éxito, solo la proporción de la plantilla vigente que lo logra.

Sexo: del grado del padrón 2023 (DR./DRA., MTRO./MTRA.) enlazado por CVU. Quien no está en el
padrón 2023 recibe el sexo del diccionario de nombres (`datasets/mujeres.csv`, el mismo de la
app) y queda marcado `sexo_fuente = "diccionario"`. Contra el grado 2023, el diccionario clasifica
como mujer al 12.3 % de los hombres (Juan, Jesús, José María...) y como hombre al 4.3 % de las
mujeres; neto, sobrestima a las mujeres ~6 pp (ver `validar_diccionario`).

Salida solo agregada: no imprime nombres ni CVU.

    python permanencia/permanencia.py
"""
import re
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DATOS = RAIZ / "datasets"
sys.path.insert(0, str(RAIZ / "app"))
from sni_dashboard.normalize import GenderClassifier  # noqa: E402

ARCHIVOS = {2023: "SNI2023_official.xlsx", 2024: "SNI2024_official.xlsx", 2025: "SNI2025.xlsx"}
RENOMBRAR = {"CVU padrón corregido": "CVU", "CATEGORIA": "CATEGORÍA",
             "FECHA DE INICIO DE VIGENCIA": "FECHA INICIO DE VIGENCIA",
             "FECHA DE FIN DE VIGENCIA": "FECHA FIN DE VIGENCIA",
             "ÁREA DEL CONOCIMIENTO": "ÁREA DE CONOCIMIENTO"}
ORDEN = {"C": 0, "1": 1, "2": 2, "3": 3, "E": 4}
NIVEL_TXT = {"C": "Candidatura", "1": "Nivel I", "2": "Nivel II", "3": "Nivel III"}
SEXO_GRADO = {"DR.": "M_no", "MTRO.": "M_no", "DRA.": "M", "MTRA.": "M"}
RESULTADOS = ["promovido", "renovado", "bajó", "emérito", "no está"]


def _area(v):
    v = re.sub(r"^[IVX]+\.-\s*", "", str(v)).strip().rstrip(".").upper()
    return v.title().replace(" Y ", " y ").replace(" De ", " de ").replace(" La ", " la ")


def padron(anio):
    x = pd.read_excel(DATOS / ARCHIVOS[anio]).rename(columns=RENOMBRAR)
    x["CVU"] = pd.to_numeric(x["CVU"], errors="coerce").astype("Int64")
    x["nivel"] = x["NIVEL"].astype(str).str.strip().str.upper()
    x["inicio"] = pd.to_datetime(x["FECHA INICIO DE VIGENCIA"], errors="coerce").dt.year
    x["fin"] = pd.to_datetime(x["FECHA FIN DE VIGENCIA"], errors="coerce").dt.year
    x["area"] = x["ÁREA DE CONOCIMIENTO"].map(_area)
    cat = x.get("CATEGORÍA", x.get("EMÉRITO", pd.Series("", index=x.index))).fillna("").astype(str)
    x["categoria"] = cat.str.strip().str.upper()
    x["emerito"] = x["categoria"].str.contains("EMÉRITO") | (x["nivel"] == "E")
    x["anio"] = anio
    return x.dropna(subset=["CVU"]).drop_duplicates("CVU")


def sexos(padrones):
    """Serie CVU → (sexo, fuente). Grado 2023 primero; diccionario para el resto."""
    p23 = padrones[2023]
    g = p23.set_index("CVU")["GRADO ACADÉMICO"].astype(str).str.strip().map(SEXO_GRADO)
    out = pd.DataFrame({"sexo": g.replace("M_no", "H"), "sexo_fuente": "grado"}).dropna()
    dic = GenderClassifier(DATOS / "mujeres.csv")
    resto = pd.concat([p[~p["CVU"].isin(out.index)] for a, p in padrones.items() if a != 2023])
    resto = resto.drop_duplicates("CVU").set_index("CVU")
    pila = resto["NOMBRE DEL INVESTIGADOR"].astype(str).str.split(",").str[-1]
    d = dic.classify_series(pila).map({"MUJER": "M", "HOMBRE": "H"})
    return pd.concat([out, pd.DataFrame({"sexo": d, "sexo_fuente": "diccionario"})])


def validar_diccionario(padrones):
    """Matriz grado (verdad) × diccionario en el padrón 2023."""
    p = padrones[2023]
    pila = p["NOMBRE DEL INVESTIGADOR"].astype(str).str.split(",").str[-1]
    dic = GenderClassifier(DATOS / "mujeres.csv").classify_series(pila).map({"MUJER": "M", "HOMBRE": "H"})
    ver = p["GRADO ACADÉMICO"].astype(str).str.strip().map(SEXO_GRADO).replace("M_no", "H")
    return pd.crosstab(ver.rename("grado"), dic.rename("diccionario"))


def transiciones(padrones, sx):
    """Una fila por persona vigente en t: resultado en t+1 y si le tocaba evaluación."""
    filas = []
    for t in (2023, 2024):
        p0 = padrones[t]
        p1 = padrones[t + 1].set_index("CVU")
        d = p0[["CVU", "nivel", "fin", "area", "emerito", "categoria"]].copy()
        d = d.join(p1[["nivel", "inicio", "fin", "emerito", "categoria"]].rename(
            columns={"nivel": "nivel1", "inicio": "inicio1", "fin": "fin1", "emerito": "emerito1",
                     "categoria": "categoria1"}), on="CVU")
        d["anio"] = t
        d["vence"] = d["fin"] == t
        presente = d["nivel1"].notna()
        nueva = presente & (d["inicio1"] == t + 1)
        r0, r1 = d["nivel"].map(ORDEN), d["nivel1"].map(ORDEN)
        d["resultado"] = np.select(
            [~presente,
             nueva & ((d["nivel1"] == "E") | (d["emerito1"] & ~d["emerito"])),
             nueva & (r1 > r0), nueva & (r1 < r0), nueva & (r1 == r0)],
            ["no está", "emérito", "promovido", "bajó", "renovado"], default="prorrogado")
        ext = (d["resultado"] == "prorrogado") & (
            d["categoria1"].fillna("").str.contains("EXTENSI") | (d["fin1"] >= t + 10))
        d.loc[ext, "resultado"] = "extensión 15 años"
        filas.append(d)
    d = pd.concat(filas, ignore_index=True).join(sx, on="CVU")
    d["nivel_txt"] = d["nivel"].map(NIVEL_TXT)
    return d


def evaluables(d):
    """Cohortes que vencían en t, sin eméritos de inicio ni prorrogados, niveles C–3."""
    return d[d["vence"] & ~d["emerito"] & d["nivel"].isin(NIVEL_TXT)
             & ~d["resultado"].isin(["prorrogado", "extensión 15 años"])]


def vencian(d):
    """Todas las personas que vencían en t (niveles C–3, sin eméritos), con prorrogadas."""
    return d[d["vence"] & ~d["emerito"] & d["nivel"].isin(NIVEL_TXT)]


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (100 * (c - h), 100 * (c + h))


def tasas(d, por, resultado):
    """% con `resultado` (str o lista) por grupo y sexo, con IC de Wilson."""
    res = [resultado] if isinstance(resultado, str) else resultado
    out = []
    for k, g in d.groupby(por + ["sexo"]):
        n, x = len(g), int(g["resultado"].isin(res).sum())
        lo, hi = wilson(x, n)
        out.append(dict(zip(por + ["sexo"], k if isinstance(k, tuple) else (k,)),
                        n=n, k=x, pct=100 * x / n, lo=lo, hi=hi))
    return pd.DataFrame(out)


def logit(d, y, controles=("C(nivel)", "C(area)", "C(anio)")):
    """Razón de momios mujer/hombre con controles; errores robustos."""
    import statsmodels.formula.api as smf
    dd = d.assign(y=d["resultado"].isin([y] if isinstance(y, str) else y).astype(int),
                  mujer=(d["sexo"] == "M").astype(int))
    dd = dd[["y", "mujer", "nivel", "area", "anio"]].astype({"nivel": object, "area": object})
    f = "y ~ mujer + " + " + ".join(c for c in controles if dd[c[2:-1]].nunique() > 1)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = smf.logit(f, dd).fit(disp=0, cov_type="HC1", maxiter=200)
    except np.linalg.LinAlgError:          # alguna celda sin variación (áreas pequeñas)
        return {"n": len(dd), **{k: np.nan for k in ("OR", "OR_lo", "OR_hi", "dif_pp", "dif_lo", "dif_hi", "p")}}
    b, (lo, hi) = m.params["mujer"], m.conf_int().loc["mujer"]
    # efecto marginal promedio en puntos porcentuales
    ame = m.get_margeff().summary_frame().loc["mujer"]   # columnas: dy/dx, err, z, p, lo, hi
    return {"n": int(m.nobs), "OR": np.exp(b), "OR_lo": np.exp(lo), "OR_hi": np.exp(hi),
            "dif_pp": 100 * ame.iloc[0], "dif_lo": 100 * ame.iloc[4],
            "dif_hi": 100 * ame.iloc[5], "p": m.pvalues["mujer"]}


SIGUE = ["renovado", "promovido", "bajó", "emérito"]


def por_area(d):
    """Diferencia mujer − hombre (pp, con controles de nivel y año) por área."""
    ev = evaluables(d)
    out = []
    for a, g in ev.groupby("area"):
        s = g[(g["resultado"] != "no está") & g["nivel"].isin(["1", "2"])]
        r = logit(g, SIGUE, controles=("C(nivel)", "C(anio)"))
        q = logit(s, "promovido", controles=("C(nivel)", "C(anio)"))
        out.append({"area": a, "n": r["n"], "%M": 100 * (g["sexo"] == "M").mean(),
                    "sigue_dif": r["dif_pp"], "sigue_lo": r["dif_lo"], "sigue_hi": r["dif_hi"],
                    "n_promo": q["n"], "promo_dif": q["dif_pp"], "promo_lo": q["dif_lo"],
                    "promo_hi": q["dif_hi"]})
    return pd.DataFrame(out)


def anticipada(d):
    """Vigentes que no vencían en t y aparecen promovidos en t+1, por nivel y sexo."""
    v = d[~d["vence"] & ~d["emerito"] & d["nivel"].isin(["C", "1", "2"])]
    return tasas(v, ["nivel_txt"], "promovido")


def cargar():
    warnings.simplefilter("ignore")
    padrones = {a: padron(a) for a in ARCHIVOS}
    sx = sexos(padrones)
    return padrones, sx, transiciones(padrones, sx)


def main():
    pd.set_option("display.width", 150)
    padrones, sx, d = cargar()
    print("padrones:", {a: len(p) for a, p in padrones.items()})
    print("\nDiccionario vs grado (2023):\n", validar_diccionario(padrones))
    ev = evaluables(d)
    print("\nResultado de quienes vencían, por año (incluye prorrogados):")
    print(pd.crosstab([d.loc[d.vence, "anio"]], d.loc[d.vence, "resultado"]))
    print("\nFuente del sexo en las cohortes evaluables:", ev["sexo_fuente"].value_counts().to_dict())
    print("\nDistribución de resultados por nivel y sexo (%):")
    print((pd.crosstab([ev["nivel_txt"], ev["sexo"]], ev["resultado"], normalize="index") * 100)
          .reindex(columns=RESULTADOS).round(1))
    print("\nSigue en el SNII (renovado, promovido, bajó o emérito):")
    print(tasas(ev, ["nivel_txt"], ["renovado", "promovido", "bajó", "emérito"]).round(1).to_string(index=False))
    sigue = ev[ev["resultado"] != "no está"]
    print("\nPromoción, entre quienes siguen (I y II; en C seguir = ser promovido):")
    print(tasas(sigue[sigue["nivel"].isin(["1", "2"])], ["nivel_txt"], "promovido")
          .round(1).to_string(index=False))
    print("\nLogit con controles de nivel, área y año (mujer vs hombre):")
    for nom, base, y in [("sigue en el SNII", ev, ["renovado", "promovido", "bajó", "emérito"]),
                         ("promovido | sigue", sigue[sigue["nivel"].isin(["1", "2"])], "promovido"),
                         ("promovido | vencía", ev[ev["nivel"].isin(["C", "1", "2"])], "promovido")]:
        for etiqueta, b in [("todas", base), ("solo sexo por grado", base[base["sexo_fuente"] == "grado"])]:
            r = logit(b, y)
            print(f"  {nom:20s} {etiqueta:20s} n={r['n']:6d}  dif={r['dif_pp']:+5.1f} pp "
                  f"[{r['dif_lo']:+.1f}, {r['dif_hi']:+.1f}]  OR={r['OR']:.2f}  p={r['p']:.3f}")
    v = vencian(d)
    print("\nProrrogado (vigencia extendida sin evaluación), entre quienes vencían:")
    print(tasas(v, ["nivel_txt"], "prorrogado").round(1).to_string(index=False))
    r = logit(v, "prorrogado")
    print(f"  logit: dif={r['dif_pp']:+.1f} pp [{r['dif_lo']:+.1f}, {r['dif_hi']:+.1f}]")
    print("\nPor área (dif. mujer − hombre en pp, controles de nivel y año):")
    print(por_area(d).round(1).to_string(index=False))
    print("\nPromoción anticipada (vigentes que no vencían):")
    print(anticipada(d).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
