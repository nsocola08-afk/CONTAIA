"""
Análisis de cuentas principales: saldos por cliente o proveedor, antigüedad de saldos, kardex valorizado y mayores auxiliares.
Todo se calcula a partir de los asientos registrados. Funciones puras (sin Streamlit) para poder probarlas.
"""
import re
from datetime import date

import pandas as pd

import contabilidad as cont

COLS = ["fecha", "doc_id", "tipo", "documento", "tercero_id", "tercero", "glosa", "cuenta", "cuenta_nombre", "debe", "haber"]
TRAMOS = ["0-30 días", "31-60 días", "61-90 días", "Más de 90 días"]
SIN_ID = "SIN-IDENTIFICAR"


def movimientos(docs, tokens, hasta=None):
    """Una fila por línea de asiento de las cuentas indicadas, con los datos del documento que la originó."""
    filas = []
    for d in docs:
        if d.get("estado") != "registrado" or (hasta and d["fecha"] > hasta):
            continue
        documento = f"{d.get('serie') or ''}-{d.get('numero') or ''}".strip("-")
        for l in d["asiento"]:
            cta = str(l["cuenta"])
            if cont.coincide(cta, tokens):
                filas.append({"fecha": d["fecha"], "doc_id": d["id"], "tipo": d["tipo"], "documento": documento,
                              "tercero_id": d.get("contraparte_id") or "", "tercero": d.get("contraparte_nombre") or "",
                              "glosa": d.get("glosa") or "", "cuenta": cta, "cuenta_nombre": l["nombre"],
                              "debe": float(l["debe"] or 0), "haber": float(l["haber"] or 0)})
    df = pd.DataFrame(filas, columns=COLS)
    if not df.empty:
        df = df.sort_values(["fecha", "doc_id"], kind="stable").reset_index(drop=True)
    return df


# ------------------------------------------------------------------------------------------ terceros
def _norm_id(x):
    return re.sub(r"[^0-9A-Z]", "", str(x or "").upper())


def _norm_nombre(x):
    return re.sub(r"\s+", " ", str(x or "").upper()).strip()


def asignar_terceros(df):
    """Agrega 'clave': el ID fiscal si existe; si no, el nombre (unido al ID cuando el mismo nombre aparece con ID en otro movimiento)."""
    df = df.copy()
    if df.empty:
        df["clave"] = pd.Series(dtype=str)
        return df
    ids, nombres = df["tercero_id"].map(_norm_id), df["tercero"].map(_norm_nombre)
    nombre_a_id = {}
    for i, n in zip(ids, nombres):
        if i and n and n not in nombre_a_id:
            nombre_a_id[n] = i
    df["clave"] = [i or nombre_a_id.get(n) or (f"N:{n}" if n else SIN_ID) for i, n in zip(ids, nombres)]
    return df


def ficha_terceros(df):
    """clave -> (ID, nombre) para mostrar."""
    ficha = {}
    for clave, g in df.groupby("clave"):
        nombre = next((n for n in g["tercero"] if str(n).strip()), "")
        idv = next((i for i in g["tercero_id"] if str(i).strip()), "")
        ficha[clave] = (idv, nombre or ("(sin identificar)" if clave == SIN_ID else ""))
    return ficha


def saldos_por_tercero(df, signo, etiquetas=("Facturado", "Cobrado / abonos", "Saldo"), solo_con_saldo=True):
    """signo +1: saldo = debe − haber (por cobrar). signo −1: saldo = haber − debe (por pagar)."""
    cols = ["ID", "Nombre", etiquetas[0], etiquetas[1], etiquetas[2]]
    if df.empty:
        return pd.DataFrame(columns=cols)
    df = asignar_terceros(df)
    ficha = ficha_terceros(df)
    g = df.groupby("clave")[["debe", "haber"]].sum()
    filas = []
    for clave, r in g.iterrows():
        cargos, abonos = (r["debe"], r["haber"]) if signo > 0 else (r["haber"], r["debe"])
        filas.append([ficha[clave][0], ficha[clave][1], round(cargos, 2), round(abonos, 2), round(cargos - abonos, 2)])
    out = pd.DataFrame(filas, columns=cols)
    if solo_con_saldo:
        out = out[out[etiquetas[2]].abs() >= 0.005]
    return out.sort_values(etiquetas[2], ascending=False).reset_index(drop=True)


def antiguedad(df, signo, corte=None):
    """Antigüedad de saldos por tercero. Los cobros o pagos se aplican a las facturas más antiguas (primero en entrar, primero en salir)."""
    corte = corte or date.today()
    cols = ["ID", "Nombre"] + TRAMOS + ["Saldo a favor", "Total"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    df = asignar_terceros(df)
    ficha = ficha_terceros(df)
    filas = []
    for clave, g in df.groupby("clave", sort=False):
        abiertos, favor = [], 0.0
        for r in g.sort_values(["fecha", "doc_id"], kind="stable").itertuples():
            neto = (r.debe - r.haber) * signo
            f = date.fromisoformat(r.fecha)
            if neto > 1e-9:                                  # factura o cargo
                usar = min(favor, neto)
                favor -= usar
                neto -= usar
                if neto > 1e-9:
                    abiertos.append([f, neto])
            elif neto < -1e-9:                               # cobro, pago o nota de crédito
                credito = -neto
                while credito > 1e-9 and abiertos:
                    t = min(abiertos[0][1], credito)
                    abiertos[0][1] -= t
                    credito -= t
                    if abiertos[0][1] <= 1e-9:
                        abiertos.pop(0)
                favor += credito
        tramos = [0.0] * 4
        for f, m in abiertos:
            dias = max(0, (corte - f).days)
            tramos[0 if dias <= 30 else 1 if dias <= 60 else 2 if dias <= 90 else 3] += m
        total = sum(tramos) - favor
        if abs(total) >= 0.005 or any(abs(t) >= 0.005 for t in tramos):
            filas.append([ficha[clave][0], ficha[clave][1]] + [round(t, 2) for t in tramos] + [round(-favor, 2) + 0.0, round(total, 2) + 0.0])
    return pd.DataFrame(filas, columns=cols).sort_values("Total", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------------------------------ mayores auxiliares
def resumen_cuentas(df, signo):
    if df.empty:
        return pd.DataFrame(columns=["Cuenta", "Denominación", "Debe", "Haber", "Saldo"])
    g = df.groupby(["cuenta", "cuenta_nombre"], as_index=False)[["debe", "haber"]].sum().sort_values("cuenta")
    g["saldo"] = (g["debe"] - g["haber"]) * signo
    g.columns = ["Cuenta", "Denominación", "Debe", "Haber", "Saldo"]
    return g.round(2).reset_index(drop=True)


def mayor(df, signo, cuenta=None):
    """Movimientos con saldo acumulado. 'cuenta' filtra una sola cuenta."""
    d = df if cuenta in (None, "Todas") else df[df["cuenta"] == cuenta]
    d = d.copy()
    d["saldo"] = ((d["debe"] - d["haber"]) * signo).cumsum()
    return d.reset_index(drop=True)


def por_mes(df, signo):
    if df.empty:
        return pd.DataFrame(columns=["Mes", "Debe", "Haber", "Variación", "Saldo acumulado"])
    d = df.assign(Mes=df["fecha"].str[:7]).groupby("Mes")[["debe", "haber"]].sum()
    d["var"] = (d["debe"] - d["haber"]) * signo
    d["acum"] = d["var"].cumsum()
    d = d.reset_index()
    d.columns = ["Mes", "Debe", "Haber", "Variación", "Saldo acumulado"]
    return d.round(2)


def entradas_por_tercero(df):
    """Total que entró por cada proveedor (para existencias, activo fijo, etc.)."""
    if df.empty:
        return pd.DataFrame(columns=["ID", "Nombre", "Entradas"])
    d = asignar_terceros(df[df["debe"] > 0])
    if d.empty:
        return pd.DataFrame(columns=["ID", "Nombre", "Entradas"])
    ficha = ficha_terceros(d)
    g = d.groupby("clave")["debe"].sum()
    out = pd.DataFrame([[ficha[k][0], ficha[k][1], round(v, 2)] for k, v in g.items()], columns=["ID", "Nombre", "Entradas"])
    return out.sort_values("Entradas", ascending=False).reset_index(drop=True)


# ------------------------------------------------------------------------------------------ corriente / no corriente
def parte_no_corriente(docs, tokens, signo, hasta, corte):
    """Parte de un saldo por cobrar (signo 1) o por pagar (signo −1) cuyo vencimiento es posterior a 12 meses del corte.
    Los cobros y pagos se aplican a las facturas más antiguas. Sin fecha límite, se considera de corto plazo."""
    from datetime import timedelta
    mov = movimientos(docs, tokens, hasta=hasta)
    if mov.empty:
        return 0.0
    vence = {d["id"]: d.get("vence") for d in docs}
    limite = corte + timedelta(days=365)
    mov = asignar_terceros(mov)
    total = 0.0
    for _, g in mov.groupby("clave", sort=False):
        abiertos = []
        for r in g.sort_values(["fecha", "doc_id"], kind="stable").itertuples():
            neto = (r.debe - r.haber) * signo
            if neto > 1e-9:
                v = vence.get(r.doc_id) or r.fecha
                try:
                    v = date.fromisoformat(v)
                except ValueError:
                    v = date.fromisoformat(r.fecha)
                abiertos.append([v, neto])
            elif neto < -1e-9:
                credito = -neto
                while credito > 1e-9 and abiertos:
                    t = min(abiertos[0][1], credito)
                    abiertos[0][1] -= t
                    credito -= t
                    if abiertos[0][1] <= 1e-9:
                        abiertos.pop(0)
        total += sum(m for v, m in abiertos if v > limite)
    return round(total, 2)


def situacion_clasificada(docs, df, g, per):
    """Situación financiera con activo y pasivo corriente / no corriente. Devuelve secciones listas para mostrar."""
    import calendar
    A, P, Pt, ta, tp, tpt = cont.situacion_financiera(df, g, per)
    if per in (None, "Todo"):
        hasta, corte = None, date.today()
    else:
        a, m = int(per[:4]), int(per[5:7])
        corte = date(a, m, calendar.monthrange(a, m)[1])
        hasta = corte.isoformat()
    nc_cxc = min(max(parte_no_corriente(docs, g["cxc"], 1, hasta, corte), 0.0), max(A["Cuentas por cobrar"], 0.0))
    nc_cxp = min(max(parte_no_corriente(docs, g["cxp"], -1, hasta, corte), 0.0), max(P["Cuentas por pagar"], 0.0))
    ac = [("Efectivo y equivalentes", A["Efectivo y equivalentes"]), ("Cuentas por cobrar", A["Cuentas por cobrar"] - nc_cxc),
          ("Inventarios", A["Inventarios"]), ("Tributos por recuperar", A["Tributos por recuperar"])]
    anc = ([("Cuentas por cobrar a largo plazo", nc_cxc)] if nc_cxc > 0 else []) + \
          [("Inmuebles, maquinaria y equipo (neto)", A["Inmuebles, maquinaria y equipo (neto)"])]
    pc = [("Tributos por pagar", P["Tributos por pagar"]), ("Remuneraciones por pagar", P["Remuneraciones por pagar"]),
          ("Cuentas por pagar", P["Cuentas por pagar"] - nc_cxp)]
    pnc = [("Cuentas por pagar a largo plazo", nc_cxp)]
    return dict(ac=ac, anc=anc, pc=pc, pnc=pnc, pt=list(Pt.items()), ta=ta, tp=tp, tpt=tpt, corte=corte,
                tac=sum(v for _, v in ac), tanc=sum(v for _, v in anc), tpc=sum(v for _, v in pc), tpnc=sum(v for _, v in pnc))
