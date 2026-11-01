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


def operacion_falsa(texto, empresa, pais, hoy):
    """Interpretación simulada para pruebas: busca palabras clave y el primer número."""
    import re
    t = texto.lower()
    nums = re.findall(r"\d+(?:[.,]\d+)?", t.replace(" ", ""))
    monto = float(nums[0].replace(",", ".")) if nums else 0
    tipo = ("venta" if "vend" in t else "compra" if "compr" in t else "gasto" if "gast" in t else
            "cobranza" if "cobr" in t else "pago" if "pagu" in t else "planilla" if "planilla" in t else "no_claro")
    return {"tipo": tipo, "pregunta": "", "fecha": hoy, "monto": monto, "impuesto": "incluido",
            "forma": "credito" if "crédito" in t or "credito" in t else "caja", "vence": None, "tercero_id": "", "tercero_nombre": "",
            "comprobante": "Factura", "documento": "", "se_vende": "mercaderias", "cuenta": pais["cuentas_base"]["compras"],
            "destino": "Proveedores", "bruto": monto, "moneda": empresa["moneda"], "tipo_cambio": 0,
            "glosa": texto[:80], "supuestos": ["El monto incluye impuesto (supuesto de prueba)."]}
