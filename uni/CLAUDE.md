# Proyecto: Brecha de género por posición laboral en universidades públicas estatales (UPE) de México

## Objetivo
Analizar la composición por sexo y la brecha salarial por puesto en las ~34 UPE, y seguir las trayectorias de las personas (ascensos) usando datos abiertos.

Preguntas:
1. Segregación vertical: ¿cómo baja la proporción de mujeres al subir de nivel (docente, titular, jefatura, dirección, rectoría)?
2. Brecha salarial con el mismo puesto o nivel, dentro de cada universidad.
3. Trayectorias 2021–2025: tasas de ascenso por sexo.

## Fuentes evaluadas (noviembre de 2026)

### 1. PNT – Remuneraciones (fracción VIII antigua; art. 65 fr. VII de la LGTAIP 2025). FUENTE PRINCIPAL
- Microdatos: una fila por persona y periodo (trimestre).
- Columnas clave: `Ejercicio`, `FechaDeInicioDelPeriodoQueSeInforma`, `TipoDeIntegranteDelSujetoObligadoCatalogo`, `ClaveONivelDelPuesto`, `DenominacionODescripcionDelPuestoRedactadosConPerspectivaDeGenero`, `DenominacionDelCargoDeConformidadConElNombramientoOtorgado`, `AreaDeAdscripcion`, `NombreS`, `PrimerApellido`, `SegundoApellido`, `SexoCatalogo`, `MontoDeLaRemuneracionMensualBruta...`, `MontoDeLaRemuneracionMensualNeta...`
- El campo de sexo existe en todos los años. Los formatos 2015–2017 usan `SexoFemeninoMasculino` con valores Femenino/Masculino; los recientes usan Mujer/Hombre. Hay que homologar.
- Conservación legal: solo el ejercicio en curso más el anterior. Los años viejos pueden desaparecer, así que conviene DESCARGAR PRONTO.

### 2. Formato 911.10 (SEP)
- Agregados por sexo: directivos centrales y de facultad, docentes, docentes-investigadores, SNI por nivel. Categorías homogéneas, sin salario.
- Publicado llenado solo por la UAT (2021–2023, en dpei.uat.edu.mx). BUAP y UJED publican anuarios con datos parciales.
- Para el resto hay que hacer una solicitud de información a la SEP-DGPPyEE (pendiente de redactar).

## API de la PNT (descubierta; no documentada)
Base: `https://consultapublicamx.plataformadetransparencia.org.mx`
Está protegida por Cloudflare: desde un servidor puede devolver la página "Just a moment". En la sesión anterior funcionó con fetch() desde el navegador (Claude in Chrome). Probar primero con requests/httpx; si falla, usar Playwright o el navegador.

- Lista de sujetos obligados (9,086):
  `POST /gwpnt/api/federado/sujetosObligados/buscar-sujetos-obligados` con body `{}` y header `Content-Type: application/json`
  → `[{id, idOrganoGarante, idEntidadFederativa, nombre, ...}]`
- Formatos disponibles por año:
  `GET /sabg/api/v1/obligaciones/facetasfiltros?entidad={idEntidad}&idSujetoObligado={id}&ejercicio={año}`
  → `formatos[{id, etiqueta, total}]` (`total` = número de cargas o trimestres)
- Obligaciones con su conteo (paginado de 10 en 10; size>10 da error 400):
  `GET /sabg/api/v1/obligaciones?entidad=..&idSujetoObligado=..&ejercicio=..&page=N&size=10`
- Registros (los microdatos):
  `GET /sabg/api/v1/obligaciones/{idFormato}/registros/tabla?idSujetoObligado=..&ejercicio=..&idObligacion=7&idCarga=0&entidad=..&page=N&size=100`
  → `{columnas[{key,label}], paginacion{total,totalPages}, registros[{valores[], fecPer, subtablas}]}`
  - `idObligacion=7` corresponde a SUELDOS (remuneraciones).
  - La remuneración docente aparte suele ser `idObligacion=248`.
  - Algunas universidades tienen formatos duplicados (UNISON e ITSON usan 47392 y 55146): probar todos los que tengan la etiqueta "Remuneraci" y quedarse con el de más registros.
  - Hay que ser amable con el servidor: peticiones secuenciales y pausas.
- Verificado el 2026-11-18:
  - **Las páginas empiezan en 0**, tanto en `obligaciones` como en `registros/tabla`, y van de `0` a `totalPages-1`. Con `page=1` se pierde la primera página (en el listado de obligaciones, ahí vienen las obligaciones 1–8, incluida la 7, de sueldos).
  - `registros/tabla` acepta `size` ≤ 100 (con 500 da 400). Tarda unos 1.3 s por página. El orden es estable entre peticiones e `idIntegra` es único por registro: sirve como llave.
  - Cloudflare NO bloqueó `curl`/`requests` simples ni desde doramilaje ni desde acaxees01.
  - El formato docente (obl. 248) tiene otro esquema: 17 columnas (unidad académica, tipo o nivel de contratación, bruta, neta, estímulos, total), contra 32 del general. La limpieza debe manejar los dos.
  - UAEH sí tiene formato docente (4 186 registros en 2025), además de los ~420 funcionarios del general.

## Descarga
- Script: `scripts/descarga_pnt.py`. Solo usa `requests`; se puede reanudar (salta las páginas ya bajadas y los formatos marcados `completo`). Descubre por año los formatos de remuneraciones (general y docente, sin el tabulador) desde el listado de obligaciones, así que no depende de los IDs del CSV.
- Datos en el cluster: `acaxees01:/storage/isadoji/sni/uni/data/`
  - `raw_json/{siglas}/{año}/obligaciones.json.gz`: listado completo, para auditoría.
  - `raw_json/{siglas}/{año}/{idFormato}/meta.json` y `p00000.json.gz`, …: respuesta cruda de cada página.
  - `logs/`: un log y un resumen TSV por corrida.
- Entorno en el cluster: `condaon` (entorno `base`: requests 2.34 y pandas, sin pyarrow). Para el parquet hará falta un entorno propio (`uni`); ningún entorno actual tiene requests + pandas + pyarrow.
- Correr en el nodo de login dentro de `screen` (no hay tmux), no con sbatch.
- Tamaño: ~15 KB por página comprimida, unos 0.6 GB para 2021–2025.
- Corridas lanzadas el 2026-11-18 en acaxees01 (sesiones de `screen`):
  - `pnt_udeg` (UdeG, 2021–2025) y `pnt_resto` (las otras 33, 2021–2025). Velocidad medida: ~5 s/página en UdeG (~28 h) y ~2.3 s/página en el resto (~13 h).
  - En cola: `pnt_udeg_extra` y `pnt_resto_extra`, con 2015–2020 y 2026. Cada una espera a que termine su sesión correspondiente para no tener más de dos procesos a la vez.
  - 2026 queda parcial (el año está en curso); hay que volver a correrlo en 2027 para completar el 4.º trimestre.

## Universidades (id_sujeto, id_entidad, siglas)
551,1,UAA | 682,2,UABC | 788,3,UABCS | 856,4,UACAM | 857,4,UNACAR | 1369,7,UNACH | 1433,8,UACH | 1434,8,UACJ | 3098,5,UAdeC | 1153,6,UCOL | 1847,10,UJED | 2003,11,UG | 3110,12,UAGRO | 14669,13,UAEH | 2936,14,UdeG | 3334,15,UAEMex | 3533,16,UMSNH | 3631,17,UAEM | 3777,18,UAN | 11187,19,UANL | 11731,20,UABJO | 4479,21,BUAP | 4594,22,UAQ | 12851,23,UQROO | 4776,24,UASLP | 4865,25,UAS | 5027,26,UNISON | 4920,26,ITSON | 5119,27,UJAT | 5277,28,UAT | 5389,29,UATx | 5642,30,UV | 5870,31,UADY | 5968,32,UAZ

Los IDs de formato de remuneraciones por universidad están en `pnt_remuneraciones_UPE.csv`. Los conteos por año (2015–2026) están en `pnt_remuneraciones_anios_UPE.csv`.

## Diagnóstico de calidad (muestra de ~300–400 registros de 2025 por universidad)
- Usables en 2025 (sexo lleno, puesto detallado, salario): UAA, UABC, UACAM, UNACAR, UNACH, UACH, UACJ*, UCOL, UJED, UG, UdeG, UAEM, UAN, UABJO, BUAP, UAQ, UQROO, UASLP, UAS, ITSON, UJAT, UAT, UATx, UV, UADY.
  - *UACJ: el campo de puesto es genérico; usar el de cargo.
- Parciales:
  - UANL: el puesto solo dice Académico/Administrativo.
  - UAEH: solo publica funcionarios (~420 registros).
  - UMSNH: el formato general es pequeño; el grueso está en el formato docente.
  - UAZ: tiene 2024, no 2025.
- No usables:
  - UNISON: sexo vacío en 2024 y 2025 (revisar años viejos).
  - UAEMex: sin 2025 y sexo vacío.
  - UAGRO: 4 registros por año.
  - UABCS y UAdeC: nada cargado.

## Años disponibles para el panel de trayectorias
- Hay un hueco casi general en 2018–2020. Ventana útil: 2021–2025.
- Panel 2021–2025 completo: UABC, UNACAR, UNACH, UG, UANL, UABJO, UAQ, UASLP, UJAT, UAT, UADY.
- Series largas: UCOL y UdeG (2019–2025), ITSON (2018–2025).
- UAA, UACH, UACJ, UMSNH: 2022–2025.

## Advertencias metodológicas
- Registros ≠ personas: cada trimestre se repite a la misma gente. Deduplicar por persona y periodo; para cortes anuales usar el 4.º trimestre.
- UdeG tiene ~400 mil registros por año: revisar la periodicidad (¿quincenal?) y los duplicados.
- Los montos no son homogéneos entre universidades: la mediana va de ~6k (UAEM) a ~79k (ITSON); sospecha de mezcla mensual/quincenal. Comparar brechas dentro de cada universidad; normalizar antes de comparar entre universidades.
- No hay identificador único: enlazar por nombre normalizado (sin acentos, mayúsculas, espacios) + universidad, usando el área como desempate. Esperar errores por homónimos.
- Sesgo de supervivencia: las salidas no se distinguen de errores de captura.
- Ética: los nombres son públicos por ley, pero pseudonimizar después de enlazar. Publicar solo agregados y tasas.
- Homologar catálogos de puestos por universidad y por año. Es el trabajo más pesado; usar reglas más un LLM y validar a mano una muestra.

## Literatura previa
- Niebla Moreno et al. (2024), "Presencia del liderazgo femenino en las universidades públicas sinaloenses", Rev. Educación Superior y Sociedad 36(2), doi:10.54674/ess.v36i2.923. Usa la PNT 2023, solo Sinaloa y solo liderazgo.
- "El Techo de Cristal en Universidades Públicas de México. Un Análisis Exploratorio" (UAT, 2018): 37 universidades, a partir de sitios web, nivel central.
- Ortiz Ortega y Góngora Soberanes (2019): ~14 % de mujeres en rectoría, secretaría general y abogacía general.
- Hueco detectado: nadie ha usado la fracción VIII de forma sistemática en todas las UPE, ni ha hecho trayectorias con ella.

## Próximos pasos
1. Descarga: script listo y probado (UAS, UAT, UAEH; 2026-11-18). Corrida 2021–2025 en curso y 2015–2020 + 2026 en cola; falta la conversión JSON → parquet en `data/raw/{siglas}/{año}.parquet`.
2. Limpieza: homologar el sexo, parsear montos y fechas, deduplicar, quedarse con el 4.º trimestre de cada año.
3. Taxonomía de puestos: directivo alto / mando medio / académico TC por categoría / asignatura / administrativo / apoyo.
4. Análisis transversal 2025: % de mujeres por nivel; brecha salarial a igual puesto (regresión log(salario) ~ sexo + puesto + área, por universidad).
5. Panel 2021–2025: enlace de personas y tasas de ascenso por sexo (modelo de transiciones o de supervivencia).
6. En paralelo: solicitud a SEP-DGPPyEE por el 911.10 de las 34 UPE, 2015–2025, en formato abierto. Validar la PNT contra el 911 de la UAT.
