"""
Genera los datos de los gráficos de paro registrado (SEPE) y afiliación (Seguridad Social).

Uso:
  python ministerios/actualizar.py            # consulta solo los meses de paro que falten
  python ministerios/actualizar.py --rehacer  # vuelve a consultar todo el paro desde 2006

Salidas (carpeta datos/ en la raíz del proyecto):
  paro_afiliacion.csv -> fecha, parados, afiliados y, para cada uno, variación mensual e
                         interanual en personas y en %. El paro empieza en 2006-01 y la
                         afiliación en 2001-01; antes de 2006 la columna de paro va vacía.
  nota.json           -> pie de gráfico para Datawrapper: "Actualizado por última vez el
                         dd/mm/aaaa", con la fecha en que se recogió el dato más reciente.

Entrada opcional:
  paro_provisional.json -> {"AAAA-MM": parados} con cifras de la nota de prensa del Ministerio de
                           Trabajo, para los meses que el SEPE aún no ha subido en .xls. Se usan
                           solo mientras falte el fichero del SEPE; esos meses se siguen
                           consultando en cada ejecución y, cuando el SEPE publica, el dato oficial
                           sustituye al provisional y el mes se borra de este fichero.

El paro se consulta mes a mes y solo los meses que no están ya en el CSV. La afiliación es un
único fichero pequeño con toda la serie y se vuelve a leer entera.

Si después del día 7 de un mes todavía falta el dato del mes anterior, el script termina con
error para que GitHub Actions avise por correo. Si lo que falta es solo el .xls de un mes que ya
tiene cifra provisional, deja un aviso en el log de Actions en lugar de fallar.

Requisitos: pip install -r requirements.txt
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from afiliacion_seg_social import serie_afiliacion
from paro_registrado_sepe import PRIMER_MES, parados_mes

DATOS = Path(__file__).resolve().parent.parent / "datos"
CSV = DATOS / "paro_afiliacion.csv"
NOTA = DATOS / "nota.json"
PROVISIONAL = DATOS / "paro_provisional.json"
SERIES = ["parados", "afiliados"]
# Ambos organismos publican hacia el segundo día laborable del mes siguiente
DIA_LIMITE = 7


def meses(desde: str, hasta: dt.date):
    y, m = map(int, desde.split("-"))
    while (y, m) <= (hasta.year, hasta.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rehacer", action="store_true",
                    help="ignora el CSV existente y vuelve a consultar todo el paro")
    args = ap.parse_args()
    DATOS.mkdir(exist_ok=True)
    hoy = dt.datetime.now(ZoneInfo("Europe/Madrid")).date()

    previo = pd.read_csv(CSV) if CSV.exists() else pd.DataFrame(columns=["fecha", *SERIES])

    # Cifras provisionales de la nota de prensa, a la espera del .xls del SEPE
    provisional = json.loads(PROVISIONAL.read_text(encoding="utf-8")) if PROVISIONAL.exists() else {}
    provisional = {f"{k}-01": int(v) for k, v in provisional.items()}

    # Paro: solo los meses que faltan. Los provisionales cuentan como pendientes.
    paro = {} if args.rehacer else previo.dropna(subset=["parados"]).set_index("fecha")["parados"].to_dict()
    for fecha in provisional:
        paro.pop(fecha, None)
    avisos, confirmados = [], []
    for y, m in meses(PRIMER_MES, hoy):
        fecha = f"{y}-{m:02d}-01"
        if fecha in paro:
            continue
        parados, motivo = parados_mes(y, m)
        if parados is None:
            avisos.append(f"paro {fecha[:7]}: {motivo}")
            if fecha in provisional:
                paro[fecha] = provisional[fecha]
                print(f"paro {fecha[:7]}: {provisional[fecha]:,} (provisional)".replace(",", "."))
        else:
            paro[fecha] = parados
            print(f"paro {fecha[:7]}: {parados:,}".replace(",", "."))
            if fecha in provisional:
                confirmados.append(fecha)
                if parados != provisional[fecha]:
                    print(f"::warning::paro {fecha[:7]}: el SEPE da {parados}, distinto del "
                          f"provisional {provisional[fecha]}; se usa el del SEPE")

    if confirmados:
        resto = {k[:7]: v for k, v in sorted(provisional.items()) if k not in confirmados}
        PROVISIONAL.write_text(json.dumps(resto, indent=2) + "\n", encoding="utf-8")
        print("Provisional sustituido por el dato del SEPE:", ", ".join(f[:7] for f in confirmados))

    afiliacion = serie_afiliacion().set_index("fecha")["afiliados"]

    # Se reindexa a todos los meses para que diff/pct_change comparen con el mes correcto
    df = pd.DataFrame({"parados": pd.Series(paro, dtype="float"), "afiliados": afiliacion})
    df.index = pd.to_datetime(df.index)
    df = df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="MS"))
    for s in SERIES:
        df[f"{s}_var_mensual"] = df[s].diff()
        df[f"{s}_var_mensual_pct"] = (df[s].pct_change(fill_method=None) * 100).round(2)
        df[f"{s}_var_interanual"] = df[s].diff(12)
        df[f"{s}_var_interanual_pct"] = (df[s].pct_change(12, fill_method=None) * 100).round(2)
    enteros = [c for c in df.columns if not c.endswith("_pct")]
    df[enteros] = df[enteros].round().astype("Int64")
    columnas = ["fecha"] + [c for s in SERIES for c in df.columns if c.startswith(s)]
    df = df.rename_axis("fecha").reset_index()
    df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d")
    df = df[columnas]
    df.to_csv(CSV, index=False)

    # Nota: la fecha solo cambia cuando entra un dato nuevo (un mes más en cualquiera de las series)
    ultimo_antes = {s: previo.dropna(subset=[s])["fecha"].max() if s in previo else None for s in SERIES}
    ultimo_ahora = {s: df.dropna(subset=[s])["fecha"].max() for s in SERIES}
    if ultimo_ahora != ultimo_antes or confirmados or not NOTA.exists():
        nota = {"annotate": {"notes": f"Actualizado por última vez el {hoy:%d/%m/%Y}"}}
        NOTA.write_text(json.dumps(nota, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("Nota actualizada:", nota["annotate"]["notes"])

    print(f"Último paro: {ultimo_ahora['parados'][:7]} | última afiliación: {ultimo_ahora['afiliados'][:7]}")

    # ¿Falta el mes anterior cuando ya debería estar publicado?
    mes_anterior = (hoy.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m-01")
    if hoy.day > DIA_LIMITE:
        retrasados = [s for s in SERIES if ultimo_ahora[s] < mes_anterior]
        if retrasados:
            print("\n".join(avisos), file=sys.stderr)
            sys.exit(f"ERROR: falta el dato de {mes_anterior[:7]} en: {', '.join(retrasados)}")
        pendientes = [f[:7] for f in provisional if f not in confirmados]
        if pendientes:
            print(f"::warning::paro provisional, sin .xls del SEPE todavía: {', '.join(pendientes)}")


if __name__ == "__main__":
    main()
