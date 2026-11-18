# Brecha de género por puesto en universidades públicas estatales de México

Análisis de la composición por sexo, la brecha salarial a igual puesto y las trayectorias de ascenso del personal de las ~34 universidades públicas estatales (UPE), a partir de los microdatos de remuneraciones que cada universidad publica en la Plataforma Nacional de Transparencia (PNT).

## Preguntas

1. **Segregación vertical:** ¿cómo baja la proporción de mujeres al subir de nivel (docente, titular, jefatura, dirección, rectoría)?
2. **Brecha salarial a igual puesto** o nivel, dentro de cada universidad.
3. **Trayectorias 2021–2025:** tasas de ascenso por sexo, enlazando a las mismas personas entre años.

## Fuentes

| Fuente | Qué aporta | Estado |
|---|---|---|
| PNT, remuneraciones (art. 65 fr. VII LGTAIP 2025; antes fr. VIII) | Microdatos por persona y trimestre: puesto, área, sexo, sueldo bruto y neto. Formato general (obligación 7) y formato docente (obligación 248) | Fuente principal; descarga 2021–2025 en curso |
| Formato 911.10 (SEP) | Agregados por sexo y nivel, con categorías homogéneas | Solo la UAT lo publica; falta una solicitud a la SEP-DGPPyEE para validar |

La PNT solo está obligada a conservar el ejercicio en curso y el anterior, así que los años viejos pueden desaparecer.

## Estructura

```
uni/
├── CLAUDE.md                        especificación viva: API, calidad por universidad, advertencias, pasos
├── README.md
├── pnt_remuneraciones_UPE.csv       universidades: id de sujeto obligado, entidad, formato, diagnóstico
├── pnt_remuneraciones_anios_UPE.csv registros por universidad y año (2015–2026)
└── scripts/
    └── descarga_pnt.py              descarga reanudable de la PNT (solo requiere requests)
```

Los datos no están en el repositorio. Viven en el cluster: `acaxees01:/storage/isadoji/sni/uni/data/`.

```
data/
├── raw_json/{siglas}/{año}/obligaciones.json.gz   listado de obligaciones (auditoría)
├── raw_json/{siglas}/{año}/{idFormato}/meta.json  etiqueta, totales, estado (completo o no)
├── raw_json/{siglas}/{año}/{idFormato}/p*.json.gz respuesta cruda de cada página (100 registros)
├── raw/{siglas}/{año}.parquet                     (pendiente) tabla por universidad y año
└── logs/                                          log y resumen TSV de cada corrida
```

## Descarga

```bash
ssh acaxees01
condaon                                   # entorno base de miniconda (trae requests)
cd /storage/isadoji/sni/uni/scripts

python descarga_pnt.py --unis UAS,UAT --max-paginas 3   # prueba corta
python descarga_pnt.py --inventario                     # solo lista formatos y totales
python descarga_pnt.py --anios 2021-2025                # todo (reanudable)
```

- Por cada universidad y año, el script busca en el listado de obligaciones los formatos de remuneraciones (general y docente, sin el tabulador) y baja todas sus páginas.
- Las peticiones son secuenciales, con 1 s de pausa entre ellas, y reintentan con espera creciente.
- Si se corta, se vuelve a correr el mismo comando: salta las páginas ya bajadas y los formatos completos.
- Se corre en el nodo de login dentro de `screen` (no con sbatch). La corrida de 2021–2025 usa dos sesiones: `pnt_udeg` (solo UdeG, ~2 M registros) y `pnt_resto` (las otras 33). En cola, para cuando terminen: `pnt_udeg_extra` y `pnt_resto_extra`, con 2015–2020 y 2026 (2026 queda parcial y habrá que repetirlo en 2027). Avance:

```bash
ssh acaxees01 'tail -3 /storage/isadoji/sni/uni/data/logs/screen_*.out'
```

Notas de la API (no documentada): las páginas empiezan en 0, `size` ≤ 100, el orden es estable y `idIntegra` identifica cada registro. Detalles en `CLAUDE.md`.

## Hoja de ruta

1. ~~Script de descarga~~ (listo); corrida 2021–2025 en curso desde 2026-11-18, 2015–2020 + 2026 en cola; conversión a parquet pendiente.
2. Limpieza: homologar sexo (Mujer/Hombre y Femenino/Masculino), montos, fechas y los dos esquemas (general y docente); quitar duplicados; corte anual con el 4.º trimestre.
3. Taxonomía de puestos homologada entre universidades.
4. Análisis transversal 2025: % de mujeres por nivel; regresión log(salario) ~ sexo + puesto + área por universidad.
5. Panel 2021–2025: enlace de personas y tasas de ascenso por sexo.
6. Validación contra el 911.10.

## Ética

Los nombres son públicos por ley, pero se reemplazan por claves (pseudonimización) en cuanto se termina de enlazar a las personas entre años. Solo se publican agregados y tasas. Los microdatos no se suben a este repositorio.
