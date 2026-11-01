"""
Conexión con Claude en Amazon Bedrock.
Claude lee el documento (PDF o imagen), lo clasifica y propone el asiento contable.
La app valida el resultado; Claude nunca guarda nada por su cuenta.
"""
import json
import os
import re
from datetime import date

import boto3
from botocore.config import Config

import contabilidad
import paises as _paises

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-5-5")

FORMATOS_IMG = {"image/png": "png", "image/jpeg": "jpeg", "image/jpg": "jpeg", "image/webp": "webp", "image/gif": "gif"}
LIMITE_BYTES = 4_500_000  # límite de Bedrock para documentos

_client = None


def cliente():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION,
                               config=Config(read_timeout=120, retries={"max_attempts": 3}))
    return _client


def probar_conexion():
    """Devuelve (ok, mensaje)."""
    try:
        r = cliente().converse(modelId=MODEL_ID, messages=[{"role": "user", "content": [{"text": "Responde solo: OK"}]}],
                               inferenceConfig={"maxTokens": 50})
        txt = _texto(r)
        return True, f"Conexión correcta con {MODEL_ID}. Respuesta: {txt.strip()[:60]}"
    except Exception as e:  # noqa: BLE001
        return False, _explicar_error(e)


def _explicar_error(e):
    s = str(e)
    if "AccessDenied" in s:
        return "AWS rechazó el acceso: al usuario IAM le faltan permisos de Bedrock o el modelo no está habilitado. Detalle: " + s[:200]
    if "NoCredentials" in s or "Unable to locate credentials" in s:
        return "No se encontraron las claves de AWS. Revisa las variables AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY en Railway."
    if "UnrecognizedClient" in s or "InvalidSignature" in s or "security token" in s.lower():
        return "Las claves de AWS son incorrectas o están desactivadas."
    if "ValidationException" in s:
        return "Bedrock no reconoce el modelo o la región. Revisa BEDROCK_MODEL_ID y AWS_REGION. Detalle: " + s[:200]
    if "Throttling" in s:
        return "AWS está limitando las llamadas. Espera unos segundos y reintenta."
    return "Error al llamar a Claude: " + s[:300]


def _texto(resp):
    partes = resp["output"]["message"]["content"]
    return "".join(p["text"] for p in partes if "text" in p)


def _prompt_sistema(empresa, pais):
    plan = "\n".join(f"{c} | {n}" for c, n in pais["plan"])
    notas = (empresa.get("notas_ia") or "").strip()
    bloque_notas = (f"\nINSTRUCCIONES PERMANENTES DEL USUARIO (tienen prioridad sobre las reglas generales; el asiento debe cuadrar siempre)\n{notas}\n"
                    if notas else "")
    guia = _paises.guia_actividad(pais, empresa.get("actividad", ""))
    return f"""Eres un contador público experto en {pais.get('contexto', pais['nombre'])}. Lees comprobantes y propones el asiento contable.

EMPRESA QUE USA EL SISTEMA
- Razón social: {empresa['nombre']}
- {pais['id_fiscal']}: {empresa['id_fiscal']}
- Régimen: {empresa['regimen']}
- Giro del negocio: {empresa['actividad']}
- Moneda funcional: {empresa['moneda']}

CÓMO CLASIFICAR
- Si el emisor del comprobante es la empresa (su {pais['id_fiscal']} coincide), es una VENTA.
- Si la empresa es el receptor/adquirente, es una COMPRA.
- Planillas o boletas de pago de trabajadores: "planilla". Recibos por honorarios: "honorarios".
- Vouchers bancarios, cobranzas, pagos, aportes u otros movimientos: "otro".

{bloque_notas}
{guia}

CLASIFICACIÓN DE COMPRAS (muy importante)
- MERCADERÍA: bienes que la empresa compra para revender sin transformarlos. Va a la cuenta de compras de mercadería.
- GASTO: bienes de consumo y servicios de la operación (gas, limpieza, útiles, luz, alquiler, honorarios, etc.). Va a una cuenta de gasto.
- ACTIVO FIJO: bienes duraderos de uso propio (equipos, muebles, vehículos). Va a una cuenta de inmuebles, maquinaria y equipo.
- Si el usuario indica la naturaleza de la compra (en sus instrucciones o junto al documento), OBEDÉCELA sin discutirla.
- Si no la indica, usa el concepto del comprobante y la actividad de la empresa. Si dudas entre mercadería y gasto, elige la opción
  más probable y deja una alerta que pregunte explícitamente, para que el usuario pueda corregirla.

REGLAS CONTABLES DEL PAÍS
{pais['reglas_ia']}

PLAN DE CUENTAS PERMITIDO (usa SOLO estas cuentas, con su código exacto)
{plan}

FORMATO DE RESPUESTA
Responde ÚNICAMENTE con un objeto JSON, sin texto antes ni después ni bloques de código:
{{
  "tipo": "compra|venta|planilla|honorarios|otro",
  "tipo_comprobante": "texto, ej. Factura",
  "serie": "texto", "numero": "texto",
  "fecha": "AAAA-MM-DD",
  "emisor_id": "texto o vacío", "emisor_nombre": "texto",
  "receptor_id": "texto o vacío", "receptor_nombre": "texto",
  "moneda_original": "PEN|USD|EUR", "tipo_cambio": 0,
  "base_imponible": 0, "impuesto": 0, "no_gravado": 0, "total": 0,
  "glosa": "descripción corta del asiento",
  "asiento": [{{"cuenta": "codigo", "nombre": "denominación", "debe": 0, "haber": 0}}],
  "alertas": ["avisos para el contador, si los hay"]
}}
Todos los importes (base_imponible, impuesto, no_gravado, total y el asiento) deben estar en la moneda funcional ({empresa['moneda']}),
ya convertidos. Usa números con punto decimal y 2 decimales. El asiento debe cuadrar: suma del Debe igual a la suma del Haber.
Si un dato no se lee o no existe, usa cadena vacía o 0 y explícalo en "alertas". Nunca inventes datos."""


def _bloque_documento(nombre, mime, datos):
    if mime == "application/pdf" or nombre.lower().endswith(".pdf"):
        limpio = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 \-\(\)\[\]]", " ", os.path.splitext(nombre)[0])).strip()[:40] or "documento"
        return {"document": {"format": "pdf", "name": limpio, "source": {"bytes": datos}}}
    fmt = FORMATOS_IMG.get(mime)
    if not fmt:
        ext = nombre.lower().rsplit(".", 1)[-1]
        fmt = {"png": "png", "jpg": "jpeg", "jpeg": "jpeg", "webp": "webp", "gif": "gif"}.get(ext)
    if not fmt:
        raise ValueError("Formato no soportado. Sube un PDF, PNG, JPG o WEBP.")
    return {"image": {"format": fmt, "source": {"bytes": datos}}}


def _json_de(texto):
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.M).strip()
    i, j = texto.find("{"), texto.rfind("}")
    if i < 0 or j < 0:
        raise ValueError("Claude no devolvió un JSON.")
    return json.loads(texto[i:j + 1])


def _num(x):
    try:
        return round(float(x), 2)
    except (TypeError, ValueError):
        return 0.0


def normalizar(j, empresa, pais):
    """Convierte la respuesta de Claude al formato interno y la valida."""
    alertas = [str(a) for a in (j.get("alertas") or [])]
    plan = dict(pais["plan"])
    limpiar = lambda x: re.sub(r"[^0-9A-Z]", "", str(x or "").upper())  # noqa: E731
    mi_id = limpiar(empresa["id_fiscal"])

    emi, rec = limpiar(j.get("emisor_id")), limpiar(j.get("receptor_id"))
    tipo = j.get("tipo") if j.get("tipo") in ("compra", "venta", "planilla", "honorarios", "otro") else "otro"
    # La app manda: si el ID fiscal de la empresa aparece, eso decide compra/venta.
    if tipo in ("compra", "venta") and mi_id:
        if emi == mi_id and tipo != "venta":
            tipo = "venta"; alertas.append("Se corrigió el tipo a VENTA porque el emisor es tu empresa.")
        elif rec == mi_id and tipo != "compra":
            tipo = "compra"; alertas.append("Se corrigió el tipo a COMPRA porque el receptor es tu empresa.")
        elif mi_id not in (emi, rec):
            alertas.append(f"Ni el emisor ni el receptor coinciden con tu {pais['id_fiscal']}. Verifica que sea un comprobante de tu empresa.")
    if tipo == "venta":
        c_id, c_nom = j.get("receptor_id") or "", j.get("receptor_nombre") or ""
    elif tipo in ("compra", "honorarios"):
        c_id, c_nom = j.get("emisor_id") or "", j.get("emisor_nombre") or ""
    else:
        c_id, c_nom = j.get("emisor_id") or "", j.get("emisor_nombre") or ""

    asiento = []
    for l in j.get("asiento") or []:
        cta = str(l.get("cuenta", "")).strip()
        nombre_ia = str(l.get("nombre", "")).strip()
        if cta not in plan:
            if pais.get("cuentas_libres") and re.fullmatch(r"[1-5]\d{3,}", cta) and nombre_ia:
                alertas.append(f"Cuenta nueva propuesta: {cta} {nombre_ia}. Confírmala antes de registrar.")
            else:
                alertas.append(f"La cuenta {cta} no está en el plan de cuentas. Corrígela antes de registrar.")
        asiento.append({"cuenta": cta, "nombre": plan.get(cta) or nombre_ia,
                        "debe": _num(l.get("debe")), "haber": _num(l.get("haber")), "grupo": 1})

    fecha = str(j.get("fecha") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
        alertas.append("No se pudo leer la fecha; se puso la de hoy. Corrígela.")
        fecha = date.today().isoformat()

    doc = {
        "tipo": tipo, "tipo_comprobante": str(j.get("tipo_comprobante") or ""),
        "serie": str(j.get("serie") or ""), "numero": str(j.get("numero") or ""), "fecha": fecha,
        "contraparte_id": str(c_id), "contraparte_nombre": str(c_nom),
        "moneda": str(j.get("moneda_original") or empresa["moneda"]), "tipo_cambio": _num(j.get("tipo_cambio")),
        "base": _num(j.get("base_imponible")), "impuesto": _num(j.get("impuesto")),
        "no_gravado": _num(j.get("no_gravado")), "total": _num(j.get("total")),
        "glosa": str(j.get("glosa") or ""), "asiento": asiento, "alertas": alertas,
    }
    if doc["tipo"] in ("compra", "venta") and abs(doc["base"] + doc["impuesto"] + doc["no_gravado"] - doc["total"]) > 0.05:
        alertas.append("Base + impuesto + no gravado no suman el total. Revisa los montos.")
    doc = agregar_destino(doc, pais)
    doc = agregar_destino_funcion(doc, pais)
    if pide_costo_venta(doc["asiento"], doc["tipo"], pais):
        doc["alertas"].append("Venta de mercaderías: falta el asiento de costo de ventas (Debe 69 / Haber 20). "
                              "Ingresa el costo de lo vendido más abajo.")
    return doc


def _agregar_asiento(doc, pais, pares, alerta=None):
    """Agrega un asiento nuevo (grupo siguiente) con líneas (cuenta, debe, haber)."""
    plan = dict(pais["plan"])
    g = max([int(l.get("grupo", 1) or 1) for l in doc["asiento"]] or [1]) + 1
    for cta, d, h in pares:
        doc["asiento"].append({"cuenta": cta, "nombre": plan[cta], "debe": round(d, 2), "haber": round(h, 2), "grupo": g})
    if alerta:
        doc["alertas"].append(alerta)


def agregar_destino(doc, pais):
    """Perú: a una compra de mercadería, materia prima o envases le agrega el asiento de destino a existencias
    (Debe 20/24/26 / Haber 61). Si la compra ya va directo a existencias, no agrega nada. Una nota de crédito lo revierte."""
    cfg = pais.get("destino_compra")
    if not cfg or doc["tipo"] != "compra":
        return doc
    pares, usadas = [], []
    for m in cfg["mapa"]:
        monto = round(sum(l["debe"] - l["haber"] for l in doc["asiento"] if int(l.get("grupo", 1) or 1) == 1
                          and any(str(l["cuenta"]).startswith(p) for p in m["compra"])), 2)
        if abs(monto) < 0.01:
            continue
        a = abs(monto)
        pares += [(m["inventario"], a, 0), (m["variacion"], 0, a)] if monto > 0 else [(m["variacion"], a, 0), (m["inventario"], 0, a)]
        usadas.append(f"{m['inventario']} / {m['variacion']}")
    if pares:
        _agregar_asiento(doc, pais, pares, f"Se agregó el asiento de destino de la compra a existencias (Debe / Haber: {', '.join(usadas)}).")
    return doc


def agregar_destino_funcion(doc, pais):
    """Perú: a cada gasto de las cuentas 62, 63, 64, 65 y 68 le agrega el destino por función:
    Debe 94 Gastos administrativos (o 95 Gastos de ventas) / Haber 791 Cargas imputables."""
    cfg = pais.get("destino_funcion")
    if not cfg or doc["tipo"] == "venta":
        return doc
    adm = ven = 0.0
    for l in doc["asiento"]:
        if int(l.get("grupo", 1) or 1) != 1:
            continue
        cta = str(l["cuenta"])
        if any(cta.startswith(p) for p in cfg["cuentas_gasto"]):
            m = l["debe"] - l["haber"]
            if any(cta.startswith(p) for p in cfg["ventas_prefijos"]):
                ven += m
            else:
                adm += m
    pares, total = [], 0.0
    for cuenta_fn, m in ((cfg["administrativo"], round(adm, 2)), (cfg["ventas"], round(ven, 2))):
        if abs(m) < 0.01:
            continue
        pares.append((cuenta_fn, m, 0) if m > 0 else (cuenta_fn, 0, -m))
        total += m
    if not pares:
        return doc
    pares.append((cfg["contrapartida"], 0, total) if total > 0 else (cfg["contrapartida"], -total, 0))
    _agregar_asiento(doc, pais, pares, "Se agregó el destino por función (94 Gastos administrativos / 79). "
                                      "Cambia a 95 Gastos de ventas si corresponde a ventas.")
    return doc


def lineas_costo_venta(asiento, pais, monto):
    """Líneas del asiento de costo de ventas (inventario permanente): Debe 6911 / Haber 2011."""
    cfg = pais["costo_venta"]
    plan = dict(pais["plan"])
    g = max([int(l.get("grupo", 1) or 1) for l in asiento] or [1]) + 1
    monto = round(float(monto), 2)
    return [{"cuenta": cfg["cuenta_costo"], "nombre": plan[cfg["cuenta_costo"]], "debe": monto, "haber": 0.0, "grupo": g},
            {"cuenta": cfg["inventario"], "nombre": plan[cfg["inventario"]], "debe": 0.0, "haber": monto, "grupo": g}]


def pide_costo_venta(doc_o_asiento, tipo, pais):
    """True si es una venta de mercaderías sin asiento de costo de ventas (cuenta 69)."""
    cfg = pais.get("costo_venta")
    asiento = doc_o_asiento
    if not cfg or tipo != "venta":
        return False
    vende = any(str(l["cuenta"]).startswith(cfg["ventas_prefijo"]) and l["haber"] > 0 for l in asiento)
    tiene = any(str(l["cuenta"]).startswith("69") for l in asiento)
    return vende and not tiene


def opciones_naturaleza(pais):
    """Cuentas que ofrece el botón Reclasificar según la naturaleza de la compra."""
    g, cc = pais["grupos"], contabilidad.coincide
    gasto = [c for c, _ in pais["plan"] if any(cc(c, g[k]) for k in ("servicios", "otros_gastos", "tributos"))]
    activo = [c for c, n in pais["plan"] if cc(c, g["fijo"]) and "depreciación" not in n.lower()]
    opciones = {"Mercadería para reventa": [pais["cuentas_base"]["compras"]]}
    opciones.update(pais.get("naturalezas_extra", {}))
    opciones.update({"Gasto (consumo u operación)": gasto, "Activo fijo": activo})
    return opciones


def naturaleza_actual(asiento, pais):
    """Indica cuál opción de opciones_naturaleza describe hoy el asiento (para preseleccionarla)."""
    op = opciones_naturaleza(pais)
    cuentas = [str(l["cuenta"]) for l in asiento if int(l.get("grupo", 1) or 1) == 1 and l["debe"] > 0]
    merc = pais["cuentas_base"]["compras"]
    if any(c.startswith(merc[:3]) for c in cuentas):
        return 0
    for i, nombre in enumerate(op):
        if i and any(c in op[nombre] for c in cuentas):
            return i
    return 0


def reclasificar_compra(asiento, pais, cuenta):
    """Cambia la cuenta de la base de una compra (mercadería, gasto o activo fijo) y regenera los asientos
    de destino. Conserva las líneas de impuesto y de contrapartida (proveedores, caja, bancos), sin importar
    de qué lado estén (una nota de crédito las invierte). Devuelve (asiento, alertas) o None."""
    g, cc, plan = pais["grupos"], contabilidad.coincide, dict(pais["plan"])
    fijas = g["impuestos"] + g["cxp"] + g["remuneraciones"] + g["efectivo"] + g["cxc"]
    g1 = [l for l in asiento if int(l.get("grupo", 1) or 1) == 1]
    mantener = [dict(l, grupo=1) for l in g1 if cc(str(l["cuenta"]), fijas)]
    base = round(sum(l["debe"] - l["haber"] for l in g1 if not cc(str(l["cuenta"]), fijas)), 2)
    if abs(base) < 0.01 or cuenta not in plan:
        return None
    linea = {"cuenta": cuenta, "nombre": plan[cuenta], "debe": base if base > 0 else 0.0,
             "haber": -base if base < 0 else 0.0, "grupo": 1}
    doc = {"tipo": "compra", "asiento": [linea] + mantener, "alertas": []}
    agregar_destino(doc, pais)
    agregar_destino_funcion(doc, pais)
    return doc["asiento"], doc["alertas"]


def validar_asiento(asiento):
    """Cada asiento (grupo 1, 2…) debe cuadrar por separado."""
    grupos = {}
    for l in asiento:
        g = int(l.get("grupo", 1) or 1)
        d, h = grupos.get(g, (0.0, 0.0))
        grupos[g] = (d + l["debe"], h + l["haber"])
    ok = bool(grupos) and all(abs(d - h) < 0.02 and d > 0 for d, h in grupos.values())
    return ok, sum(d for d, _ in grupos.values()), sum(h for _, h in grupos.values())


def extraer(nombre, mime, datos, empresa, pais, pista=""):
    """Llama a Claude y devuelve el documento normalizado. Reintenta una vez si el JSON viene mal."""
    if len(datos) > LIMITE_BYTES:
        raise ValueError("El archivo supera 4.5 MB. Comprímelo o sube una foto más liviana.")
    if os.environ.get("CONTAIA_MOCK") == "1":  # solo para pruebas sin AWS
        from mock_claude import respuesta_falsa
        return normalizar(respuesta_falsa(nombre, empresa, pista), empresa, pais)

    mensajes = [{"role": "user", "content": [_bloque_documento(nombre, mime, datos),
                                              {"text": "Analiza este documento y responde solo con el JSON indicado."
                                                       + (f"\n\nINDICACIÓN DEL USUARIO PARA ESTE DOCUMENTO (obligatoria): {pista.strip()}" if pista.strip() else "")}]}]
    ultimo_error = None
    for intento in range(2):
        try:
            r = cliente().converse(modelId=MODEL_ID, system=[{"text": _prompt_sistema(empresa, pais)}],
                                   messages=mensajes, inferenceConfig={"maxTokens": 4000})
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(_explicar_error(e)) from e
        txt = _texto(r)
        try:
            return normalizar(_json_de(txt), empresa, pais)
        except (ValueError, json.JSONDecodeError) as e:
            ultimo_error = e
            mensajes += [r["output"]["message"],
                         {"role": "user", "content": [{"text": "Tu respuesta no fue un JSON válido. Responde SOLO con el JSON."}]}]
    raise RuntimeError(f"Claude no devolvió un resultado válido tras 2 intentos ({ultimo_error}).")


# ------------------------------------------------------------------------------------------ registro inteligente (modo simple)
TIPOS_IA = ["venta", "compra", "gasto", "activo_fijo", "honorarios", "planilla", "cobranza", "pago", "aporte_capital", "no_claro"]


def _prompt_operacion(empresa, pais, hoy):
    plan = dict(pais["plan"])
    opc = opciones_naturaleza(pais)
    bloques = "\n".join(f"* {k}:\n" + "\n".join(f"    {c} | {plan[c]}" for c in cs) for k, cs in opc.items())
    notas = (empresa.get("notas_ia") or "").strip()
    bloque_notas = f"\nINSTRUCCIONES PERMANENTES DEL USUARIO (tienen prioridad)\n{notas}\n" if notas else ""
    guia = _paises.guia_actividad(pais, empresa.get("actividad", ""))
    return f"""Eres un contador público experto en {pais.get('contexto', pais['nombre'])}. El usuario describe en una frase una operación de su empresa
y tú la conviertes en los campos de un formulario. No armas el asiento: solo rellenas los datos; el sistema genera el asiento.

EMPRESA: {empresa['nombre']} | Giro: {empresa['actividad']} | Régimen: {empresa['regimen']} | Moneda: {empresa['moneda']}
FECHA DE HOY: {hoy}
{bloque_notas}
{guia}

TIPOS DE OPERACIÓN
- venta: la empresa vende bienes o servicios. "se_vende": "mercaderias" (bienes que revende) o "servicios".
- compra: compra de mercadería o insumos para reventa/producción. Elige "cuenta" de la lista de naturalezas que NO sean gasto ni activo fijo.
- gasto: servicios y consumo de la operación (luz, gas, limpieza, alquiler, útiles). Elige "cuenta" de «Gasto».
- activo_fijo: bienes duraderos de uso propio. Elige "cuenta" de «Activo fijo».
- honorarios: pago a un profesional independiente (recibo por honorarios).
- planilla: remuneraciones del personal ("bruto" = total bruto).
- cobranza: un cliente pagó una deuda anterior. pago: la empresa paga una deuda ("destino": "Proveedores", "Remuneraciones por pagar" o "Tributos por pagar").
- aporte_capital: un socio aporta dinero.
- no_claro: si la frase no permite saber el tipo o el monto. Escribe en "pregunta" qué falta.

CUENTAS DISPONIBLES PARA compra, gasto y activo_fijo (usa el código exacto)
{bloques}

REGLAS
- "tasa_impuesto": el porcentaje del impuesto al consumo (IVA, IGV, "valor agregado", impuesto a las ventas, etc.) SOLO si el usuario lo dice (ej. 18); si no lo dice, null. Si el usuario menciona un porcentaje de impuesto, "impuesto" no puede ser "sin".
- Si el usuario no dice si el monto incluye impuesto, supón que SÍ lo incluye ("incluido") y anótalo en "supuestos". Si dice que no es gravado/exonerado, usa "sin"; si dice "más IGV/IVA", usa "agregar".
- Forma de pago: "credito" (por cobrar/pagar, "a crédito", "fiado", "a 30 días"), "banco" (transferencia, depósito, tarjeta, yape/plin, cheque) o "caja" (efectivo, al contado). Si no se indica en una venta o compra, supón "caja" y anótalo.
- "vence": fecha AAAA-MM-DD solo si es a crédito y hay plazo; si hay "a 30 días" calcúlala desde la fecha de la operación. Si no, null.
- Si no hay fecha, usa la fecha de hoy. Interpreta "ayer", "el lunes", "el 5 de octubre" respecto a la fecha de hoy.
- "supuestos": SOLO lo que el usuario NO dijo y tuviste que suponer (forma de pago, comprobante, fecha, tasa, plazo). No repitas ni confirmes lo que sí dijo, ni escribas datos que no se supusieron. Máximo 4 frases cortas.
- "monto" es lo que dice el usuario (un solo número). Si da cantidad x precio unitario, "monto" es el total (cantidad × precio), sin impuesto si dice que se agrega. No inventes datos: lo que no se sabe va vacío, 0 o null y se anota en "supuestos".
- Si la operación está en otra moneda, indica "moneda" (código) y "tipo_cambio" solo si el usuario lo da; si no, 0.
- Comprobante: "Factura", "Boleta de venta", "Recibo por honorarios", "Nota de crédito", "Nota de débito" o "Ticket / otro"; si no se indica en venta/compra, "Factura" y anótalo.
- Reglas del país: {pais['reglas_ia']}

FORMATO: responde ÚNICAMENTE con un JSON, sin texto antes ni después ni bloques de código:
{{"tipo": "{'|'.join(TIPOS_IA)}", "pregunta": "", "fecha": "AAAA-MM-DD", "monto": 0, "impuesto": "incluido|agregar|sin", "tasa_impuesto": null,
 "forma": "credito|banco|caja", "vence": null, "tercero_id": "", "tercero_nombre": "", "comprobante": "Factura", "documento": "",
 "se_vende": "mercaderias|servicios", "cuenta": "", "destino": "", "bruto": 0, "moneda": "{empresa['moneda']}", "tipo_cambio": 0,
 "glosa": "descripción corta", "supuestos": ["lo que supusiste, en frases cortas"]}}"""


def interpretar_operacion(texto, empresa, pais, hoy):
    """Convierte una frase del usuario en los campos del formulario de «Registrar operación». Devuelve un diccionario validado."""
    texto = (texto or "").strip()
    if not texto:
        raise ValueError("Escribe la operación.")
    if len(texto) > 1500:
        raise ValueError("La descripción es muy larga: máximo 1,500 caracteres. Registra una operación por vez.")
    if os.environ.get("CONTAIA_MOCK") == "1":
        from mock_claude import operacion_falsa
        r = operacion_falsa(texto, empresa, pais, hoy)
    else:
        mensajes = [{"role": "user", "content": [{"text": f"Operación: {texto}\n\nResponde solo con el JSON."}]}]
        r, ultimo = None, None
        for _ in range(2):
            try:
                resp = cliente().converse(modelId=MODEL_ID, system=[{"text": _prompt_operacion(empresa, pais, hoy)}],
                                          messages=mensajes, inferenceConfig={"maxTokens": 800})
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(_explicar_error(e)) from e
            try:
                r = _json_de(_texto(resp))
                break
            except (ValueError, json.JSONDecodeError) as e:
                ultimo = e
                mensajes += [resp["output"]["message"], {"role": "user", "content": [{"text": "Responde SOLO con el JSON."}]}]
        if r is None:
            raise RuntimeError(f"La IA no devolvió un resultado válido ({ultimo}). Inténtalo de nuevo o usa el formulario.")
    return _validar_operacion(r, empresa, pais, hoy)


def _validar_operacion(r, empresa, pais, hoy):
    """Revisa lo que devolvió la IA: tipos, fechas, cuentas del plan y números. Lo dudoso se corrige o se rechaza."""
    import re as _re
    from datetime import date as _date
    plan = dict(pais["plan"])
    if not isinstance(r, dict):
        raise ValueError("Respuesta inesperada de la IA.")
    tipo = str(r.get("tipo") or "no_claro")
    if tipo not in TIPOS_IA:
        tipo = "no_claro"
    sup = [str(x) for x in (r.get("supuestos") or []) if str(x).strip()]
    out = {"tipo": tipo, "pregunta": str(r.get("pregunta") or "").strip(), "supuestos": sup}
    if tipo == "no_claro":
        out["pregunta"] = out["pregunta"] or "No pude entender la operación. Indica qué ocurrió y por cuánto."
        return out
    fecha = str(r.get("fecha") or "")
    try:
        _date.fromisoformat(fecha)
    except ValueError:
        fecha = hoy
        sup.append("No se entendió la fecha: se usó la de hoy.")
    try:
        monto = round(float(r.get("monto") or 0), 2)
    except (TypeError, ValueError):
        monto = 0.0
    bruto = 0.0
    try:
        bruto = round(float(r.get("bruto") or 0), 2)
    except (TypeError, ValueError):
        pass
    if tipo == "planilla":
        monto = bruto or monto
        bruto = monto
    if monto <= 0:
        return {"tipo": "no_claro", "pregunta": "No encontré el monto. ¿Por cuánto fue la operación?", "supuestos": sup}
    vence = r.get("vence")
    try:
        vence = _date.fromisoformat(str(vence)).isoformat() if vence else None
    except ValueError:
        vence = None
    cuenta = str(r.get("cuenta") or "").strip()
    if tipo in ("compra", "gasto", "activo_fijo"):
        opc = opciones_naturaleza(pais)
        validas = {"compra": [c for k, cs in opc.items() if not k.startswith(("Gasto", "Activo")) for c in cs],
                   "gasto": opc["Gasto (consumo u operación)"], "activo_fijo": opc["Activo fijo"]}[tipo]
        if cuenta not in validas:
            cuenta = validas[0] if validas else ""
            sup.append(f"No se pudo elegir la cuenta con certeza: se propuso {cuenta} – {plan.get(cuenta, '')}. Cámbiala en «Reclasificar» si no corresponde.")
    mon = str(r.get("moneda") or empresa["moneda"]).upper()[:8]
    try:
        tc = float(r.get("tipo_cambio") or 0)
    except (TypeError, ValueError):
        tc = 0.0
    try:
        tasa = float(r.get("tasa_impuesto") or 0)
    except (TypeError, ValueError):
        tasa = 0.0
    tasa = tasa if 0 < tasa <= 100 else 0.0
    out.update({
        "fecha": fecha, "monto": monto, "bruto": bruto, "tasa": tasa,
        "impuesto": r.get("impuesto") if r.get("impuesto") in ("incluido", "agregar", "sin") else "incluido",
        "forma": r.get("forma") if r.get("forma") in ("credito", "banco", "caja") else "caja",
        "vence": vence, "tercero_id": _re.sub(r"[^0-9A-Za-z\-]", "", str(r.get("tercero_id") or "")),
        "tercero_nombre": str(r.get("tercero_nombre") or "").strip()[:250],
        "comprobante": str(r.get("comprobante") or "Factura"), "documento": str(r.get("documento") or "").strip()[:40],
        "se_vende": "servicios" if r.get("se_vende") == "servicios" else "mercaderias", "cuenta": cuenta,
        "destino": r.get("destino") if r.get("destino") in ("Proveedores", "Remuneraciones por pagar", "Tributos por pagar") else "Proveedores",
        "moneda": mon, "tipo_cambio": tc, "glosa": str(r.get("glosa") or "").strip()[:200]})
    return out
