"""
Modo simple: arma el asiento de una operación a partir de los datos que escribe el usuario (sin leer facturas).

Cada función recibe la ficha del país `p` y un diccionario `d` con lo escrito en el formulario, y devuelve un documento
con el mismo formato que usa el lector de facturas, para que los dos modos compartan reportes, destinos y revisión.
"""
import claude_bedrock as ia

TIPOS = ["Venta", "Compra (mercadería, insumos)", "Gasto (servicios y consumo)", "Activo fijo", "Honorarios",
         "Planilla", "Cobranza a cliente", "Pago a proveedor o deuda", "Aporte de capital", "Asiento manual"]
FORMAS = ["A crédito (por cobrar o por pagar)", "Contado – banco", "Contado – caja"]
COMPROBANTES = ["Factura", "Boleta de venta", "Recibo por honorarios", "Nota de crédito", "Nota de débito", "Ticket / otro"]
VOUCHER = "Voucher / movimiento bancario"


# ------------------------------------------------------------------------------------------ importes
def importes(monto, modo, tasa_pct, sobre_total=False):
    """modo: 'incluido' (el monto ya trae impuesto), 'agregar' (se suma al monto) o 'sin' (no gravado).
    Devuelve base, impuesto, no_gravado y total en la moneda del documento."""
    monto = round(float(monto or 0), 2)
    t = float(tasa_pct or 0) / 100
    if modo == "sin" or t <= 0:
        return {"base": 0.0, "impuesto": 0.0, "no_gravado": monto, "total": monto}
    if sobre_total:                      # Bolivia: el impuesto es t% del importe total facturado
        total = monto if modo == "incluido" else round(monto / (1 - t), 2)
        imp = round(total * t, 2)
        return {"base": round(total - imp, 2), "impuesto": imp, "no_gravado": 0.0, "total": total}
    if modo == "incluido":
        base = round(monto / (1 + t), 2)
        return {"base": base, "impuesto": round(monto - base, 2), "no_gravado": 0.0, "total": monto}
    imp = round(monto * t, 2)
    return {"base": monto, "impuesto": imp, "no_gravado": 0.0, "total": round(monto + imp, 2)}


def a_local(im, tc):
    """Convierte a la moneda local multiplicando por el tipo de cambio; base + impuesto + no gravado = total."""
    tc = float(tc or 1)
    total = round(im["total"] * tc, 2)
    imp = round(im["impuesto"] * tc, 2)
    ng = round(im["no_gravado"] * tc, 2)
    return {"base": round(total - imp - ng, 2), "impuesto": imp, "no_gravado": ng, "total": total}


def _imp(p, d):
    im = importes(d["monto"], d["modo_imp"], d["tasa"], p.get("impuesto_sobre_total", False))
    return a_local(im, d["tc"])


# ------------------------------------------------------------------------------------------ utilidades
def _split_doc(texto):
    texto = (texto or "").strip()
    if "-" in texto:
        serie, numero = texto.split("-", 1)
        return serie.strip(), numero.strip()
    return "", texto


def _linea(p, cuenta, debe, haber):
    plan = dict(p["plan"])
    if cuenta not in plan:
        raise KeyError(f"La cuenta {cuenta} no está en el plan de {p['nombre']}.")
    return {"cuenta": cuenta, "nombre": plan[cuenta], "debe": round(debe, 2), "haber": round(haber, 2), "grupo": 1}


def _lineas(p, pares):
    return [_linea(p, c, d, h) for c, d, h in pares if abs(d) >= 0.005 or abs(h) >= 0.005]


def _contrapartida(p, forma, cuenta_credito):
    """A crédito va a la cuenta por cobrar/pagar; al contado, a banco o caja."""
    if forma == FORMAS[0]:
        return cuenta_credito
    return p["cuentas_base"]["banco"] if forma == FORMAS[1] else p["cuentas_base"]["caja"]


def _doc(p, tipo, d, comprobante, im, lineas, glosa):
    serie, numero = _split_doc(d.get("documento"))
    return {"tipo": tipo, "tipo_comprobante": comprobante, "serie": serie, "numero": numero, "fecha": d["fecha"],
            "contraparte_id": (d.get("id") or "").strip(), "contraparte_nombre": (d.get("nombre") or "").strip(),
            "moneda": d["moneda"], "tipo_cambio": float(d["tc"] or 1), "base": im["base"], "impuesto": im["impuesto"],
            "no_gravado": im["no_gravado"], "total": im["total"], "glosa": glosa, "asiento": lineas, "alertas": []}


def _nota_credito(doc):
    """Una nota de crédito invierte el sentido del asiento."""
    for l in doc["asiento"]:
        l["debe"], l["haber"] = l["haber"], l["debe"]
    doc["alertas"].append("Nota de crédito: el asiento está invertido respecto a una operación normal.")
    return doc


def finalizar(doc, p, comprobante=""):
    """Aplica los destinos del país (existencias, función) y los avisos, igual que el lector de facturas."""
    if comprobante == "Nota de crédito" and doc["asiento"]:
        _nota_credito(doc)
    doc = ia.agregar_destino(doc, p)
    doc = ia.agregar_destino_funcion(doc, p)
    if ia.pide_costo_venta(doc["asiento"], doc["tipo"], p):
        doc["alertas"].append("Venta de mercaderías: falta el asiento de costo de ventas. Ingresa el costo de lo vendido más abajo.")
    return doc


# ------------------------------------------------------------------------------------------ operaciones
def venta(p, d):
    cb, im = p["cuentas_base"], _imp(p, d)
    cobro = _contrapartida(p, d["forma"], cb["clientes"])
    iva = cb["iva_debito"]
    if d["forma"] != FORMAS[0] and cb.get("iva_debito_cobrado"):
        iva = cb["iva_debito_cobrado"]
    ls = _lineas(p, [(cobro, im["total"], 0), (iva, 0, im["impuesto"]), (d["cuenta"], 0, im["base"] + im["no_gravado"])])
    glosa = d["glosa"] or f"Venta {d.get('documento', '')}".strip()
    return finalizar(_doc(p, "venta", d, d["comprobante"], im, ls, glosa), p, d["comprobante"])


def compra(p, d):
    """Compra de mercadería o insumos, gasto o activo fijo: cambia solo la cuenta elegida."""
    cb, im = p["cuentas_base"], _imp(p, d)
    pago = _contrapartida(p, d["forma"], cb["proveedores"])
    iva = cb["iva_credito"]
    if d["forma"] == FORMAS[0] and cb.get("iva_credito_pendiente"):
        iva = cb["iva_credito_pendiente"]
    ls = _lineas(p, [(d["cuenta"], im["base"] + im["no_gravado"], 0), (iva, im["impuesto"], 0), (pago, 0, im["total"])])
    nombre_cuenta = dict(p["plan"])[d["cuenta"]]
    glosa = d["glosa"] or f"{nombre_cuenta} {d.get('documento', '')}".strip()
    return finalizar(_doc(p, "compra", d, d["comprobante"], im, ls, glosa), p, d["comprobante"])


def honorarios(p, d):
    """Honorarios con las retenciones del país que el usuario haya marcado (d['retenciones'] = {índice: True})."""
    cb, cfg, im = p["cuentas_base"], p["honorarios"], _imp(p, d)
    pares = [(cfg["cuenta"], im["base"] + im["no_gravado"], 0)]
    iva = cb["iva_credito"]
    if d["forma"] == FORMAS[0] and cb.get("iva_credito_pendiente"):
        iva = cb["iva_credito_pendiente"]
    pares.append((iva, im["impuesto"], 0))
    retenido = 0.0
    for i, r in enumerate(cfg["retenciones"]):
        if not d.get("retenciones", {}).get(i):
            continue
        sobre = im["impuesto"] if r["sobre"] == "impuesto" else im["base"] + im["no_gravado"]
        monto = round(sobre * r["pct"] / 100, 2)
        pares.append((r["cuenta"], 0, monto))
        retenido += monto
    pago = _contrapartida(p, d["forma"], cb["proveedores"])
    pares.append((pago, 0, round(im["total"] - retenido, 2)))
    glosa = d["glosa"] or f"Honorarios {d.get('documento', '')}".strip()
    tipo = "honorarios" if im["impuesto"] == 0 else "compra"   # con impuesto entra al registro de compras
    return finalizar(_doc(p, tipo, d, d["comprobante"], im, _lineas(p, pares), glosa), p, d["comprobante"])


def planilla(p, d):
    """d: fecha, glosa, bruto, aporte (empleador), retenciones {cuenta: monto}."""
    cfg = p["planilla"]
    bruto, aporte = round(float(d["bruto"]), 2), round(float(d.get("aporte") or 0), 2)
    ret = {c: round(float(m), 2) for c, m in (d.get("retenciones") or {}).items() if float(m or 0) > 0}
    neto = round(bruto - sum(ret.values()), 2)
    if neto <= 0:
        raise ValueError("Las retenciones no pueden ser mayores o iguales a la remuneración bruta.")
    pares = [(cfg["gasto"], bruto, 0)]
    if aporte > 0:
        pares += [(cfg["gasto_aportes"], aporte, 0), (cfg["aportes_pagar"], 0, aporte)]
    pares += [(c, 0, m) for c, m in ret.items()] + [(cfg["neto"], 0, neto)]
    costo = round(bruto + aporte, 2)
    im = {"base": costo, "impuesto": 0.0, "no_gravado": 0.0, "total": costo}
    dd = dict(d, documento=d.get("documento") or "PLA-" + d["fecha"][:7], moneda=d["moneda"], tc=1.0, nombre="Trabajadores")
    doc = _doc(p, "planilla", dd, "Planilla", im, _lineas(p, pares), d["glosa"] or f"Planilla {d['fecha'][:7]}")
    return finalizar(doc, p)


def _voucher(p, tipo_doc, d, pares, glosa):
    im = a_local({"base": 0.0, "impuesto": 0.0, "no_gravado": round(float(d["monto"]), 2), "total": round(float(d["monto"]), 2)}, d["tc"])
    im["base"] = 0.0
    doc = _doc(p, "otro", d, VOUCHER, im, _lineas(p, pares(im["total"])), glosa)
    return finalizar(doc, p)


def cobranza(p, d):
    cb = p["cuentas_base"]
    medio = _contrapartida(p, d["forma"], cb["banco"])
    return _voucher(p, "cobranza", d, lambda m: [(medio, m, 0), (cb["clientes"], 0, m)], d["glosa"] or "Cobranza a cliente")


def pago(p, d):
    """d['destino']: clave de la deuda que se paga (proveedores, remuneraciones o tributos)."""
    cb = p["cuentas_base"]
    cuenta = {"Proveedores": cb["proveedores"], "Remuneraciones por pagar": p["planilla"]["neto"],
              "Tributos por pagar": cb["tributos_pagar"]}[d["destino"]]
    medio = _contrapartida(p, d["forma"], cb["banco"])
    return _voucher(p, "pago", d, lambda m: [(cuenta, m, 0), (medio, 0, m)], d["glosa"] or f"Pago: {d['destino']}")


def aporte_capital(p, d):
    cb = p["cuentas_base"]
    medio = _contrapartida(p, d["forma"], cb["banco"])
    return _voucher(p, "capital", d, lambda m: [(medio, m, 0), (cb["capital"], 0, m)], d["glosa"] or "Aporte de capital")


def manual(p, d):
    """Asiento libre: se crea vacío y el usuario escribe las cuentas en el editor."""
    im = {"base": 0.0, "impuesto": 0.0, "no_gravado": 0.0, "total": 0.0}
    dd = dict(d, documento=d.get("documento") or "", moneda=d["moneda"], tc=1.0)
    doc = _doc(p, "otro", dd, "Asiento manual", im, [], d["glosa"] or "Asiento manual")
    doc["alertas"].append("Asiento manual: escribe las cuentas, el Debe y el Haber en la tabla antes de registrar.")
    return doc
