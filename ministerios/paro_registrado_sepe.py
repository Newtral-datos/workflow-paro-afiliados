"""
Paro registrado del SEPE: total nacional de un mes.

Fuente: fichero mensual ESTADISTICA_DE_EMPLEO.xls del SEPE, hoja 1.1 (fila AMBOS SEXOS / TOTAL EDAD,
columna PARADOS). Se lee en memoria; no se guarda nada en disco.
  https://www.sepe.es/SiteSepe/contenidos/que_es_el_sepe/estadisticas/
  datos_estadisticos/empleo/datos/{AÑO}/{Mes}_{AÑO}/ESTADISTICA_DE_EMPLEO.xls

Primer mes disponible en .xls: 2006-01. La serie SISPE empieza en 2005-05, pero mayo-diciembre
de 2005 solo está en PDF, y lo anterior son estimaciones retrospectivas, no paro registrado.

Lo usa actualizar.py.
"""

import re
import time
import unicodedata
from urllib.parse import urljoin

import requests
import xlrd

PRIMER_MES = "2006-01"
BASE = ("https://www.sepe.es/SiteSepe/contenidos/que_es_el_sepe/estadisticas/"
        "datos_estadisticos/empleo/datos/{y}/{carpeta}/ESTADISTICA_DE_EMPLEO.xls")
PAGINA = ("https://www.sepe.es/HomeSepe/que-es-el-sepe/estadisticas/empleo/"
          "estadisticas-nuevas/{y}/{mes}.html")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Newtral datos)"}


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


# ---------- descarga ----------

def urls_candidatas(y: int, m: int):
    """El SEPE no es consistente con las mayúsculas (Septiembre_2026 vs abril_2008)."""
    mes = MESES[m - 1]
    for carpeta in (f"{mes.capitalize()}_{y}", f"{mes}_{y}", f"{mes.upper()}_{y}"):
        yield BASE.format(y=y, carpeta=carpeta)


def url_desde_pagina(y: int, m: int) -> tuple[str | None, str]:
    """Plan B: leer el enlace real en la página HTML del mes.
    Desde 2020 el nombre del fichero cambia (ESTADISTICA_DE_-EMPLEO.xls, ESTADISTICA-DE-EMPLEO.xls,
    incluso ESTADISTICA_DE_-EMPLEO.xls0 en mayo de 2026, que el servidor sirve tal cual)."""
    try:
        r = requests.get(PAGINA.format(y=y, mes=MESES[m - 1]), headers=HEADERS, timeout=60)
    except requests.RequestException as e:
        return None, f"no descargado (página del mes: {e.__class__.__name__})"
    if r.status_code != 200:
        return None, "no descargado (sin página del mes en el SEPE)"
    enlace = re.search(r'href="([^"]*ESTADISTICA[^"/]*EMPLEO[^"/]*\.xls\w*)"', r.text, re.I)
    if enlace:
        return urljoin(r.url, enlace.group(1)), ""
    if re.search(r'href="[^"]*ESTADISTICA[^"/]*EMPLEO[^"/]*\.pdf', r.text, re.I):
        return None, "no descargado (el SEPE solo publica PDF este mes)"
    return None, "no descargado (la página del mes no enlaza ningún .xls)"


def bajar_xls(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
    except requests.RequestException:
        return None
    # Un .xls antiguo empieza por la firma OLE2 (D0 CF 11 E0); si no, suele ser una página de error
    if r.status_code == 200 and r.content[:4] == b"\xd0\xcf\x11\xe0":
        return r.content
    return None


def descargar(y: int, m: int) -> tuple[bytes | None, str]:
    """Devuelve (contenido del .xls, "") o (None, motivo)."""
    for url in urls_candidatas(y, m):
        contenido = bajar_xls(url)
        if contenido:
            return contenido, ""
        time.sleep(0.5)
    # Fallaron las variantes de nombre: probar el enlace que publica la página del mes
    url, motivo = url_desde_pagina(y, m)
    if url is None:
        return None, motivo
    contenido = bajar_xls(url)
    if contenido:
        return contenido, ""
    return None, f"no descargado (el enlace de la página no devuelve un .xls válido: {url})"


# ---------- lectura ----------

def leer_parados(contenido: bytes) -> int:
    """Hoja 1.1: fila 'TOTAL EDAD' del bloque AMBOS SEXOS, columna 'PARADOS'."""
    book = xlrd.open_workbook(file_contents=contenido)
    sh = next((book.sheet_by_name(s) for s in book.sheet_names() if s.strip() == "1.1"), None)
    if sh is None:
        raise KeyError("no existe la hoja 1.1")
    filas = [[norm(v) for v in sh.row_values(r)] for r in range(sh.nrows)]
    col = next((f.index("PARADOS") for f in filas if "PARADOS" in f), None)
    if col is None:
        raise ValueError("no encuentro la columna PARADOS en 1.1")
    # Desde 2013 el sexo se repite en la propia fila TOTAL EDAD; hasta 2012 solo aparece en una
    # fila de cabecera encima del bloque. Se recuerda el último bloque visto y vale para ambos.
    bloque = None
    for r, fila in enumerate(filas):
        bloque = next((v for v in fila if v in ("AMBOS SEXOS", "HOMBRES", "MUJERES")), bloque)
        if "TOTAL EDAD" in fila and bloque == "AMBOS SEXOS":
            return int(sh.cell_value(r, col))
    raise ValueError("no encuentro la fila AMBOS SEXOS / TOTAL EDAD en 1.1")


def parados_mes(y: int, m: int) -> tuple[int | None, str]:
    """(parados, "") o (None, motivo)."""
    contenido, motivo = descargar(y, m)
    if contenido is None:
        return None, motivo
    try:
        return leer_parados(contenido), ""
    except Exception as e:  # formato distinto: se devuelve el motivo y se sigue
        return None, str(e)
