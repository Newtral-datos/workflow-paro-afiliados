"""
Afiliados medios a la Seguridad Social: serie nacional mensual desde 2001-01.

Fuente: "19_Serie afiliación media por regímenes (Total Sistema).xlsx", enlazada en la página
"Afiliados medios TOTALES" de www.seg-social.es (Estadísticas > Afiliación y alta de trabajadores >
Afiliaciones en alta laboral > Afiliación media mensual). Es un único fichero pequeño (~50 KB) con
toda la serie, que el ministerio actualiza cada mes. Su URL lleva un identificador aleatorio, así
que se saca del enlace de la página. Se lee en memoria; no se guarda nada en disco.

Se usa el TOTAL SISTEMA, la cifra oficial que da el ministerio. Incluye a los cuidadores no
profesionales (convenio especial, ~108.000 en 2026), que no son empleo.

Lo usa actualizar.py.
"""

import html
import re
import unicodedata
import warnings
from io import BytesIO
from urllib.parse import unquote_plus

import openpyxl
import pandas as pd
import requests

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

WEB = "https://www.seg-social.es"
PAGINA_MEDIOS = ("/wps/portal/wss/internet/EstadisticasPresupuestosEstudios/Estadisticas/"
                 "EST8/EST10/EST290/EST291")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Newtral datos)"}


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


def get(url: str) -> requests.Response:
    r = requests.get(url if url.startswith("http") else WEB + url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r


def url_serie() -> str:
    """Enlace al fichero de la serie en la página de afiliados medios."""
    t = get(PAGINA_MEDIOS).text
    for h in re.findall(r'href="(/wps/wcm/connect/wss/[0-9a-f-]{36}/[^"]+)"', t):
        h = html.unescape(h)
        if re.search(r"serie afiliaci.n media", unquote_plus(h.split("?")[0]), re.I):
            return WEB + h
    raise ValueError("no encuentro el enlace a la serie de afiliación media en la página")


def serie_afiliacion() -> pd.DataFrame:
    """DataFrame con fecha (AAAA-MM-01) y afiliados (media mensual redondeada)."""
    contenido = get(url_serie()).content
    if contenido[:4] != b"PK\x03\x04":
        raise ValueError("la serie descargada no es un .xlsx")
    ws = openpyxl.load_workbook(BytesIO(contenido), read_only=True, data_only=True).worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    # La columna se busca por nombre en la fila de cabecera de regímenes
    cab = next(f for f in filas[:6] if any("TOTAL SISTEMA" in norm(v) for v in f if v))
    col = next(i for i, v in enumerate(cab) if v and "TOTAL SISTEMA" in norm(v))
    res = []
    for f in filas:
        t = norm(f[0]).lower().split() if isinstance(f[0], str) else []
        if len(t) == 2 and t[0] in MESES and t[1].isdigit():
            res.append({"fecha": f"{t[1]}-{MESES.index(t[0]) + 1:02d}-01", "afiliados": round(f[col])})
    if not res:
        raise ValueError("no encuentro filas 'Mes AAAA' en la serie de afiliación")
    return pd.DataFrame(res)
