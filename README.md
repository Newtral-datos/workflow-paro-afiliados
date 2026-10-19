# Paro registrado y afiliación a la Seguridad Social

Datos mensuales para dos gráficos de líneas en Datawrapper:

- **Paro registrado** según el SEPE, desde enero de 2006.
- **Afiliados medios** a la Seguridad Social, desde enero de 2001.

Un workflow de GitHub Actions comprueba cada día laborable si hay datos nuevos y, si los hay,
actualiza el CSV y la nota del gráfico. Datawrapper lee ambos ficheros directamente del repositorio.

## Ficheros que genera

### `datos/paro_afiliacion.csv`

Una fila por mes.

| Columna | Descripción |
|---|---|
| `fecha` | Primer día del mes (AAAA-MM-01) |
| `parados` | Paro registrado, en personas. Vacío antes de 2006-01 |
| `parados_var_mensual` | Diferencia con el mes anterior, en personas |
| `parados_var_mensual_pct` | Diferencia con el mes anterior, en % |
| `parados_var_interanual` | Diferencia con el mismo mes del año anterior, en personas |
| `parados_var_interanual_pct` | Diferencia con el mismo mes del año anterior, en % |
| `afiliados` | Afiliados medios del mes (TOTAL SISTEMA), en personas |
| `afiliados_var_*` | Las mismas cuatro variaciones para la afiliación |

### `datos/nota.json`

Pie del gráfico, en el formato de metadatos externos de Datawrapper:

```json
{"annotate": {"notes": "Actualizado por última vez el dd/mm/aaaa"}}
```

La fecha es la del día en que el script recogió el dato más reciente. Solo cambia cuando entra un
mes nuevo de cualquiera de las dos series; las ejecuciones sin datos nuevos no la tocan.

### URLs para Datawrapper

- Datos: `https://raw.githubusercontent.com/Newtral-datos/workflow-paro-afiliados/main/datos/paro_afiliacion.csv`
- Nota: `https://raw.githubusercontent.com/Newtral-datos/workflow-paro-afiliados/main/datos/nota.json`

El repositorio tiene que ser público para que Datawrapper pueda leerlos.

## Fuentes

### Paro registrado: SEPE

Fichero mensual `ESTADISTICA_DE_EMPLEO.xls`, hoja 1.1, fila *AMBOS SEXOS / TOTAL EDAD*, columna
*PARADOS*.

- URL habitual: `https://www.sepe.es/SiteSepe/contenidos/que_es_el_sepe/estadisticas/datos_estadisticos/empleo/datos/{AÑO}/{Mes}_{AÑO}/ESTADISTICA_DE_EMPLEO.xls`
- El nombre de la carpeta y del fichero no es estable: cambian las mayúsculas del mes, desde 2020
  aparecen variantes como `ESTADISTICA_DE_-EMPLEO.xls` o `ESTADISTICA-DE-EMPLEO.xls`, y en mayo de
  2026 el enlace oficial termina en `.xls0`. Por eso el script prueba primero las variantes
  habituales y, si fallan, lee el enlace real en la página del mes
  (`/HomeSepe/que-es-el-sepe/estadisticas/empleo/estadisticas-nuevas/{año}/{mes}.html`).
- El formato de la hoja 1.1 cambió en 2013. El script lee los dos.

### Afiliación: Seguridad Social

Fichero *19_Serie afiliación media por regímenes (Total Sistema).xlsx*, enlazado en la página
"Afiliados medios TOTALES" (Estadísticas > Afiliación y alta de trabajadores > Afiliaciones en alta
laboral > Afiliación media mensual). Un único Excel de unos 50 KB con toda la serie desde 2001; la
URL lleva un identificador aleatorio y se saca del enlace de la página. Se usa la columna TOTAL
SISTEMA, la cifra oficial del ministerio.

## Por qué el paro empieza en 2006

En mayo de 2005 el SEPE cambió a la metodología SISPE, y las cifras de antes no son comparables con
las de después.

| Periodo | Qué hay | ¿Se usa? |
|---|---|---|
| Hasta abril de 2005 | Paro con la metodología antigua (SILE). En abril de 2005 eran 1.653.537 personas; la estimación con SISPE para ese mismo mes es de 2.095.945, unas 440.000 más (+27%) | No: no es comparable |
| Enero de 1996 a abril de 2005 | Estimaciones retrospectivas del SEPE con metodología SISPE: un modelo (los valores llevan decimales), no paro registrado | No: es una estimación, no un recuento |
| Mayo a diciembre de 2005 | Paro SISPE, comparable, pero el SEPE solo lo publica en PDF | No: 8 meses que habría que meter a mano |
| Desde enero de 2006 | Paro SISPE en `.xls` cada mes | Sí |

Consecuencia: la variación mensual del paro empieza en febrero de 2006 y la interanual en enero de
2007.

## Cómo leer la serie de afiliación

La serie es continua desde 2001 y no tiene una ruptura como la del paro, pero hay efectos que mueven
el total sin que cambie el empleo:

- **Cuidadores no profesionales.** Familiares que cuidan a personas dependientes y cotizan por un
  convenio especial. No son empleo, pero el TOTAL SISTEMA los incluye. Llegaron a unos 180.000 a
  mediados de 2012, cayeron a unos 23.000 a finales de 2012 cuando el Estado dejó de pagar su
  cotización, y crecen de nuevo desde abril de 2019 (unos 108.000 en 2026). Por ejemplo, la caída
  interanual de diciembre de 2012 es de −787.000 con cuidadores y de −639.000 sin ellos.
- **Empleadas de hogar en 2012.** La reforma obligó a dar de alta a todas, también a las de pocas
  horas. El colectivo pasó de unas 297.000 a unas 416.000 a lo largo de 2012.
- **ERTE en 2020.** Las personas en ERTE siguieron contando como afiliadas, así que la caída de abril
  de 2020 (−548.000) es menor que la pérdida real de actividad.
- **Afiliaciones, no personas.** Quien tiene dos empleos cuenta dos veces.
- **Es una media de los valores diarios del mes**, por eso viene con decimales; aquí se redondea a
  enteros.

## Código

```
.github/workflows/actualizar_datos.yml   workflow de GitHub Actions
ministerios/actualizar.py                script principal: genera el CSV y la nota
ministerios/paro_registrado_sepe.py      descarga y lee el paro de un mes
ministerios/afiliacion_seg_social.py     descarga y lee la serie de afiliación
datos/                                   salidas (las actualiza el workflow)
requirements.txt
```

- **`actualizar.py`**: lee el CSV existente y consulta al SEPE solo los meses de paro que faltan.
  Lee entera la serie de afiliación, une las dos series, calcula las variaciones y escribe el CSV.
  Actualiza la nota solo si ha entrado un mes nuevo. Si después del día 7 todavía falta el dato del
  mes anterior, termina con error para que GitHub avise por correo.
- **`paro_registrado_sepe.py`**: `parados_mes(año, mes)` descarga el `.xls` del mes en memoria y
  devuelve el total nacional, o el motivo por el que no ha podido.
- **`afiliacion_seg_social.py`**: `serie_afiliacion()` localiza el enlace de la serie, la descarga
  en memoria y devuelve todos los meses.

No se guarda en disco ningún Excel: solo los dos ficheros de `datos/`.

## Actualización automática

El workflow se ejecuta los días laborables a las 7:30 y a las 10:30 UTC (9:30 y 12:30 en Madrid en
verano; 8:30 y 11:30 en invierno). Los dos organismos publican hacia las 9:00 del segundo día
laborable del mes. Si no hay datos nuevos, no hace commit. También se puede lanzar a mano desde la
pestaña **Actions → Actualizar paro y afiliación → Run workflow**.

El workflow necesita permiso de escritura: **Settings → Actions → General → Workflow permissions →
Read and write permissions**.

## Uso en local

```
pip install -r requirements.txt
python ministerios/actualizar.py            # solo consulta lo que falta
python ministerios/actualizar.py --rehacer  # vuelve a descargar todo el paro desde 2006 (~250 ficheros)
```
