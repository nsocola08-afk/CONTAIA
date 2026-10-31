"""
Fichas por país: plan de cuentas, impuesto, regímenes y cómo agrupar las cuentas
en los estados financieros.

Para agregar un país nuevo: copia el bloque PERU, cámbiale los datos y regístralo
en el diccionario PAISES al final del archivo.
"""

# Agrupación de cuentas -> reportes (por prefijo de cuenta).
# Es la misma lógica para todos los países que usen una numeración tipo PCGE.
GRUPOS_PCGE = {
    # Estado de resultados
    "ventas": ["70"], "descuentos": ["74"], "otros_ingresos": ["73", "75", "76", "77"],
    "costo": ["60", "61", "69"], "personal": ["62"], "servicios": ["63"], "tributos": ["64"],
    "otros_gastos": ["65", "66"], "financieros": ["67"], "depreciacion": ["68"],
    # Situación financiera
    "efectivo": ["10"], "cxc": ["12", "13", "14", "16", "17", "18", "19"], "inventarios": ["2"],
    "fijo": ["3"], "impuestos": ["40"], "remuneraciones": ["41"],
    "cxp": ["42", "43", "44", "45", "46", "47", "48", "49"],
    "capital": ["50", "52", "56", "57", "58"], "acumulados": ["59"],
}

PERU = {
    "codigo": "PE",
    "nombre": "Perú",
    "plan_nombre": "PCGE (Plan Contable General Empresarial) – cuentas de uso frecuente",
    "id_fiscal": "RUC",
    "id_fiscal_largo": 11,
    "impuesto": "IGV",
    "tasa_impuesto": 0.18,
    "moneda": "PEN",
    "simbolo": "S/",
    "monedas_aceptadas": ["PEN", "USD", "EUR"],
    "inicio_ejercicio": "Enero",
    "cuenta_impuesto_compras_ventas": "40111",
    "reporte_impuestos": "PDT 621 / PLE",
    "regimenes": {
        # nombre: % referencial de pago a cuenta del Impuesto a la Renta sobre ingresos netos
        "Régimen General": 1.5,
        "Régimen MYPE Tributario": 1.0,
        "Régimen Especial (RER)": 1.5,
    },
    "actividades": ["Comercio", "Servicios", "Producción / industria", "Construcción", "Otra"],
    "tipos_comprobante": ["Factura", "Boleta de venta", "Recibo por honorarios", "Nota de crédito",
                          "Nota de débito", "Planilla", "Voucher / movimiento bancario", "Otro"],
    "grupos": GRUPOS_PCGE,
    "reglas_ia": """
- IGV 18% (16% IGV + 2% IPM). Cuenta del IGV: 40111.
- Compra con factura: Debe gasto o inventario por la base + Debe 40111 por el IGV; Haber 4212 por el total.
- Venta con factura o boleta: Debe 1212 por el total; Haber 40111 por el IGV; Haber 70xx por la base.
- Recibo por honorarios (4ta categoría): Debe 6321 (o la cuenta del servicio) por el honorario bruto;
  Haber 40172 por la retención del 8% SOLO si el recibo indica retención o supera S/ 1,500;
  Haber 4212 por el neto. No hay IGV.
- Planilla: Debe 6211 remuneraciones + Debe 6271 EsSalud (9% a cargo del empleador);
  Haber 4031 EsSalud por pagar; Haber 4032 (ONP 13%) o 407 (AFP) por lo retenido al trabajador;
  Haber 4111 por el neto a pagar. Las partidas deben cuadrar.
- Si la factura tiene detracción (servicios o bienes sujetos a SPOT) o percepción/retención de IGV,
  agrega una alerta; no inventes una cuenta que no esté en el plan.
- Si el documento está en dólares, convierte a soles con el tipo de cambio del documento; si no figura,
  agrégalo como alerta y usa 0 en tipo_cambio.
- Nota de crédito: invierte el sentido del asiento de la venta o de la compra.
""",
    "plan": [
        ("101", "Caja"),
        ("1041", "Cuentas corrientes operativas"),
        ("1212", "Facturas, boletas y otros comprobantes por cobrar – Emitidas en cartera"),
        ("1411", "Adelantos de remuneraciones al personal"),
        ("1699", "Otras cuentas por cobrar diversas"),
        ("2011", "Mercaderías manufacturadas"),
        ("2091", "Existencias por recibir"),
        ("332", "Edificaciones"),
        ("333", "Maquinarias y equipos de explotación"),
        ("334", "Unidades de transporte"),
        ("335", "Muebles y enseres"),
        ("336", "Equipos diversos (cómputo, etc.)"),
        ("391", "Depreciación acumulada"),
        ("40111", "IGV – Cuenta propia"),
        ("40112", "IGV – Servicios prestados por no domiciliados"),
        ("40171", "Impuesto a la renta – Renta de tercera categoría"),
        ("40172", "Impuesto a la renta – Renta de cuarta categoría (retenciones)"),
        ("40173", "Impuesto a la renta – Renta de quinta categoría"),
        ("4031", "EsSalud por pagar"),
        ("4032", "ONP por pagar"),
        ("407", "Administradoras de fondos de pensiones (AFP) por pagar"),
        ("4111", "Sueldos y salarios por pagar"),
        ("4151", "Beneficios sociales por pagar (CTS, gratificaciones)"),
        ("4212", "Facturas, boletas y otros comprobantes por pagar – Emitidas"),
        ("4511", "Préstamos de instituciones financieras"),
        ("4699", "Otras cuentas por pagar diversas"),
        ("5011", "Capital social – Acciones o participaciones"),
        ("5811", "Reservas legales"),
        ("5911", "Resultados acumulados – Utilidades acumuladas"),
        ("5921", "Resultados acumulados – Pérdidas acumuladas"),
        ("60111", "Compra de mercaderías – Terceros"),
        ("6091", "Costos vinculados con las compras"),
        ("6111", "Variación de existencias – Mercaderías"),
        ("6211", "Sueldos y salarios"),
        ("6212", "Gratificaciones"),
        ("6271", "Régimen de prestaciones de salud (EsSalud)"),
        ("6291", "Compensación por tiempo de servicios"),
        ("6311", "Transporte de carga"),
        ("6312", "Gastos de viaje"),
        ("6321", "Asesoría y consultoría"),
        ("6341", "Mantenimiento y reparaciones"),
        ("6352", "Alquiler de edificaciones"),
        ("6353", "Alquiler de maquinarias y equipos"),
        ("6361", "Energía eléctrica"),
        ("6362", "Gas"),
        ("6363", "Agua"),
        ("6364", "Teléfono e internet"),
        ("6371", "Publicidad"),
        ("6391", "Otros servicios (gastos bancarios, software, etc.)"),
        ("6411", "Tributos – IGV no deducible"),
        ("6441", "Tributos municipales"),
        ("6599", "Otros gastos de gestión"),
        ("6711", "Intereses por préstamos"),
        ("6811", "Depreciación de inmuebles, maquinaria y equipo"),
        ("70111", "Ventas de mercaderías – Terceros"),
        ("70411", "Ventas de servicios – Terceros"),
        ("7411", "Descuentos y rebajas concedidos"),
        ("7591", "Otros ingresos de gestión"),
        ("7711", "Ingresos financieros"),
    ],
}

PAISES = {"PE": PERU}

# Países anunciados en el selector pero todavía sin ficha (se habilitan agregando su bloque arriba).
PROXIMAMENTE = ["Colombia", "México", "Chile", "Argentina", "Ecuador", "Bolivia"]


def get_pais(codigo):
    return PAISES[codigo]


def plan_dict(codigo):
    return dict(PAISES[codigo]["plan"])
