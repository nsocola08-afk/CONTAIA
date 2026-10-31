"""Cálculos contables: libro diario, estados financieros, impuestos. Todo sale de los asientos registrados."""
import pandas as pd


def lineas(docs):
    """DataFrame con una fila por línea de asiento de los documentos registrados."""
    filas = []
    for d in docs:
        if d.get("estado") != "registrado":
            continue
        for l in d["asiento"]:
            filas.append({"doc_id": d["id"], "fecha": d["fecha"], "mes": d["fecha"][:7], "tipo": d["tipo"],
                          "glosa": d["glosa"], "cuenta": str(l["cuenta"]), "nombre": l["nombre"],
                          "debe": float(l["debe"] or 0), "haber": float(l["haber"] or 0)})
    cols = ["doc_id", "fecha", "mes", "tipo", "glosa", "cuenta", "nombre", "debe", "haber"]
    return pd.DataFrame(filas, columns=cols)


def saldo(df, prefijos):
    """Debe - Haber de las cuentas que empiezan con alguno de los prefijos."""
    if df.empty:
        return 0.0
    m = df["cuenta"].str.startswith(tuple(prefijos))
    return float(df.loc[m, "debe"].sum() - df.loc[m, "haber"].sum())


def filtrar(df, periodo):
    return df if periodo in (None, "Todo") or df.empty else df[df["mes"] == periodo]


def estado_resultados(df, g):
    ventas = -saldo(df, g["ventas"])
    desc = saldo(df, g["descuentos"])
    otros_ing = -saldo(df, g["otros_ingresos"])
    costo, personal, servicios = saldo(df, g["costo"]), saldo(df, g["personal"]), saldo(df, g["servicios"])
    tributos, otros_g = saldo(df, g["tributos"]), saldo(df, g["otros_gastos"])
    financ, deprec = saldo(df, g["financieros"]), saldo(df, g["depreciacion"])
    netas = ventas - desc
    bruta = netas - costo
    operativa = bruta - personal - servicios - tributos - otros_g - deprec
    antes = operativa + otros_ing - financ
    return dict(ventas=ventas, descuentos=desc, ventas_netas=netas, costo=costo, utilidad_bruta=bruta,
                personal=personal, servicios=servicios, tributos=tributos, otros_gastos=otros_g,
                depreciacion=deprec, utilidad_operativa=operativa, otros_ingresos=otros_ing,
                financieros=financ, antes_impuestos=antes)


def situacion_financiera(df, g, hasta=None):
    if hasta and hasta != "Todo" and not df.empty:
        df = df[df["mes"] <= hasta]
    imp = saldo(df, g["impuestos"])
    A = {"Efectivo y equivalentes": saldo(df, g["efectivo"]), "Cuentas por cobrar": saldo(df, g["cxc"]),
         "Inventarios": saldo(df, g["inventarios"]), "Tributos por recuperar": max(0.0, imp),
         "Inmuebles, maquinaria y equipo (neto)": saldo(df, g["fijo"])}
    P = {"Tributos por pagar": max(0.0, -imp), "Remuneraciones por pagar": -saldo(df, g["remuneraciones"]),
         "Cuentas por pagar": -saldo(df, g["cxp"])}
    resultado = -(saldo(df, ["6"]) + saldo(df, ["7"]))
    Pt = {"Capital y reservas": -saldo(df, g["capital"]), "Resultados acumulados": -saldo(df, g["acumulados"]),
          "Resultado del ejercicio": resultado}
    ta, tp, tpt = sum(A.values()), sum(P.values()), sum(Pt.values())
    return A, P, Pt, ta, tp, tpt


def balance_comprobacion(df):
    if df.empty:
        return pd.DataFrame(columns=["Cuenta", "Denominación", "Debe", "Haber", "Saldo deudor", "Saldo acreedor"])
    t = df.groupby(["cuenta", "nombre"], as_index=False)[["debe", "haber"]].sum().sort_values("cuenta")
    t["sd"] = (t["debe"] - t["haber"]).clip(lower=0)
    t["sa"] = (t["haber"] - t["debe"]).clip(lower=0)
    t.columns = ["Cuenta", "Denominación", "Debe", "Haber", "Saldo deudor", "Saldo acreedor"]
    return t


def impuestos_por_mes(docs, pais, pct_renta):
    """Liquidación mensual del impuesto al consumo (IGV/IVA) y pago a cuenta de renta."""
    filas = {}
    for d in docs:
        if d["estado"] != "registrado":
            continue
        m = d["fecha"][:7]
        f = filas.setdefault(m, {"Periodo": m, "Ventas gravadas": 0.0, "Impuesto débito": 0.0, "Impuesto crédito": 0.0,
                                  "EsSalud": 0.0, "ONP/AFP": 0.0})
        if d["tipo"] == "venta":
            f["Ventas gravadas"] += d["base"]; f["Impuesto débito"] += d["impuesto"]
        elif d["tipo"] == "compra":
            f["Impuesto crédito"] += d["impuesto"]
        for l in d["asiento"]:
            c = str(l["cuenta"])
            if c.startswith("4031"): f["EsSalud"] += float(l["haber"] or 0)
            if c.startswith(("4032", "407")): f["ONP/AFP"] += float(l["haber"] or 0)
    out = []
    for m in sorted(filas):
        f = filas[m]
        f[f"{pais['impuesto']} a pagar (+) / a favor (−)"] = f["Impuesto débito"] - f["Impuesto crédito"]
        f[f"Renta pago a cuenta ({pct_renta:g}%)"] = f["Ventas gravadas"] * pct_renta / 100
        out.append({k: round(v, 2) if isinstance(v, float) else v for k, v in f.items()})
    return pd.DataFrame(out)


def kpis(docs, df, g, pais):
    er = estado_resultados(df, g)
    A, P, Pt, *_ = situacion_financiera(df, g)
    reg = [d for d in docs if d["estado"] == "registrado"]
    deb = sum(d["impuesto"] for d in reg if d["tipo"] == "venta")
    cre = sum(d["impuesto"] for d in reg if d["tipo"] == "compra")
    return er, A, P, deb - cre
