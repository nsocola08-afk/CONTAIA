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
    return f"""Eres un contador público experto en {pais.get('contexto', pais['nombre'])}. Lees comprobantes y propones el asiento contable.

EMPRESA QUE USA EL SISTEMA
- Razón social: {empresa['nombre']}
- {pais['id_fiscal']}: {empresa['id_fiscal']}
- Régimen: {empresa['regimen']}
- Actividad: {empresa['actividad']}
- Moneda funcional: {empresa['moneda']}

CÓMO CLASIFICAR
- Si el emisor del comprobante es la empresa (su {pais['id_fiscal']} coincide), es una VENTA.
- Si la empresa es el receptor/adquirente, es una COMPRA.
- Planillas o boletas de pago de trabajadores: "planilla". Recibos por honorarios: "honorarios".
- Vouchers bancarios, cobranzas, pagos, aportes u otros movimientos: "otro".

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
                        "debe": _num(l.get("debe")), "haber": _num(l.get("haber"))})

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
    return doc


def validar_asiento(asiento):
    d, h = sum(l["debe"] for l in asiento), sum(l["haber"] for l in asiento)
    return abs(d - h) < 0.02 and d > 0, d, h


def extraer(nombre, mime, datos, empresa, pais):
    """Llama a Claude y devuelve el documento normalizado. Reintenta una vez si el JSON viene mal."""
    if len(datos) > LIMITE_BYTES:
        raise ValueError("El archivo supera 4.5 MB. Comprímelo o sube una foto más liviana.")
    if os.environ.get("CONTAIA_MOCK") == "1":  # solo para pruebas sin AWS
        from mock_claude import respuesta_falsa
        return normalizar(respuesta_falsa(nombre, empresa), empresa, pais)

    mensajes = [{"role": "user", "content": [_bloque_documento(nombre, mime, datos),
                                              {"text": "Analiza este documento y responde solo con el JSON indicado."}]}]
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
