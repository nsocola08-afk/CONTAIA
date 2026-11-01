"""Respuestas simuladas para probar la app sin gastar en AWS (solo si CONTAIA_MOCK=1)."""
import random

import paises


def respuesta_falsa(nombre, empresa, pista=""):
    cb = paises.get_pais(empresa["pais"])["cuentas_base"]
    tasa = paises.get_pais(empresa["pais"])["tasa_impuesto"] or 0.18
    base = round(random.choice([500, 1200, 2500, 8000]), 2)
    igv = round(base * tasa, 2)
    total = round(base + igv, 2)
    n = "".join(random.choices("0123456789", k=5))
    mi = empresa["id_fiscal"]
    if "venta" in nombre.lower():
        return {"tipo": "venta", "tipo_comprobante": "Factura", "serie": "F001", "numero": n, "fecha": "2026-10-15",
                "emisor_id": mi, "emisor_nombre": empresa["nombre"], "receptor_id": "20512345678",
                "receptor_nombre": "Cliente de Prueba S.A.C.", "moneda_original": "PEN", "tipo_cambio": 0,
                "base_imponible": base, "impuesto": igv, "no_gravado": 0, "total": total, "glosa": "Venta de mercaderías",
                "asiento": [{"cuenta": cb["clientes"], "nombre": "x", "debe": total, "haber": 0},
                            {"cuenta": cb["iva_debito"], "nombre": "x", "debe": 0, "haber": igv},
                            {"cuenta": cb["ventas"], "nombre": "x", "debe": 0, "haber": base}], "alertas": []}
    cuenta_compra = cb["compras"]
    if "gasto" in pista.lower():
        g = paises.get_pais(empresa["pais"])
        cuenta_compra = next(c for c, _ in g["plan"] if c.startswith(("6362", "5135", "5303", "603.52")))
    return {"tipo": "compra", "tipo_comprobante": "Factura", "serie": "F002", "numero": n, "fecha": "2026-10-10",
            "emisor_id": "20100070970", "emisor_nombre": "Proveedor de Prueba S.A.", "receptor_id": mi,
            "receptor_nombre": empresa["nombre"], "moneda_original": "PEN", "tipo_cambio": 0,
            "base_imponible": base, "impuesto": igv, "no_gravado": 0, "total": total, "glosa": "Compra de mercaderías",
            "asiento": [{"cuenta": cuenta_compra, "nombre": "x", "debe": base, "haber": 0},
                        {"cuenta": cb["iva_credito"], "nombre": "x", "debe": igv, "haber": 0},
                        {"cuenta": cb["proveedores"], "nombre": "x", "debe": 0, "haber": total}],
            "alertas": ["Factura con posible detracción (prueba)."]}


def documento_falso(texto, empresa, pais, hoy):
    """Simula a Claude en modo texto (solo pruebas): arma un asiento sencillo según palabras clave."""
    import re
    cb = pais["cuentas_base"]
    cv = pais.get("costo_venta") or {}
    t = texto.lower()
    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", t.replace(" ", ""))]
    if not nums:
        return {"pregunta": "No encontré el monto. ¿Por cuánto fue la operación?", "asiento": []}
    m = nums[0]
    inv = cv.get("inventario") or cb["compras"]
    caja = cb.get("caja", cb["banco"])
    base = {"tipo": "otro", "tipo_comprobante": "", "serie": "", "numero": "", "fecha": hoy, "emisor_id": "", "emisor_nombre": "",
            "receptor_id": "", "receptor_nombre": "", "moneda_original": empresa["moneda"], "tipo_cambio": 0, "base_imponible": 0,
            "impuesto": 0, "no_gravado": m, "total": m, "glosa": texto[:80], "alertas": ["Pago en efectivo (supuesto de prueba)."], "pregunta": ""}
    if "aporte" in t:
        e = nums[1] if len(nums) > 1 else 0
        lin = [(caja, m, 0)] + ([(inv, e, 0)] if e else []) + [(cb["capital"], 0, m + e)]
        base["total"] = m + e
    elif "vend" in t:
        tasa = pais["tasa_impuesto"] or 0.18
        b = round(m / (1 + tasa), 2)
        base.update(tipo="venta", tipo_comprobante="Factura", base_imponible=b, impuesto=round(m - b, 2), no_gravado=0, emisor_id=empresa["id_fiscal"])
        lin = [(caja, m, 0), (cb["iva_debito"], 0, round(m - b, 2)), (cb["ventas"], 0, b)]
    elif "compr" in t:
        tasa = pais["tasa_impuesto"] or 0.18
        b = round(m / (1 + tasa), 2)
        base.update(tipo="compra", tipo_comprobante="Factura", base_imponible=b, impuesto=round(m - b, 2), no_gravado=0, receptor_id=empresa["id_fiscal"])
        lin = [(cb["compras"], b, 0), (cb["iva_credito"], round(m - b, 2), 0), (caja, 0, m)]
    else:
        return {"pregunta": "No pude entender la operación (prueba).", "asiento": []}
    base["asiento"] = [{"cuenta": c, "nombre": "x", "debe": d, "haber": h, "grupo": 1} for c, d, h in lin]
    return base
