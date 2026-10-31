"""
Fichas por país: plan de cuentas, impuesto, regímenes, reglas para la IA y cómo agrupar las cuentas
en los estados financieros.

Tokens de agrupación: "70" = todas las cuentas que empiezan con 70; "=603" = solo la cuenta exacta 603.

Para agregar un país nuevo: copia un bloque, cambia los datos y regístralo en PAISES al final.
IMPORTANTE: antes de habilitar un país, verifica tasas y retenciones vigentes con un contador local.
"""

AVISO_BASE = ("Las reglas y cuentas son una base de trabajo: un contador local debe revisar los asientos, "
              "sobre todo retenciones, percepciones y casos especiales.")

# ---------------------------------------------------------------------------------------------- PERÚ
PERU = {
    "codigo": "PE", "nombre": "Perú",
    "plan_nombre": "PCGE (Plan Contable General Empresarial) – cuentas de uso frecuente",
    "id_fiscal": "RUC", "id_regex": r"\d{11}", "id_ejemplo": "20123456789",
    "impuesto": "IGV", "tasa_impuesto": 0.18, "moneda": "PEN", "simbolo": "S/",
    "inicio_ejercicio": "Enero", "reporte_impuestos": "PDT 621 / PLE",
    "regimenes": {"Régimen General": 1.5, "Régimen MYPE Tributario": 1.0, "Régimen Especial (RER)": 1.5},
    "pago_cuenta_label": "Renta pago a cuenta",
    "actividades": ["Comercio", "Servicios", "Producción / industria", "Construcción", "Otra"],
    "aviso": AVISO_BASE,
    "grupos": {
        "ventas": ["70"], "descuentos": ["74"], "otros_ingresos": ["73", "75", "76", "77"],
        "costo": ["60", "61", "69"], "personal": ["62"], "servicios": ["63"], "tributos": ["64"],
        "otros_gastos": ["65", "66"], "financieros": ["67"], "depreciacion": ["68"],
        "efectivo": ["10"], "cxc": ["12", "13", "14", "16", "17", "18", "19"], "inventarios": ["2"], "fijo": ["3"],
        "impuestos": ["40"], "remuneraciones": ["41"], "cxp": ["42", "43", "44", "45", "46", "47", "48", "49"],
        "capital": ["50", "52", "56", "57", "58"], "acumulados": ["59"], "resultado": ["6", "7"],
    },
    "nomina": {"gasto": ["62", "6321"], "aportes": ["4031", "4032", "407", "40172"], "neto": ["4111", "4212"]},
    "columnas_nomina": [("EsSalud", ["4031"]), ("ONP/AFP", ["4032", "407"])],
    "cuentas_base": {"clientes": "1212", "proveedores": "4212", "iva_credito": "40111", "iva_debito": "40111",
                     "ventas": "70111", "compras": "60111", "capital": "5011", "banco": "1041"},
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
- Si la factura tiene detracción (SPOT), percepción o retención de IGV, agrega una alerta; no inventes cuentas.
- Si el documento está en dólares, convierte a soles con el tipo de cambio del documento; si no figura,
  agrégalo como alerta y usa 0 en tipo_cambio.
- Nota de crédito: invierte el sentido del asiento de la venta o de la compra.
""",
    "plan": [
        ("101", "Caja"), ("1041", "Cuentas corrientes operativas"),
        ("1212", "Facturas, boletas y otros comprobantes por cobrar – Emitidas en cartera"),
        ("1411", "Adelantos de remuneraciones al personal"), ("1699", "Otras cuentas por cobrar diversas"),
        ("2011", "Mercaderías manufacturadas"), ("2091", "Existencias por recibir"),
        ("332", "Edificaciones"), ("333", "Maquinarias y equipos de explotación"), ("334", "Unidades de transporte"),
        ("335", "Muebles y enseres"), ("336", "Equipos diversos (cómputo, etc.)"), ("391", "Depreciación acumulada"),
        ("40111", "IGV – Cuenta propia"), ("40112", "IGV – Servicios prestados por no domiciliados"),
        ("40171", "Impuesto a la renta – Renta de tercera categoría"),
        ("40172", "Impuesto a la renta – Renta de cuarta categoría (retenciones)"),
        ("40173", "Impuesto a la renta – Renta de quinta categoría"),
        ("4031", "EsSalud por pagar"), ("4032", "ONP por pagar"), ("407", "Administradoras de fondos de pensiones (AFP) por pagar"),
        ("4111", "Sueldos y salarios por pagar"), ("4151", "Beneficios sociales por pagar (CTS, gratificaciones)"),
        ("4212", "Facturas, boletas y otros comprobantes por pagar – Emitidas"),
        ("4511", "Préstamos de instituciones financieras"), ("4699", "Otras cuentas por pagar diversas"),
        ("5011", "Capital social – Acciones o participaciones"), ("5811", "Reservas legales"),
        ("5911", "Resultados acumulados – Utilidades acumuladas"), ("5921", "Resultados acumulados – Pérdidas acumuladas"),
        ("60111", "Compra de mercaderías – Terceros"), ("6091", "Costos vinculados con las compras"),
        ("6111", "Variación de existencias – Mercaderías"), ("6211", "Sueldos y salarios"), ("6212", "Gratificaciones"),
        ("6271", "Régimen de prestaciones de salud (EsSalud)"), ("6291", "Compensación por tiempo de servicios"),
        ("6311", "Transporte de carga"), ("6312", "Gastos de viaje"), ("6321", "Asesoría y consultoría"),
        ("6341", "Mantenimiento y reparaciones"), ("6352", "Alquiler de edificaciones"),
        ("6353", "Alquiler de maquinarias y equipos"), ("6361", "Energía eléctrica"), ("6362", "Gas"), ("6363", "Agua"),
        ("6364", "Teléfono e internet"), ("6371", "Publicidad"), ("6391", "Otros servicios (gastos bancarios, software, etc.)"),
        ("6411", "Tributos – IGV no deducible"), ("6441", "Tributos municipales"), ("6599", "Otros gastos de gestión"),
        ("6711", "Intereses por préstamos"), ("6811", "Depreciación de inmuebles, maquinaria y equipo"),
        ("70111", "Ventas de mercaderías – Terceros"), ("70411", "Ventas de servicios – Terceros"),
        ("7411", "Descuentos y rebajas concedidos"), ("7591", "Otros ingresos de gestión"), ("7711", "Ingresos financieros"),
    ],
}

# ------------------------------------------------------------------------------------------ COLOMBIA
COLOMBIA = {
    "codigo": "CO", "nombre": "Colombia",
    "plan_nombre": "PUC (Plan Único de Cuentas, Decreto 2650/1993) – cuentas de uso frecuente",
    "id_fiscal": "NIT", "id_regex": r"\d{9,10}", "id_ejemplo": "900123456-7",
    "impuesto": "IVA", "tasa_impuesto": 0.19, "moneda": "COP", "simbolo": "$",
    "inicio_ejercicio": "Enero", "reporte_impuestos": "Formulario 300 (IVA) / 350 (retención)",
    "regimenes": {"Régimen ordinario (responsable de IVA)": None, "Régimen Simple de Tributación (RST)": None},
    "pago_cuenta_label": "Pago a cuenta",
    "actividades": ["Comercio", "Servicios", "Producción / industria", "Construcción", "Otra"],
    "aviso": AVISO_BASE + " Subcuentas 240801 y 240802 propuestas para separar IVA generado y descontable.",
    "grupos": {
        "ventas": ["4135"], "descuentos": ["4175"], "otros_ingresos": ["42"],
        "costo": ["61", "62"], "personal": ["5105"], "servicios": ["5110", "5120", "5135", "5140", "5145"],
        "tributos": ["5115"], "otros_gastos": ["5195"], "financieros": ["5305"], "depreciacion": ["5160"],
        "efectivo": ["11"], "cxc": ["1305"], "inventarios": ["14"], "fijo": ["15"],
        "impuestos": ["1355", "2408", "2365", "2367", "2368"], "remuneraciones": ["25", "2370"],
        "cxp": ["2105", "2205", "2335"], "capital": ["31", "33"], "acumulados": ["37"], "resultado": ["4", "5", "6", "7"],
    },
    "nomina": {"gasto": ["5105", "5110"], "aportes": ["2370"], "neto": ["2505", "2335"]},
    "columnas_nomina": [("Retenciones y aportes de nómina", ["2370"])],
    "cuentas_base": {"clientes": "1305", "proveedores": "2205", "iva_credito": "240802", "iva_debito": "240801",
                     "ventas": "4135", "compras": "6205", "capital": "3105", "banco": "1110"},
    "reglas_ia": """
- IVA: tarifa general 19% (también 5% y 0%/exento según el bien). Usa la tarifa que muestre la factura.
- El IVA va en la cuenta 2408: IVA generado (ventas) a 240801 por el crédito; IVA descontable (compras) a 240802 por el débito.
- Compra: Debe gasto o inventario (6205 compras de mercancías, 5xxx gasto) por la base + Debe 240802 por el IVA;
  Haber 2205 proveedores (o 2335 costos y gastos por pagar si es un servicio u honorarios) por el total.
- Venta: Debe 1305 clientes por el total; Haber 240801 por el IVA; Haber 4135 por la base.
- Retención en la fuente: si el documento o su soporte muestra retenciones practicadas, regístralas:
  las que practica la empresa a un proveedor van al Haber de 2365 (renta), 2367 (ReteIVA) o 2368 (ReteICA);
  las que le practican a la empresa en una venta van al Debe de 135515 (renta), 135517 (ReteIVA) o 135518 (ReteICA).
  NO calcules porcentajes por tu cuenta: si no están indicadas, agrega una alerta para verificarlas.
- Nómina: Debe 5105 gastos de personal; Haber 2505 salarios por pagar (neto);
  Haber 2370 retenciones y aportes de nómina (salud, pensión, parafiscales). Las prestaciones (2510, 2515, 2530, 2540)
  solo si el documento las detalla.
- Moneda funcional COP. Si el documento está en otra moneda, convierte con la TRM del documento; si no figura, alerta.
- Nota crédito: invierte el asiento de la venta o la compra.
""",
    "plan": [
        ("1105", "Caja"), ("1110", "Bancos"), ("1305", "Clientes"),
        ("135515", "Retención en la fuente (anticipo de renta a favor)"),
        ("135517", "Impuesto a las ventas retenido (a favor)"), ("135518", "Impuesto de industria y comercio retenido (a favor)"),
        ("1435", "Mercancías no fabricadas por la empresa"), ("1524", "Equipo de oficina"),
        ("1528", "Equipo de computación y comunicación"), ("1592", "Depreciación acumulada"),
        ("2105", "Obligaciones financieras – Bancos nacionales"), ("2205", "Proveedores nacionales"),
        ("2335", "Costos y gastos por pagar"), ("2365", "Retención en la fuente por pagar"),
        ("2367", "Impuesto a las ventas retenido por pagar"), ("2368", "Impuesto de industria y comercio retenido por pagar"),
        ("240801", "IVA generado (impuesto sobre las ventas por pagar)"),
        ("240802", "IVA descontable (impuesto sobre las ventas por pagar)"),
        ("2370", "Retenciones y aportes de nómina"), ("2505", "Salarios por pagar"), ("2510", "Cesantías consolidadas"),
        ("2515", "Intereses sobre cesantías"), ("2530", "Primas de servicios"), ("2540", "Vacaciones consolidadas"),
        ("3105", "Capital suscrito y pagado"), ("3305", "Reservas obligatorias"),
        ("3705", "Utilidades acumuladas"), ("3710", "Pérdidas acumuladas"),
        ("4135", "Ingresos – Comercio al por mayor y al por menor"), ("4175", "Devoluciones, rebajas y descuentos en ventas"),
        ("4210", "Ingresos financieros"), ("4295", "Otros ingresos diversos"),
        ("5105", "Gastos de personal"), ("5110", "Honorarios"), ("5115", "Impuestos"), ("5120", "Arrendamientos"),
        ("5135", "Servicios"), ("5140", "Gastos legales"), ("5145", "Mantenimiento y reparaciones"),
        ("5160", "Depreciaciones"), ("5195", "Gastos diversos"), ("5305", "Gastos financieros"),
        ("6135", "Costo de ventas – Comercio al por mayor y al por menor"), ("6205", "Compras de mercancías"),
    ],
}

# ------------------------------------------------------------------------------------------- MÉXICO
MEXICO = {
    "codigo": "MX", "nombre": "México",
    "plan_nombre": "Catálogo basado en el Código Agrupador del SAT (Anexo 24) – cuentas de uso frecuente",
    "id_fiscal": "RFC", "id_regex": r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}", "id_ejemplo": "ABC010101XX1",
    "impuesto": "IVA", "tasa_impuesto": 0.16, "moneda": "MXN", "simbolo": "$",
    "inicio_ejercicio": "Enero", "reporte_impuestos": "Declaración mensual SAT / DIOT",
    "regimenes": {"Persona moral – régimen general": None, "Persona física con actividad empresarial": None,
                  "RESICO persona física": None},
    "pago_cuenta_label": "Pago provisional",
    "actividades": ["Comercio", "Servicios", "Producción / industria", "Construcción", "Otra"],
    "aviso": AVISO_BASE + " Tasa del 8% en la franja fronteriza solo si la factura la muestra.",
    "grupos": {
        "ventas": ["401"], "descuentos": ["402"], "otros_ingresos": [], "costo": ["501"],
        "personal": ["603.01", "603.26"], "servicios": ["603.45", "603.52"], "tributos": [],
        "otros_gastos": ["=601", "=602", "=603"], "financieros": ["701"], "depreciacion": [],
        "efectivo": ["101", "102"], "cxc": ["105", "106", "107", "108", "120"], "inventarios": ["115", "116"],
        "fijo": ["15", "16", "17"], "impuestos": ["118", "119", "208", "209", "213", "216"],
        "remuneraciones": ["210", "211"], "cxp": ["201", "202", "203", "205", "206", "214", "215"],
        "capital": ["301", "302", "303"], "acumulados": ["304"], "resultado": ["4", "5", "6", "7"],
    },
    "nomina": {"gasto": ["603.01", "603.26", "=603"], "aportes": ["216.01", "216.11", "211.01"], "neto": ["210", "201"]},
    "columnas_nomina": [("ISR retenido y cuotas IMSS", ["216.01", "216.11", "211.01"])],
    "cuentas_base": {"clientes": "105.01", "proveedores": "201", "iva_credito": "118.01", "iva_debito": "209.01",
                     "ventas": "401.01", "compras": "501", "capital": "301", "banco": "102"},
    "reglas_ia": """
- IVA tarifa general 16% (8% en franja fronteriza y 0% para algunos bienes: usa la tasa que muestre el CFDI).
- Compra (CFDI recibido): Debe gasto o inventario por el subtotal; Debe 118.01 IVA acreditable pagado si se pagó de contado,
  o Debe 119.01 IVA acreditable pendiente de pago si queda por pagar (PPD); Haber 201 Proveedores (o 102 Bancos si ya se pagó).
- Venta (CFDI emitido): Debe 105.01 Clientes por el total; Haber 401.01 por el subtotal;
  Haber 209.01 IVA trasladado no cobrado (si queda por cobrar) o 208.01 IVA trasladado cobrado (si ya se cobró).
- Honorarios o arrendamiento de persona física a persona moral: la empresa retiene ISR 10% y 2/3 del IVA trasladado.
  Ejemplo con subtotal 10,000: IVA 1,600; retención ISR 1,000; retención IVA 1,066.67.
  Registra: Haber 216 (ISR retenido) y Haber 216.10 (IVA retenido), y el neto a pagar en 201. Solo si el CFDI muestra la retención.
- Nómina: Debe 603.01 sueldos y salarios + Debe 603.26 cuotas IMSS patronal; Haber 216.01 ISR retenido por sueldos,
  Haber 216.11 retenciones de IMSS al trabajador, Haber 211.01 IMSS patronal por pagar, Haber 210 sueldos por pagar (neto).
- Gastos de administración sin subcuenta específica: usa 603. Moneda funcional MXN; si el CFDI está en otra moneda,
  usa el tipo de cambio del documento; si no figura, alerta.
- Nota de crédito (CFDI de egreso): invierte el asiento de la venta o la compra.
""",
    "plan": [
        ("101", "Caja"), ("102", "Bancos"), ("105.01", "Clientes nacionales"), ("107", "Deudores diversos"),
        ("115", "Inventario"), ("118.01", "IVA acreditable pagado"), ("119.01", "IVA acreditable pendiente de pago"),
        ("120", "Anticipo a proveedores"), ("152", "Edificios"), ("153", "Maquinaria y equipo"),
        ("154", "Automóviles, autobuses, camiones de carga y remolques"), ("155", "Mobiliario y equipo de oficina"),
        ("156", "Equipo de cómputo"), ("171", "Depreciación acumulada de activos fijos"),
        ("201", "Proveedores"), ("205", "Acreedores diversos a corto plazo"), ("208.01", "IVA trasladado cobrado"),
        ("209.01", "IVA trasladado no cobrado"), ("210", "Provisión de sueldos y salarios por pagar"),
        ("211.01", "Provisión de IMSS patronal por pagar"), ("213.01", "IVA por pagar"),
        ("216", "Impuestos retenidos (ISR de honorarios y arrendamiento)"),
        ("216.01", "ISR retenido por sueldos y salarios"), ("216.10", "IVA retenido"),
        ("216.11", "Retenciones de IMSS a los trabajadores"),
        ("301", "Capital social"), ("303", "Reserva legal"), ("304", "Resultado de ejercicios anteriores"),
        ("401.01", "Ventas y/o servicios gravados a la tasa general"),
        ("402", "Devoluciones, descuentos o bonificaciones sobre ingresos"), ("501", "Costo de venta y/o servicio"),
        ("601", "Gastos generales"), ("602", "Gastos de venta"), ("603", "Gastos de administración (otros)"),
        ("603.01", "Sueldos y salarios"), ("603.26", "Cuotas al IMSS"),
        ("603.45", "Arrendamiento a personas físicas residentes nacionales"), ("603.52", "Energía eléctrica"),
        ("701", "Gastos financieros"),
    ],
}


# ---------------------------------------------------------------- plan estándar (CL, AR, EC, BO)
def _plan_estandar(iva_credito, iva_debito, impuestos_x_pagar, remun_x_pagar, leyes_sociales):
    return [
        ("1101", "Caja"), ("1102", "Bancos"), ("1201", "Clientes (cuentas por cobrar comerciales)"),
        ("1202", "Anticipos y otras cuentas por cobrar"), ("1301", "Mercaderías (inventario)"),
        ("1401", iva_credito), ("1402", "Impuestos a favor, anticipos y retenciones sufridas"),
        ("1501", "Edificios"), ("1502", "Maquinaria y equipo"), ("1503", "Vehículos"),
        ("1504", "Muebles y equipos de oficina"), ("1505", "Equipos de computación"), ("1599", "Depreciación acumulada"),
        ("2101", "Proveedores"), ("2102", "Honorarios y otras cuentas por pagar"), ("2201", iva_debito),
        ("2202", impuestos_x_pagar), ("2301", remun_x_pagar), ("2302", leyes_sociales),
        ("2401", "Préstamos bancarios"), ("3101", "Capital"), ("3201", "Reservas"), ("3301", "Resultados acumulados"),
        ("4101", "Ventas de mercaderías"), ("4102", "Ventas de servicios"), ("4201", "Descuentos y devoluciones sobre ventas"),
        ("4301", "Otros ingresos"), ("4401", "Ingresos financieros"),
        ("5101", "Costo de ventas / compras de mercaderías"), ("5201", "Sueldos y salarios"),
        ("5202", "Leyes sociales (aportes del empleador)"), ("5301", "Honorarios y servicios profesionales"),
        ("5302", "Arriendos"), ("5303", "Servicios básicos (luz, agua, internet)"), ("5304", "Publicidad y marketing"),
        ("5305", "Mantenimiento y reparaciones"), ("5306", "Gastos bancarios y otros servicios"),
        ("5401", "Impuestos y tasas"), ("5501", "Otros gastos de administración y ventas"),
        ("5601", "Gastos financieros"), ("5701", "Depreciación"),
    ]


_GRUPOS_ESTANDAR = {
    "ventas": ["41"], "descuentos": ["42"], "otros_ingresos": ["43", "44"], "costo": ["51"],
    "personal": ["52"], "servicios": ["53"], "tributos": ["54"], "otros_gastos": ["55"],
    "financieros": ["56"], "depreciacion": ["57"],
    "efectivo": ["11"], "cxc": ["12"], "inventarios": ["13"], "fijo": ["15"],
    "impuestos": ["14", "22"], "remuneraciones": ["23"], "cxp": ["21", "24"],
    "capital": ["31", "32"], "acumulados": ["33"], "resultado": ["4", "5"],
}
_NOMINA_ESTANDAR = {"gasto": ["52", "5301"], "aportes": ["2302", "2202"], "neto": ["2301", "2102"]}
_BASE_ESTANDAR = {"clientes": "1201", "proveedores": "2101", "iva_credito": "1401", "iva_debito": "2201",
                  "ventas": "4101", "compras": "5101", "capital": "3101", "banco": "1102"}
_ACTIVIDADES = ["Comercio", "Servicios", "Producción / industria", "Construcción", "Otra"]
_AVISO_ESTANDAR = (AVISO_BASE + " Este país no usa un plan único obligatorio para todas las empresas: se aplica un plan "
                   "estándar de uso común que puedes adaptar con tu contador.")

CHILE = {
    "codigo": "CL", "nombre": "Chile", "plan_nombre": "Plan estándar de cuentas (uso común, sin plan oficial único)",
    "id_fiscal": "RUT", "id_regex": r"\d{7,8}[0-9K]", "id_ejemplo": "76.123.456-K",
    "impuesto": "IVA", "tasa_impuesto": 0.19, "moneda": "CLP", "simbolo": "$",
    "inicio_ejercicio": "Enero", "reporte_impuestos": "Formulario 29 (SII)",
    "regimenes": {"Régimen general (14 A)": None, "Pro Pyme general (14 D N°3)": None,
                  "Pro Pyme transparente (14 D N°8)": None},
    "pago_cuenta_label": "PPM", "actividades": _ACTIVIDADES, "aviso": _AVISO_ESTANDAR,
    "grupos": _GRUPOS_ESTANDAR, "nomina": _NOMINA_ESTANDAR, "cuentas_base": _BASE_ESTANDAR,
    "columnas_nomina": [("Cotizaciones e impuesto retenido", ["2302", "2202"])],
    "plan": _plan_estandar("IVA crédito fiscal", "IVA débito fiscal", "Impuestos por pagar y retenciones (honorarios, impuesto único)",
                           "Remuneraciones por pagar (líquidos)", "Cotizaciones previsionales por pagar"),
    "reglas_ia": """
- IVA 19%. Compra con factura afecta: Debe gasto o inventario por el neto + Debe 1401 IVA crédito fiscal;
  Haber 2101 por el total. Venta: Debe 1201 por el total; Haber 2201 IVA débito fiscal; Haber 4101/4102 por el neto.
- Factura exenta o no afecta: sin IVA; el monto va en no_gravado.
- Boleta de honorarios (persona natural): NO lleva IVA; lleva retención de segunda categoría que en 2026 es 15,25% del bruto.
  Asiento: Debe 5301 por el bruto; Haber 2202 por la retención (15,25%); Haber 2102 por el líquido.
  Si la boleta muestra otro porcentaje, usa el del documento y agrega una alerta.
- Remuneraciones: Debe 5201 sueldos + Debe 5202 aportes del empleador; Haber 2301 líquido a pagar;
  Haber 2302 cotizaciones por pagar; Haber 2202 impuesto único retenido, si el documento lo muestra.
- Si el documento está en moneda extranjera, convierte a CLP con el tipo de cambio del documento; si no figura, alerta.
- Nota de crédito: invierte el asiento de la venta o la compra.
""",
}

ARGENTINA = {
    "codigo": "AR", "nombre": "Argentina", "plan_nombre": "Plan estándar de cuentas (uso común, sin plan oficial único)",
    "id_fiscal": "CUIT", "id_regex": r"\d{11}", "id_ejemplo": "30-12345678-9",
    "impuesto": "IVA", "tasa_impuesto": 0.21, "moneda": "ARS", "simbolo": "$",
    "inicio_ejercicio": "Enero", "reporte_impuestos": "Libro IVA Digital / DDJJ IVA (ARCA)",
    "regimenes": {"Responsable inscripto": None, "Monotributista": None},
    "pago_cuenta_label": "Pago a cuenta", "actividades": _ACTIVIDADES, "aviso": _AVISO_ESTANDAR,
    "grupos": _GRUPOS_ESTANDAR, "nomina": _NOMINA_ESTANDAR, "cuentas_base": _BASE_ESTANDAR,
    "columnas_nomina": [("Cargas sociales y retenciones", ["2302", "2202"])],
    "plan": _plan_estandar("IVA crédito fiscal", "IVA débito fiscal", "Impuestos por pagar, retenciones y percepciones",
                           "Sueldos y jornales a pagar", "Cargas sociales a pagar"),
    "reglas_ia": """
- IVA alícuota general 21% (también 10,5% y 27%, exento o no gravado: usa la que muestre la factura).
- Factura A (discrimina IVA): Debe gasto o inventario por el neto + Debe 1401 IVA crédito fiscal; Haber 2101 por el total.
  Factura B o C que no discrimina IVA: el total completo es gasto; no hay crédito fiscal.
- Venta: Debe 1201 por el total; Haber 2201 IVA débito fiscal; Haber 4101/4102 por el neto.
- Percepciones y retenciones (IVA, Ganancias, Ingresos Brutos): si el comprobante las muestra, las sufridas van al Debe de 1402
  y las practicadas al Haber de 2202. No calcules porcentajes por tu cuenta: si faltan datos, agrega una alerta.
- Sueldos: Debe 5201 + Debe 5202 cargas sociales del empleador; Haber 2301 sueldos a pagar; Haber 2302 cargas sociales a pagar.
- Si el documento está en moneda extranjera, convierte a ARS con el tipo de cambio del documento; si no figura, alerta.
- Nota de crédito: invierte el asiento de la venta o la compra.
""",
}

ECUADOR = {
    "codigo": "EC", "nombre": "Ecuador", "plan_nombre": "Plan estándar de cuentas (uso común; no es el plan de la Superintendencia de Compañías)",
    "id_fiscal": "RUC", "id_regex": r"\d{13}", "id_ejemplo": "1790012345001",
    "impuesto": "IVA", "tasa_impuesto": 0.15, "moneda": "USD", "simbolo": "$",
    "inicio_ejercicio": "Enero", "reporte_impuestos": "Formulario 104 (IVA) / 103 (retenciones) – SRI",
    "regimenes": {"Régimen general": None, "RIMPE – emprendedor": None, "RIMPE – negocio popular": None},
    "pago_cuenta_label": "Pago a cuenta", "actividades": _ACTIVIDADES,
    "aviso": _AVISO_ESTANDAR + " Si tu empresa está controlada por la Superintendencia de Compañías, consulta con tu contador por su plan oficial.",
    "grupos": _GRUPOS_ESTANDAR, "nomina": _NOMINA_ESTANDAR, "cuentas_base": _BASE_ESTANDAR,
    "columnas_nomina": [("Aportes IESS y retenciones", ["2302", "2202"])],
    "plan": _plan_estandar("Crédito tributario IVA", "IVA cobrado en ventas (por pagar)", "Impuestos por pagar y retenciones (SRI)",
                           "Sueldos por pagar", "Aportes al IESS y beneficios de ley por pagar"),
    "reglas_ia": """
- IVA tarifa general 15% (0% para ciertos bienes y servicios: usa la tarifa que muestre la factura).
- Compra con factura: Debe gasto o inventario por la base + Debe 1401 crédito tributario IVA; Haber 2101 por el total,
  menos las retenciones del comprobante de retención si existe.
- Venta: Debe 1201 por el total; Haber 2201 IVA cobrado; Haber 4101/4102 por la base.
- Retenciones en la fuente de Impuesto a la Renta e IVA: si hay un comprobante de retención, las practicadas por la empresa van al
  Haber de 2202; las que le practican a la empresa van al Debe de 1402. No calcules porcentajes por tu cuenta: si faltan, alerta.
- Nómina: Debe 5201 + Debe 5202 aporte patronal; Haber 2301 sueldos por pagar; Haber 2302 aportes al IESS y beneficios por pagar.
- Moneda funcional USD. Si el documento está en otra moneda, convierte con el tipo de cambio del documento; si no figura, alerta.
- Nota de crédito: invierte el asiento de la venta o la compra.
""",
}

BOLIVIA = {
    "codigo": "BO", "nombre": "Bolivia", "plan_nombre": "Plan estándar de cuentas (uso común, sin plan oficial único)",
    "id_fiscal": "NIT", "id_regex": r"\d{6,13}", "id_ejemplo": "1020304050",
    "impuesto": "IVA", "tasa_impuesto": 0.13, "moneda": "BOB", "simbolo": "Bs",
    "inicio_ejercicio": "Enero (según tu actividad)", "reporte_impuestos": "Formularios 200 (IVA) y 400 (IT) – SIN",
    "regimenes": {"Régimen general": 3.0, "Sistema Tributario Integrado (STI)": None},
    "pago_cuenta_label": "IT (Impuesto a las Transacciones)", "actividades": _ACTIVIDADES, "aviso": _AVISO_ESTANDAR,
    "grupos": _GRUPOS_ESTANDAR, "nomina": _NOMINA_ESTANDAR, "cuentas_base": _BASE_ESTANDAR,
    "columnas_nomina": [("Aportes AFP/CNS y retenciones", ["2302", "2202"])],
    "plan": _plan_estandar("IVA crédito fiscal", "IVA débito fiscal", "Impuestos por pagar (IT, IUE, retenciones)",
                           "Sueldos por pagar", "Aportes sociales por pagar (AFP, CNS)"),
    "reglas_ia": """
- IVA 13%: en Bolivia el impuesto está INCLUIDO en el importe facturado; el crédito o débito fiscal es el 13% del importe
  total de la factura (no se suma encima). La base es el total menos ese 13%.
- Compra con factura: Debe gasto o inventario por (total − crédito fiscal) + Debe 1401 IVA crédito fiscal (13% del importe);
  Haber 2101 por el total. Si el importe sujeto a crédito fiscal difiere del total (descuentos, exentos), usa lo que indique la factura.
- Venta: Debe 1201 por el total; Haber 2201 IVA débito fiscal (13% del importe); Haber 4101/4102 por el resto.
- El Impuesto a las Transacciones (IT, 3% de los ingresos brutos) se liquida en la declaración mensual: NO lo registres factura por factura.
- Sueldos: Debe 5201 + Debe 5202 aportes del empleador; Haber 2301 sueldos por pagar; Haber 2302 aportes sociales por pagar;
  Haber 2202 si se retuvo RC-IVA al trabajador y el documento lo muestra.
- Si el documento está en moneda extranjera, convierte a BOB con el tipo de cambio del documento; si no figura, alerta.
- Nota de crédito: invierte el asiento de la venta o la compra.
""",
}


ESTANDAR = {
    "codigo": "ST", "nombre": "Estándar (sin país)",
    "contexto": "contabilidad general según NIIF, sin una legislación de país específica",
    "plan_nombre": "Plan estándar neutro (1 Activo, 2 Pasivo, 3 Patrimonio, 4 Ingresos, 5 Costos y gastos). Puedes crear cuentas nuevas",
    "id_fiscal": "ID fiscal", "id_regex": r"[0-9A-Z]{3,20}", "id_ejemplo": "123456789",
    "impuesto": "Impuesto a las ventas", "tasa_impuesto": None, "moneda": "USD", "simbolo": "",
    "monedas": ["USD", "EUR", "PEN", "COP", "MXN", "CLP", "ARS", "BOB", "BRL", "GBP"],
    "inicio_ejercicio": "Enero", "reporte_impuestos": "Declaración de impuestos de tu país",
    "regimenes": {"General": None}, "pago_cuenta_label": "Pago a cuenta",
    "actividades": _ACTIVIDADES, "cuentas_libres": True,
    "aviso": ("Modo neutro: la IA usa un plan estándar y la tasa de impuesto que muestre cada comprobante. "
              "No aplica reglas de ningún país; tu contador debe validar los asientos y las retenciones."),
    "grupos": _GRUPOS_ESTANDAR, "nomina": _NOMINA_ESTANDAR, "cuentas_base": _BASE_ESTANDAR,
    "columnas_nomina": [("Aportes y retenciones de nómina", ["2302", "2202"])],
    "plan": _plan_estandar("Impuesto a las ventas soportado (crédito)", "Impuesto a las ventas cobrado (por pagar)",
                           "Impuestos por pagar y retenciones", "Sueldos por pagar", "Aportes sociales por pagar"),
    "reglas_ia": """
- Impuesto a las ventas (IVA, IGV, VAT u otro): usa la tasa y el nombre que muestre el comprobante. No supongas una tasa.
- Compra con impuesto: Debe gasto o inventario por la base + Debe 1401 por el impuesto; Haber 2101 por el total
  (o 2102 si es un honorario o servicio por pagar).
- Venta con impuesto: Debe 1201 por el total; Haber 2201 por el impuesto; Haber 4101 (bienes) o 4102 (servicios) por la base.
- Compra o venta sin impuesto: el monto completo va al gasto, inventario o ingreso, y a no_gravado.
- Retenciones o percepciones: solo si el comprobante las muestra. Las sufridas van al Debe de 1402; las practicadas, al Haber de 2202.
  No calcules porcentajes por tu cuenta: si faltan datos, agrega una alerta.
- Nómina: Debe 5201 sueldos + Debe 5202 aportes del empleador; Haber 2301 sueldos por pagar; Haber 2302 aportes por pagar;
  Haber 2202 si el documento muestra retenciones al trabajador.
- Cuentas nuevas: si ninguna cuenta del plan describe bien la operación, puedes proponer una nueva con código de 4 dígitos que empiece
  con la clase correcta (1 activo, 2 pasivo, 3 patrimonio, 4 ingresos, 5 costos y gastos), con su nombre, y avísalo en alertas.
- Usa la moneda funcional de la empresa; si el documento está en otra moneda, convierte con el tipo de cambio del documento
  o agrega una alerta si no figura.
- Nota de crédito: invierte el asiento de la venta o la compra.
""",
}

PAISES = {p["codigo"]: p for p in (ESTANDAR, PERU, COLOMBIA, MEXICO, CHILE, ARGENTINA, ECUADOR, BOLIVIA)}
PROXIMAMENTE = []


def get_pais(codigo):
    return PAISES[codigo]


def plan_dict(codigo):
    return dict(PAISES[codigo]["plan"])
