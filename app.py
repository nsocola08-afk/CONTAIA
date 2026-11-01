import io
import os
import re
import uuid
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from streamlit_cookies_controller import CookieController

import claude_bedrock as ia
import analisis as an
import contabilidad as cont
import informe
import db
import operaciones as ops
import paises

st.set_page_config(page_title="REDContable IA", layout="wide")
COOKIE = "contaia_id"
ESTILO = """
<style>
.block-container{padding-top:3.4rem}
[data-testid=stMetricValue]{font-size:1.5rem}
/* Botones: bloques sólidos y rectangulares */
.stButton>button, .stDownloadButton>button, .stFormSubmitButton>button, [data-testid="stFileUploaderDropzone"] button{
  border-radius:0 !important; box-shadow:none !important; font-weight:600 !important; letter-spacing:.2px;
  padding:.6rem 1.3rem !important; min-height:2.7rem; border:0 !important;
  background:#dde4ee !important; color:#1f3a5f !important; transition:background .15s;}
.stButton>button:hover, .stDownloadButton>button:hover, .stFormSubmitButton>button:hover,
[data-testid="stFileUploaderDropzone"] button:hover{background:#c9d4e4 !important; color:#14284a !important;}
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"]{
  background:#1f3a5f !important; color:#fff !important;}
button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover{background:#2c4f80 !important; color:#fff !important;}
.stButton>button:disabled{background:#e9edf3 !important; color:#9aa5b5 !important}
/* Zona de subir archivos: bloque sólido */
[data-testid="stFileUploaderDropzone"]{
  border-radius:0 !important; border:0 !important; background:#e8edf5 !important; padding:2.2rem 1.5rem !important;}
/* Campos y paneles rectangulares */
[data-baseweb="input"], [data-baseweb="select"]>div, [data-baseweb="textarea"], .stTextInput input,
[data-testid="stExpander"], [data-testid="stForm"], [data-testid="stTable"], [data-testid="stDataFrame"], [data-testid="stAlertContainer"]{
  border-radius:0 !important;}
/* Menú lateral: bloques sólidos */
[data-testid="stSidebar"]{background:#f1f4f8}
[data-testid="stSidebar"] [data-testid="stRadioGroup"]{gap:.3rem}
[data-testid="stSidebar"] [data-testid="stRadioGroup"]>div{width:100%}
[data-testid="stSidebar"] label[data-testid="stRadioOption"]{
  display:flex; width:100%; box-sizing:border-box; border:0; border-radius:0; padding:.65rem .9rem;
  background:#dde4ee; cursor:pointer; transition:background .15s;}
[data-testid="stSidebar"] label[data-testid="stRadioOption"]>div>div:first-child{display:none}
[data-testid="stSidebar"] label[data-testid="stRadioOption"]:hover{background:#c9d4e4}
[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"]{background:#1f3a5f}
[data-testid="stSidebar"] label[data-testid="stRadioOption"][data-selected="true"] *{color:#fff !important}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:0 !important}
/* Selector de estado financiero: botones rectangulares */
[data-testid="stButtonGroup"] button{border-radius:0 !important; box-shadow:none !important; border:0 !important;
  background:#dde4ee !important; color:#1f3a5f !important; font-weight:600 !important; padding:.55rem 1.2rem !important;}
[data-testid="stButtonGroup"] button:hover{background:#c9d4e4 !important;}
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"]{background:#1f3a5f !important; color:#fff !important;}
/* Navegación lateral: botones alineados a la izquierda y submenú */
[data-testid="stSidebar"] .stButton>button{justify-content:flex-start; text-align:left}
[data-testid="stSidebar"] .stButton button div, [data-testid="stSidebar"] .stButton button p{justify-content:flex-start; text-align:left !important; width:100%}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.4rem}
[data-testid="stSidebar"] [class*="st-key-sub_"] button{background:#eef2f8 !important; font-size:.85rem; min-height:2.2rem;
  padding:.35rem .9rem .35rem 1.9rem !important}
[data-testid="stSidebar"] [class*="st-key-sub_"] button:hover{background:#dde4ee !important}
[data-testid="stSidebar"] [class*="__activo"] button{background:#4a6fa5 !important; color:#fff !important}
/* La barra superior de Streamlit conserva su estilo */
[data-testid="stHeader"] button, [data-testid="stToolbar"] button{
  background:transparent !important; min-height:0; padding:.25rem .5rem !important;}
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)


# ------------------------------------------------------------------ identificar a la persona (sin cuenta)
def identificar():
    """Cada navegador recibe un identificador secreto (cookie). Su información queda ligada a él."""
    if "owner_id" in st.session_state:
        return st.session_state.owner_id
    ya_cargo = "cookies" in st.session_state
    ctrl = CookieController()
    if not ya_cargo:           # el navegador aún no entregó sus cookies: esperar, no crear usuarios por error
        st.caption("Cargando…")
        st.stop()
    k = st.query_params.get("k", "")
    if k and db.existe_owner(k):                      # enlace de recuperación
        owner = k
    else:
        owner = ctrl.get(COOKIE) or uuid.uuid4().hex
    ctrl.set(COOKIE, owner, max_age=60 * 60 * 24 * 390, same_site="lax")
    st.session_state.owner_id = owner
    if k:
        st.query_params.clear()
    return owner


def SIM(emp, p):
    """Símbolo de moneda: en el modo estándar se muestra el código elegido (USD, EUR…)."""
    return emp["moneda"] if p.get("monedas") else p["simbolo"]


def money(x, simbolo=""):
    x = round(float(x or 0), 2) + 0.0
    return f"{simbolo} {x:,.2f}".strip()


def enlace_recuperacion(owner):
    try:
        h = st.context.headers
        host = h.get("X-Forwarded-Host") or h.get("Host")
        proto = h.get("X-Forwarded-Proto", "https")
        return f"{proto}://{host}/?k={owner}"
    except Exception:  # noqa: BLE001
        return f"(tu-direccion)/?k={owner}"


# ------------------------------------------------------------------ bienvenida (primera vez)
def normalizar_id(texto):
    return re.sub(r"[^0-9A-Z]", "", (texto or "").upper())


MARCA = '<span style="color:#d62828">RED</span>Contable IA'


def procesar_logo(archivo):
    """Reduce el logo a 400 px y lo devuelve como PNG (bytes); None si no hay o no es una imagen válida."""
    if archivo is None:
        return None
    try:
        from PIL import Image
        im = Image.open(archivo)
        im = im.convert("RGBA")
        im.thumbnail((400, 400))
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None


MODOS = {"lector": "Lector de facturas", "simple": "Modo simple"}


def elegir_modo():
    """Primera pantalla: cómo se van a registrar las operaciones."""
    st.markdown(f"# Bienvenido a {MARCA}", unsafe_allow_html=True)
    st.subheader("¿Cómo quieres trabajar?")
    st.caption("Los dos modos usan los mismos reportes. Puedes cambiar de modo después en Configuración.")
    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("### ✍️ Modo simple")
            st.write("Sin importar archivos. Tú registras cada operación (venta, compra, gasto, planilla…) llenando sus datos: "
                     "documento, moneda, tipo de cambio, monto e impuesto. La app arma el asiento.")
            if st.button("Usar el modo simple", key="modo_simple", type="primary"):
                st.session_state.modo_sel = "simple"
                st.rerun()
    with c2:
        with st.container(border=True):
            st.markdown("### 📷 Lector de facturas")
            st.write("Subes facturas, boletas, planillas o vouchers (PDF o foto). La IA los lee, los clasifica y propone el asiento. "
                     "Tú revisas y registras.")
            if st.button("Usar el lector de facturas", key="modo_lector", type="primary"):
                st.session_state.modo_sel = "lector"
                st.rerun()


def bienvenida(owner):
    st.markdown(f"# Bienvenido a {MARCA}", unsafe_allow_html=True)
    modo = st.session_state["modo_sel"]
    m1, m2 = st.columns([4, 1])
    m1.info(f"Modo elegido: **{MODOS[modo]}**")
    if m2.button("Cambiar modo", key="cambiar_modo"):
        st.session_state.pop("modo_sel", None)
        st.rerun()
    st.write("Antes de empezar, cuéntanos sobre tu empresa. Con estos datos Claude usará el plan contable y los impuestos de tu país.")
    disp = {p["nombre"]: c for c, p in sorted(paises.PAISES.items(), key=lambda x: (x[0] != "ST", x[1]["nombre"]))}
    pais_nombre = st.selectbox("País", list(disp), help="Cada país usa su propio plan de cuentas e impuestos.")
    if paises.PROXIMAMENTE:
        st.caption("Próximamente: " + ", ".join(paises.PROXIMAMENTE))
    p = paises.get_pais(disp[pais_nombre])
    act_sel = st.selectbox("Giro del negocio", p["actividades"], help="La IA usa el giro para decidir qué es mercadería, materia prima, gasto o activo.")
    act_otra = st.text_input("Especificar giro", max_chars=60, placeholder="Ej.: inmobiliaria, clínica, transporte") if act_sel == paises.OTRA else ""
    with st.form("alta"):
        nombre = st.text_input("Nombre o razón social de la empresa")
        logo_f = st.file_uploader("Logo de tu empresa (opcional)", type=["png", "jpg", "jpeg"])
        idf = st.text_input(f"{p['id_fiscal']} (número de identificación tributaria)", max_chars=20,
                            placeholder=f"Ej.: {p['id_ejemplo']}")
        if p.get("regimen_libre"):
            regimen = st.text_input("Régimen tributario", value="General", max_chars=100,
                                    help="Escribe el régimen de tu empresa (por ejemplo: General, Simplificado, MYPE).")
            r1, r2 = st.columns(2)
            tasa_renta = r1.number_input("Impuesto a la renta anual: tasa (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.5,
                                         help="Porcentaje del impuesto a la renta sobre la utilidad anual. Se usa para estimar el resultado neto.")
            pct_in = r2.number_input("Pago a cuenta mensual sobre ventas (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1,
                                     help="Porcentaje que pagas cada mes como adelanto del impuesto a la renta. Déjalo en 0 si no aplica.")
        else:
            regimen = st.selectbox("Régimen tributario", list(p["regimenes"]))
            tasa_renta = st.number_input("Impuesto a la renta anual: tasa (%) (opcional)", min_value=0.0, max_value=100.0, value=0.0,
                                         step=0.5, help="Para estimar el resultado neto en el Estado de Resultados. Puedes dejarlo en 0.")
            pct_in = None
        c1, c2 = st.columns(2)
        if p.get("monedas"):
            moneda = c1.selectbox("Moneda principal", p["monedas"], index=p["monedas"].index(p["moneda"]))
        else:
            moneda = p["moneda"]
            c1.text_input("Moneda principal", value=f"{p['moneda']} ({p['simbolo']})", disabled=True)
        c2.text_input("Inicio del ejercicio", value=p["inicio_ejercicio"], disabled=True)
        tasa = f"{p['tasa_impuesto']:.0%} (tarifa general)" if p["tasa_impuesto"] else "según cada comprobante"
        st.info(f"Plan de cuentas: {p['plan_nombre']}. {p['impuesto']}: {tasa}. El país no se puede cambiar después.")
        st.caption(p["aviso"])
        ok = st.form_submit_button("Comenzar", type="primary")
    if ok:
        idn = normalizar_id(idf)
        actividad = act_otra.strip() if act_sel == paises.OTRA else act_sel
        if not nombre.strip():
            st.error("Escribe el nombre de la empresa.")
        elif not actividad:
            st.error("Especifica el giro del negocio (por ejemplo: inmobiliaria).")
        elif not regimen.strip():
            st.error("Escribe el régimen tributario.")
        elif not re.fullmatch(p["id_regex"], idn):
            st.error(f"El {p['id_fiscal']} no tiene un formato válido para {p['nombre']}. Ejemplo: {p['id_ejemplo']}.")
        else:
            db.guardar_empresa(owner, dict(nombre=nombre.strip(), pais=p["codigo"], id_fiscal=idn,
                                           regimen=regimen.strip(), moneda=moneda, actividad=actividad,
                                           pct_renta=(pct_in if pct_in is not None else (p["regimenes"].get(regimen) or 0)),
                                           tasa_renta=tasa_renta, modo=modo, logo=procesar_logo(logo_f)))
            st.session_state.pop("modo_sel", None)
            st.rerun()


# ------------------------------------------------------------------ utilidades de vistas
def tabla(df, **kw):
    cfg = {c: st.column_config.NumberColumn(c, format="%.2f") for c in df.columns if df[c].dtype.kind == "f"}
    st.dataframe(df, hide_index=True, width="stretch", column_config=cfg, **kw)


def estado(filas):
    """Estado financiero completo, sin scroll interno. Filas con 3er elemento "t" = total (celeste y negrita)."""
    filas = [tuple(f) + (("",) if len(f) == 2 else ()) for f in filas]
    df = pd.DataFrame([(c, "" if v is None else money(v)) for c, v, _ in filas], columns=["Concepto", "Importe"])
    estilos = {"t": "background-color:#e2ecf7; font-weight:700; color:#14284a",     # secciones y totales principales
               "s": "background-color:#eff5fb; font-weight:700; color:#14284a"}     # subtotales (más claro)
    tot = {i: estilos[f[2]] for i, f in enumerate(filas) if f[2] in estilos}
    n = len(df)
    sty = df.style.apply(lambda d: pd.DataFrame([[tot[i]] * d.shape[1] if i in tot else [""] * d.shape[1]
                                                 for i in range(n)], index=d.index, columns=d.columns), axis=None)
    sty = sty.set_properties(subset=["Importe"], **{"text-align": "right"}).hide(axis="index")
    st.table(sty)


def a_excel(hojas):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for nombre, df in hojas.items():
            (df if len(df) else pd.DataFrame({"Sin datos": []})).to_excel(w, sheet_name=nombre[:31], index=False)
    return buf.getvalue()


def df_registro(docs, tipo):
    f = [{"Fecha": d["fecha"], "Comprobante": d["tipo_comprobante"], "Serie-Número": f"{d['serie']}-{d['numero']}",
          "ID": d["contraparte_id"], "Razón social": d["contraparte_nombre"], "Moneda": d["moneda"],
          "Base imponible": d["base"], "Impuesto": d["impuesto"], "No gravado": d["no_gravado"], "Total": d["total"]}
         for d in docs if d["estado"] == "registrado" and d["tipo"] == tipo]
    return pd.DataFrame(f)


def etiqueta_asiento(lineas, g):
    cuentas = [str(l["cuenta"]) for l in lineas]
    if any(c.startswith(("9", "79")) for c in cuentas):
        return "Destino del gasto por función"
    if any(c.startswith("69") for c in cuentas):
        return "Costo de ventas"
    if any(c.startswith(("20", "24", "25", "26")) for c in cuentas):
        return "Destino de la compra"
    return f"Asiento {g}"


def df_diario(docs):
    """Un número de asiento por cada grupo de líneas (una compra de mercadería en Perú genera 2)."""
    filas, n = [], 0
    for d in docs:
        if d["estado"] != "registrado":
            continue
        grupos = {}
        for l in d["asiento"]:
            grupos.setdefault(int(l.get("grupo", 1) or 1), []).append(l)
        for g in sorted(grupos):
            n += 1
            glosa = d["glosa"] if g == 1 else f"{etiqueta_asiento(grupos[g], g)} – {d['glosa']}"
            for l in grupos[g]:
                filas.append({"N°": n, "Fecha": d["fecha"], "Cuenta": l["cuenta"], "Denominación": l["nombre"],
                              "Debe": l["debe"], "Haber": l["haber"], "Glosa": glosa})
    return pd.DataFrame(filas)


def selector_periodo(docs, key):
    meses = sorted({d["fecha"][:7] for d in docs if d["estado"] == "registrado"})
    return st.selectbox("Periodo", ["Todo"] + meses, key=key)


# ------------------------------------------------------------------ páginas
def pg_dashboard(owner, emp, p, docs):
    st.header("Dashboard")
    if not any(d["estado"] == "registrado" for d in docs):
        if (emp.get("modo") or "lector") == "simple":
            st.info("Aún no hay operaciones registradas. Ve a **Registrar operación** para cargar la primera.")
        else:
            st.info("Aún no hay documentos registrados. Ve a **Subir documentos** para cargar tu primera factura.")
        return
    per = selector_periodo(docs, "per_dash")
    df_all = cont.lineas(docs)
    df = cont.filtrar(df_all, per)
    docs_p = [d for d in docs if per == "Todo" or d["fecha"][:7] == per]
    g = p["grupos"]
    er, A, P, imp = cont.kpis(docs_p, df, g, p)
    _, _, _, ta, tp, tpt = cont.situacion_financiera(df_all, g, per)
    s = SIM(emp, p)
    c = st.columns(4)
    c[0].metric("Ventas netas", money(er["ventas_netas"], s))
    c[1].metric("Compras y costo", money(er["costo"], s))
    c[2].metric("Resultado antes de impuestos", money(er["antes_impuestos"], s))
    c[3].metric(f"{p['impuesto']} del periodo", money(abs(imp), s), "por pagar" if imp >= 0 else "saldo a favor", delta_color="off")
    c = st.columns(4)
    c[0].metric("Efectivo", money(A["Efectivo y equivalentes"], s))
    c[1].metric("Por cobrar", money(A["Cuentas por cobrar"], s))
    c[2].metric("Por pagar", money(P["Cuentas por pagar"], s))
    c[3].metric("Gasto de personal", money(er["personal"], s))

    col1, col2 = st.columns(2)
    if not df_all.empty:
        meses = sorted(df_all["mes"].unique())
        v = [-cont.saldo(df_all[df_all["mes"] == m], g["ventas"]) for m in meses]
        k = [cont.saldo(df_all[df_all["mes"] == m], g["costo"] + g["servicios"] + g["personal"] + g["otros_gastos"]) for m in meses]
        fig = go.Figure([go.Bar(x=meses, y=v, name="Ventas", marker_color="#2f7d5b"),
                         go.Bar(x=meses, y=k, name="Compras y gastos", marker_color="#c46a5a")])
        fig.update_xaxes(type="category")
        fig.update_layout(barmode="group", title="Ventas vs. compras y gastos por mes", height=340, margin=dict(t=50, b=20),
                          legend=dict(orientation="h", y=-0.2))
        col1.plotly_chart(fig, width="stretch")
    gastos = {"Costo/compras": er["costo"], "Personal": er["personal"], "Servicios": er["servicios"],
              "Tributos": er["tributos"], "Otros": er["otros_gastos"], "Financieros": er["financieros"],
              "Depreciación": er["depreciacion"]}
    gastos = {k: v for k, v in gastos.items() if v > 0}
    if gastos:
        fig = go.Figure(go.Pie(labels=list(gastos), values=list(gastos.values()), hole=0.55))
        fig.update_layout(title="Composición de gastos", height=340, margin=dict(t=50, b=20))
        col2.plotly_chart(fig, width="stretch")
    st.subheader("Últimos documentos")
    ult = [d for d in docs if d["estado"] == "registrado"][-8:][::-1]
    tabla(pd.DataFrame([{"Fecha": d["fecha"], "Tipo": d["tipo"], "Comprobante": f"{d['serie']}-{d['numero']}",
                         "Contraparte": d["contraparte_nombre"], "Total": d["total"]} for d in ult]))


def pg_subir(owner, emp, p, docs):
    st.header("Subir documentos")
    st.write("Facturas, boletas, recibos por honorarios, planillas o vouchers (PDF, PNG, JPG). Máx. 4.5 MB por archivo.")
    st.caption("El archivo no se guarda en la app: solo se conserva la información del asiento. Guarda tú el comprobante original.")
    OPC_NAT = {"Que la IA decida": "", "Mercadería para reventa": "Si es una compra, es MERCADERÍA PARA REVENTA (cuenta de compras de mercadería).",
               "Gasto (consumo u operación)": "Si es una compra, es un GASTO de consumo u operación (NO mercadería): usa una cuenta de gasto adecuada al concepto.",
               "Activo fijo": "Si es una compra, es un ACTIVO FIJO (inmuebles, maquinaria y equipo)."}
    for nombre_n in p.get("naturalezas_extra", {}):
        OPC_NAT[nombre_n] = (f"Si es una compra, es: {nombre_n.upper()} (usa la cuenta de compras que corresponda a esa naturaleza, "
                             "NO la de mercadería para reventa).")
    k1, k2 = st.columns([1, 2])
    nat = k1.selectbox("Tipo de compra (opcional)", list(OPC_NAT), key="nat_up",
                       help="Se aplica a todos los archivos de esta tanda. Si subes documentos mezclados, deja «Que la IA decida» y corrige después con Reclasificar.")
    nota = k2.text_input("Indicación para la IA (opcional)", key="nota_up", placeholder="Ej.: el balón de gas es gasto de cocina")
    pista = " ".join(x for x in (OPC_NAT[nat], nota.strip()) if x)
    n = st.session_state.setdefault("up_n", 0)
    archivos = st.file_uploader("Arrastra tus documentos aquí", type=["pdf", "png", "jpg", "jpeg", "webp"],
                                accept_multiple_files=True, key=f"up_{n}")
    if archivos and st.button(f"Procesar {len(archivos)} documento(s) con Claude", type="primary"):
        barra, errores = st.progress(0.0), []
        for i, f in enumerate(archivos):
            with st.spinner(f"Claude está leyendo {f.name}…"):
                try:
                    datos = f.getvalue()
                    doc = ia.extraer(f.name, f.type or "", datos, emp, p, pista)
                    db.crear_documento(owner, doc, f.name, "", None)   # el archivo no se guarda: solo la información
                except Exception as e:  # noqa: BLE001
                    errores.append(f"{f.name}: {e}")
            barra.progress((i + 1) / len(archivos))
        st.session_state.up_err = errores
        st.session_state.up_n = n + 1
        st.rerun()
    for e in st.session_state.pop("up_err", []):
        st.error(e)
    st.divider()
    pend = [d for d in docs if d["estado"] == "pendiente"]
    st.subheader(f"Por revisar ({len(pend)})")
    if not pend:
        st.caption("No hay documentos pendientes.")
    for d in pend:
        revisar(owner, emp, p, d)


def por_revisar(owner, emp, p, docs):
    pend = [x for x in docs if x["estado"] == "pendiente"]
    st.subheader(f"Por revisar ({len(pend)})")
    if not pend:
        st.caption("No hay operaciones pendientes.")
    for x in pend:
        revisar(owner, emp, p, x)


CONSTRUCTORES = {"Venta": ops.venta, "Compra (mercadería, insumos)": ops.compra, "Gasto (servicios y consumo)": ops.compra,
                 "Activo fijo": ops.compra, "Honorarios": ops.honorarios, "Planilla": ops.planilla,
                 "Cobranza a cliente": ops.cobranza, "Pago a proveedor o deuda": ops.pago,
                 "Aporte de capital": ops.aporte_capital, "Asiento manual": ops.manual}
TIPO_IA_A_FORM = {"venta": "Venta", "compra": "Compra (mercadería, insumos)", "gasto": "Gasto (servicios y consumo)",
                  "activo_fijo": "Activo fijo", "honorarios": "Honorarios", "planilla": "Planilla",
                  "cobranza": "Cobranza a cliente", "pago": "Pago a proveedor o deuda", "aporte_capital": "Aporte de capital"}


def registro_ia(owner, emp, p, n):
    """Registro inteligente: el usuario escribe la operación y la IA rellena el formulario; el asiento queda por revisar."""
    st.write("Escribe qué pasó, con tus palabras. La IA rellena los datos y deja el asiento **por revisar**: tú lo corriges o lo registras.")
    st.caption("Ejemplo: «Vendí 15000 de mercadería, gaseosas de 1 lt que tenía en almacén, al cliente Distribuidora Sur, a crédito a 30 días». "
               "Una operación por vez.")
    if st.session_state.pop("ia_ok", None):
        st.success("Asiento generado. Revísalo abajo, en «Por revisar», y pulsa Registrar.")
    texto = st.text_area("Describe la operación", key=f"ia_txt_{n}", height=110, max_chars=1500,
                         placeholder="Ej.: Compré 3000 de hamburguesas a Proveedor SAC, pagué por transferencia")
    if st.button("Generar con IA", type="primary", key=f"ia_btn_{n}", disabled=not texto.strip()):
        local, imp_n = emp["moneda"], p["impuesto"]
        try:
            with st.spinner("Interpretando la operación…"):
                r = ia.interpretar_operacion(texto, emp, p, date.today().isoformat())
        except (ValueError, RuntimeError) as e:
            return st.error(str(e))
        if r["tipo"] == "no_claro":
            return st.warning(r["pregunta"])
        tipo_op = TIPO_IA_A_FORM[r["tipo"]]
        if r["moneda"] != local and r["tipo_cambio"] <= 0:
            return st.warning(f"La operación está en {r['moneda']}: indica el tipo de cambio en la frase (por ejemplo «a 3.75») o usa el formulario.")
        forma = {"credito": ops.FORMAS[0], "banco": ops.FORMAS[1], "caja": ops.FORMAS[2]}[r["forma"]]
        if r["tipo"] in ("cobranza", "pago", "aporte_capital") and forma == ops.FORMAS[0]:
            forma = ops.FORMAS[1]
        con_impuesto = r["tipo"] in ("venta", "compra", "gasto", "activo_fijo", "honorarios")
        if con_impuesto and r["impuesto"] != "sin" and not (r["tasa"] or p["tasa_impuesto"]):
            return st.warning(f"No sé qué tasa de {imp_n} aplicar. Indícala en la frase (por ejemplo «con {imp_n} de 18%») o di que no lleva impuesto.")
        d = {"moneda": r["moneda"], "tc": r["tipo_cambio"] or 1.0, "glosa": r["glosa"], "documento": r["documento"],
             "id": r["tercero_id"], "nombre": r["tercero_nombre"], "forma": forma, "modo_imp": r["impuesto"],
             "tasa": r["tasa"] or float(round((p["tasa_impuesto"] or 0.0) * 100, 2)), "igv_manual": 0.0, "ng_manual": 0.0,
             "fecha": r["fecha"], "comprobante": r["comprobante"] if r["comprobante"] in ops.COMPROBANTES else "Factura",
             "monto": r["monto"], "vence": r["vence"] if forma == ops.FORMAS[0] else None, "destino": r["destino"],
             "costo": r["costo"]}
        if forma == ops.FORMAS[0] and not d["vence"] and r["tipo"] in ("venta", "compra", "gasto", "activo_fijo", "honorarios"):
            d["vence"] = (date.fromisoformat(r["fecha"]) + timedelta(days=30)).isoformat()
            r["supuestos"].append("No indicaste plazo: se supuso fecha límite de pago a 30 días.")
        if r["tipo"] == "venta":
            d["cuenta"] = p["cuentas_base"]["ventas" if r["se_vende"] == "mercaderias" else "ventas_servicios"]
        elif r["tipo"] in ("compra", "gasto", "activo_fijo"):
            d["cuenta"] = r["cuenta"]
        elif r["tipo"] == "honorarios":
            d["retenciones"] = {i: (r["monto"] >= x["umbral"] if x.get("umbral") else True)
                                for i, x in enumerate(p["honorarios"]["retenciones"])}
        elif r["tipo"] == "planilla":
            cfg = p["planilla"]
            d.update({"bruto": r["monto"], "moneda": local, "tc": 1.0, "retenciones": {},
                      "aporte": round(r["monto"] * cfg["aporte_pct"] / 100, 2) if cfg.get("aporte_pct") else 0.0})
        try:
            doc = CONSTRUCTORES[tipo_op](p, d)
        except (ValueError, KeyError) as e:
            return st.error(f"No se pudo armar el asiento: {e}")
        if r["tipo"] == "planilla":
            doc["alertas"].append("Planilla por IA: no incluye retenciones de los trabajadores. Ajusta el asiento si corresponde.")
        for s_ in r["supuestos"]:
            doc["alertas"].append("IA: " + s_)
        doc["alertas"].append(f"Generado con registro inteligente a partir de: «{texto.strip()[:200]}». Verifica los datos.")
        db.crear_documento(owner, doc, "Registro inteligente (IA)", "", None)
        st.session_state.reg_n = n + 1
        st.session_state.ia_ok = True
        st.rerun()


def pg_registrar(owner, emp, p, docs):
    st.header("Registrar operación")
    st.write("Elige el tipo de operación y llena sus datos. La app arma el asiento y tú lo revisas antes de registrarlo.")
    n = st.session_state.setdefault("reg_n", 0)
    local, imp_n, plan = emp["moneda"], p["impuesto"], dict(p["plan"])
    if st.session_state.pop("reg_ok", False):
        st.success("Asiento generado. Revísalo abajo, en «Por revisar», y pulsa Registrar.")
    tipo_op = st.selectbox("Tipo de operación", ops.TIPOS, key="reg_tipo")
    if tipo_op == ops.IA:
        registro_ia(owner, emp, p, n)
        st.divider()
        return por_revisar(owner, emp, p, docs)
    K = lambda x: f"r{n}_{ops.TIPOS.index(tipo_op)}_{x}"  # noqa: E731
    es_doc = tipo_op in ("Venta", "Compra (mercadería, insumos)", "Gasto (servicios y consumo)", "Activo fijo", "Honorarios")
    con_monto = tipo_op not in ("Planilla", "Asiento manual")
    opc = ia.opciones_naturaleza(p)
    fmt = lambda c: f"{c} – {plan[c]}"                    # noqa: E731
    d = {"moneda": local, "tc": 1.0, "glosa": "", "documento": "", "id": "", "nombre": "", "forma": ops.FORMAS[1],
         "modo_imp": "incluido", "tasa": 0.0, "igv_manual": 0.0, "ng_manual": 0.0}

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        d["fecha"] = c1.date_input("Fecha", value=date.today(), key=K("fecha")).isoformat()
        if es_doc:
            d["comprobante"] = c2.selectbox("Comprobante", ops.COMPROBANTES, key=K("comp"))
            d["documento"] = c3.text_input("N° de documento (serie-número)", key=K("doc"), placeholder="F001-00123")
            tercero = "Cliente" if tipo_op == "Venta" else ("Persona o proveedor" if tipo_op == "Honorarios" else "Proveedor")
            t1, t2 = st.columns([1, 2])
            d["id"] = t1.text_input(f"{p['id_fiscal']} del {tercero.lower()}", key=K("id"), placeholder=p["id_ejemplo"])
            d["nombre"] = t2.text_input(f"Razón social o nombre del {tercero.lower()}", key=K("nom"))
        elif tipo_op in ("Cobranza a cliente", "Pago a proveedor o deuda", "Aporte de capital"):
            d["documento"] = c2.text_input("N° de operación o voucher", key=K("doc"))
            quien = {"Cobranza a cliente": "cliente", "Pago a proveedor o deuda": "proveedor", "Aporte de capital": "socio"}[tipo_op]
            t1, t2 = st.columns([1, 2])
            d["id"] = t1.text_input(f"{p['id_fiscal']} del {quien} (recomendado)", key=K("id"), placeholder=p["id_ejemplo"])
            d["nombre"] = t2.text_input(f"Nombre del {quien} (recomendado)", key=K("nom"),
                                        help="Con el nombre o el ID, la operación aparece en el Análisis de cuenta de ese tercero.")

        if es_doc:
            etiquetas = {"incluido": f"El monto ya incluye {imp_n}", "agregar": f"Sumar {imp_n} al monto",
                         "manual": f"Escribir el monto del {imp_n}", "sin": f"Sin {imp_n} (no gravado o exonerado)"}
            d["modo_imp"] = st.radio("Impuesto", list(etiquetas), format_func=lambda k: etiquetas[k], horizontal=True, key=K("imp"))
        if con_monto:
            m1, m2, m3 = st.columns(3)
            otras = [m for m in (p.get("monedas") or ["USD", "EUR"]) if m != local]
            d["moneda"] = m1.selectbox("Moneda", [local] + otras, key=K("mon"))
            if d["moneda"] != local:
                d["tc"] = m2.number_input(f"Tipo de cambio (1 {d['moneda']} = ? {local})", min_value=0.0, value=0.0, step=0.01,
                                          format="%.4f", key=K("tc"))
            d["monto"] = m3.number_input("Base imponible (sin impuesto)" if d.get("modo_imp") == "manual" else "Monto",
                                         min_value=0.0, step=1.0, format="%.2f", key=K("monto"))

        if es_doc:
            if d["modo_imp"] in ("incluido", "agregar"):
                tc1, _ = st.columns([1, 3])
                d["tasa"] = tc1.number_input(f"Tasa de {imp_n} (%)", min_value=0.0, max_value=100.0, step=0.5,
                                             value=float(round((p["tasa_impuesto"] or 0.0) * 100, 2)), key=K("tasa"))
            elif d["modo_imp"] == "manual":
                x1, x2 = st.columns(2)
                d["igv_manual"] = x1.number_input(f"Monto del {imp_n}", min_value=0.0, step=1.0, format="%.2f", key=K("igvm"))
                d["ng_manual"] = x2.number_input("No gravado o exonerado (opcional)", min_value=0.0, step=1.0, format="%.2f", key=K("ngm"),
                                                 help="Importes del comprobante que no llevan impuesto (exonerado, otros cargos).")
                st.caption("Total = base imponible + monto del impuesto + no gravado.")
            d["forma"] = st.radio("Forma de pago o cobro", ops.FORMAS, horizontal=True, key=K("forma"))
            if d["forma"] == ops.FORMAS[0]:
                fv, _ = st.columns([1, 2])
                fecha_base = date.fromisoformat(d["fecha"])
                d["vence"] = fv.date_input("Fecha límite de cobro" if tipo_op == "Venta" else "Fecha límite de pago",
                                           value=fecha_base + timedelta(days=30), key=K("vence"),
                                           help="Puede ser aproximada. Si vence en más de 12 meses, el saldo se muestra como no corriente "
                                                "en la Situación Financiera.").isoformat()

            if tipo_op == "Venta":
                por_def = 1 if emp["actividad"] in ("Servicios", "Restaurante") else 0
                vende = st.radio("Se vende", ["Mercaderías", "Servicios"], index=por_def, horizontal=True, key=K("vende"))
                d["cuenta"] = p["cuentas_base"]["ventas" if vende == "Mercaderías" else "ventas_servicios"]
                if vende == "Mercaderías" and p.get("costo_venta"):
                    cc1, _ = st.columns([1, 2])
                    d["costo"] = cc1.number_input(f"Costo de la mercadería vendida ({local})", min_value=0.0, step=1.0, format="%.2f",
                                                  key=K("costo"), help="Lo que te costó lo que vendes ahora. La compra va al inventario "
                                                  "y, al vender, se registra el costo de ventas. Si lo dejas en 0, podrás agregarlo al revisar el asiento.")
            elif tipo_op == "Compra (mercadería, insumos)":
                naturalezas = [k for k in opc if not k.startswith(("Gasto", "Activo"))]
                a1, a2 = st.columns([1, 2])
                nat = a1.selectbox("Naturaleza", naturalezas, key=K("nat"))
                d["cuenta"] = a2.selectbox("Cuenta", opc[nat], format_func=fmt, key=K(f"cta_{nat}"))
            elif tipo_op == "Gasto (servicios y consumo)":
                d["cuenta"] = st.selectbox("Cuenta de gasto", opc["Gasto (consumo u operación)"], format_func=fmt, key=K("cta"))
            elif tipo_op == "Activo fijo":
                d["cuenta"] = st.selectbox("Cuenta de activo fijo", opc["Activo fijo"], format_func=fmt, key=K("cta"))
            elif tipo_op == "Honorarios":
                rets = p["honorarios"]["retenciones"]
                d["retenciones"] = {}
                for i, r in enumerate(rets):
                    umbral = r.get("umbral")
                    por_defecto = (d["monto"] >= umbral) if umbral else True
                    d["retenciones"][i] = st.checkbox(r["label"] + (f" — corresponde si el pago es de {umbral:,.0f} o más" if umbral else ""),
                                                      value=por_defecto, key=K(f"ret{i}_{por_defecto}"))
                if not rets:
                    st.caption("Este país no tiene retenciones automáticas aquí: si hay una, agrégala en el asiento antes de registrar.")
        elif tipo_op == "Pago a proveedor o deuda":
            d["destino"] = st.selectbox("¿Qué se paga?", ["Proveedores", "Remuneraciones por pagar", "Tributos por pagar"], key=K("dest"))
            d["forma"] = st.radio("Se paga con", ops.FORMAS[1:], horizontal=True, key=K("forma"))
        elif tipo_op in ("Cobranza a cliente", "Aporte de capital"):
            d["forma"] = st.radio("Ingresa a", ops.FORMAS[1:], horizontal=True, key=K("forma"))
        elif tipo_op == "Planilla":
            cfg = p["planilla"]
            d["moneda"] = local
            b1, b2 = st.columns(2)
            d["bruto"] = b1.number_input("Remuneración bruta total", min_value=0.0, step=1.0, format="%.2f", key=K("bruto"))
            if cfg.get("aporte_pct"):
                auto = b2.checkbox(f"Calcular {cfg['aporte_label']} automáticamente", value=True, key=K("auto"))
                d["aporte"] = round(d["bruto"] * cfg["aporte_pct"] / 100, 2) if auto else b2.number_input(
                    cfg["aporte_label"], min_value=0.0, step=1.0, format="%.2f", key=K("aporte"))
            else:
                d["aporte"] = b2.number_input(cfg["aporte_label"], min_value=0.0, step=1.0, format="%.2f", key=K("aporte"))
            d["retenciones"] = {}
            cols = st.columns(max(1, min(3, len(cfg["retenciones"]))))
            for i, (label, cuenta) in enumerate(cfg["retenciones"]):
                d["retenciones"][cuenta] = d["retenciones"].get(cuenta, 0.0) + cols[i % len(cols)].number_input(
                    label, min_value=0.0, step=1.0, format="%.2f", key=K(f"ret{i}"))
            neto = round(d["bruto"] - sum(d["retenciones"].values()), 2)
            st.caption(f"Costo laboral: {money(d['bruto'] + d['aporte'], local)} · Neto a pagar a los trabajadores: {money(neto, local)}")

        d["glosa"] = st.text_input("Descripción o glosa (opcional)", key=K("glosa"),
                                   placeholder="Ej.: compra de hamburguesas, planilla de octubre…")

        # vista previa de importes
        if es_doc and (d.get("monto", 0) + d["igv_manual"] + d["ng_manual"]) > 0:
            if d["moneda"] != local and d["tc"] <= 0:
                st.warning("Escribe el tipo de cambio para ver los importes en moneda local.")
            else:
                v = ops.a_local(ops.importes(d["monto"], d["modo_imp"], d["tasa"], p.get("impuesto_sobre_total", False),
                                             d["igv_manual"], d["ng_manual"]), d["tc"] or 1)
                st.caption(f"En {local}: base {money(v['base'])} · {imp_n} {money(v['impuesto'])} · "
                           f"no gravado {money(v['no_gravado'])} · **total {money(v['total'])}**")

    if st.button("Generar asiento", type="primary", key=K("gen")):
        error = None
        if con_monto and d["monto"] + (d["igv_manual"] + d["ng_manual"] if d["modo_imp"] == "manual" else 0) <= 0:
            error = "Escribe un monto mayor a cero."
        elif con_monto and d["moneda"] != local and d["tc"] <= 0:
            error = "Escribe el tipo de cambio."
        elif es_doc and d["modo_imp"] in ("incluido", "agregar") and d["tasa"] <= 0:
            error = f"Indica la tasa de {imp_n} o elige «Sin {imp_n}»."
        elif tipo_op == "Planilla" and d["bruto"] <= 0:
            error = "Escribe la remuneración bruta."
        if error:
            st.error(error)
        else:
            try:
                doc = CONSTRUCTORES[tipo_op](p, d)
                if es_doc and d["modo_imp"] == "manual" and p["tasa_impuesto"] and not p.get("impuesto_sobre_total"):
                    esperado = round(d["monto"] * p["tasa_impuesto"], 2)
                    if abs(d["igv_manual"] - esperado) > max(0.05, esperado * 0.02):
                        doc["alertas"].append(f"El {imp_n} escrito ({d['igv_manual']:,.2f}) difiere del calculado con la tasa general "
                                              f"({esperado:,.2f}). Verifícalo.")
                if d["id"].strip() and not re.fullmatch(p["id_regex"], normalizar_id(d["id"])):
                    doc["alertas"].append(f"El {p['id_fiscal']} escrito no tiene un formato válido para {p['nombre']}. Verifícalo.")
                db.crear_documento(owner, doc, f"Registro manual – {tipo_op}", "", None)
                st.session_state.reg_n = n + 1
                st.session_state.reg_ok = True
                st.rerun()
            except (ValueError, KeyError) as e:
                st.error(str(e))

    st.divider()
    por_revisar(owner, emp, p, docs)


def revisar(owner, emp, p, d):
    plan = dict(p["plan"])
    ok_cuadre, td, th = ia.validar_asiento(d["asiento"])
    etiqueta = f"{d['archivo_nombre']} — {d['tipo']} · {d['tipo_comprobante']} {d['serie']}-{d['numero']} · {money(d['total'], SIM(emp, p))}"
    with st.expander(("✅ " if ok_cuadre and not d["alertas"] else "⚠️ ") + etiqueta, expanded=True):
        for a in d["alertas"]:
            st.warning(a)
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
        fecha = c1.text_input("Fecha (AAAA-MM-DD)", d["fecha"], key=f"f_{d['id']}")
        tipos = ["compra", "venta", "planilla", "honorarios", "otro"]
        tipo = c2.selectbox("Tipo", tipos, index=tipos.index(d["tipo"]) if d["tipo"] in tipos else 4, key=f"t_{d['id']}")
        vence = c3.text_input("Fecha límite de pago", d.get("vence") or "", key=f"v_{d['id']}", placeholder="AAAA-MM-DD",
                              help="Opcional. Para ventas o compras a crédito: sirve para separar corriente y no corriente.").strip()
        glosa = c4.text_input("Glosa", d["glosa"], key=f"g_{d['id']}")
        tercero = " ".join(x for x in (d["contraparte_nombre"], f"({d['contraparte_id']})" if d["contraparte_id"] else "") if x)
        st.caption(f"{tercero + ' · ' if tercero else ''}Base {money(d['base'])} · "
                   f"{p['impuesto']} {money(d['impuesto'])} · Total {money(d['total'])}")
        if tipo == "compra":
            opts = ia.opciones_naturaleza(p)
            nombres = list(opts)
            r1, r2, r3 = st.columns([1.3, 2, 1])
            nat_r = r1.selectbox("Naturaleza de la compra", nombres, index=ia.naturaleza_actual(d["asiento"], p), key=f"nat_{d['id']}")
            actuales = [str(l["cuenta"]) for l in d["asiento"] if int(l.get("grupo", 1) or 1) == 1 and l["debe"] > 0]
            idx_c = next((opts[nat_r].index(c) for c in actuales if c in opts[nat_r]), 0)
            cta_r = r2.selectbox("Cuenta", opts[nat_r], index=idx_c, format_func=lambda c: f"{c} – {plan[c]}", key=f"ctan_{d['id']}_{nat_r}")
            r3.write("")
            if r3.button("Reclasificar", key=f"rec_{d['id']}", help="Cambia la cuenta de la compra y rehace los asientos de destino"):
                res = ia.reclasificar_compra(d["asiento"], p, cta_r)
                if res:
                    nuevo, al = res
                    previas = [x for x in d["alertas"] if "destino" not in x.lower()]
                    db.actualizar_documento(owner, d["id"], asiento=nuevo,
                                            alertas=[f"Reclasificado por ti a: {cta_r} {plan[cta_r]}."] + previas + al)
                    st.rerun()
                else:
                    st.error("No se pudo reclasificar: revisa que el asiento tenga la compra y su contrapartida.")
        if ia.pide_costo_venta(d["asiento"], d["tipo"], p):
            c1, c2 = st.columns([3, 1])
            costo = c1.number_input("Costo de la mercadería vendida (para el asiento de costo de ventas)", min_value=0.0,
                                    step=1.0, key=f"cv_{d['id']}", help="Lo que te costó lo que vendiste (inventario permanente).")
            c2.write("")
            if c2.button("Agregar costo de ventas", key=f"cvb_{d['id']}", disabled=costo <= 0):
                db.actualizar_documento(owner, d["id"], asiento=d["asiento"] + ia.lineas_costo_venta(d["asiento"], p, costo))
                st.rerun()
        filas = d["asiento"] or [{"cuenta": "", "nombre": "", "debe": 0.0, "haber": 0.0}]
        base = pd.DataFrame([{"grupo": int(l.get("grupo", 1) or 1), "cuenta": l["cuenta"], "nombre": l["nombre"],
                              "debe": l["debe"], "haber": l["haber"]} for l in filas])
        libres = bool(p.get("cuentas_libres"))
        ed = st.data_editor(base, num_rows="dynamic", width="stretch", hide_index=True, key=f"ed_{d['id']}",
                            column_config={"grupo": st.column_config.NumberColumn("Asiento N°", min_value=1, max_value=9, step=1,
                                                                                  format="%d", default=1),
                                           "cuenta": (st.column_config.TextColumn("Cuenta (código)", required=True) if libres
                                                      else st.column_config.SelectboxColumn("Cuenta", options=list(plan), required=True)),
                                           "nombre": st.column_config.TextColumn("Denominación", disabled=not libres),
                                           "debe": st.column_config.NumberColumn("Debe", format="%.2f", default=0.0),
                                           "haber": st.column_config.NumberColumn("Haber", format="%.2f", default=0.0)})
        lineas = [{"cuenta": str(r["cuenta"]).strip(), "nombre": plan.get(str(r["cuenta"]).strip()) or str(r["nombre"] or "").strip(),
                   "debe": float(r["debe"] or 0), "haber": float(r["haber"] or 0),
                   "grupo": int(r["grupo"]) if pd.notna(r["grupo"]) else 1}
                  for _, r in ed.iterrows() if str(r["cuenta"]).strip()]
        invalidas = [l["cuenta"] for l in lineas if l["cuenta"] not in plan and not (
            libres and re.fullmatch(r"[1-5]\d{3,}", l["cuenta"]) and l["nombre"])]
        if invalidas:
            st.error("Cuenta inválida: " + ", ".join(invalidas) + (". Usa un código de 4 dígitos (1 a 5) y escribe su nombre." if libres else ". Elige una del plan."))
        cuadra, td, th = ia.validar_asiento(lineas)
        (st.success if cuadra else st.error)(f"Debe {money(td)}  |  Haber {money(th)}" + ("" if cuadra else "  — un asiento no cuadra"))
        if len({l["grupo"] for l in lineas}) > 1:
            st.caption("Esta operación genera varios asientos; cada uno debe cuadrar por separado. "
                       "Las líneas con el mismo «Asiento N°» forman un asiento.")
        b1, b2, b3, _ = st.columns(4)
        fecha_ok = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha)) and (not vence or bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", vence)))
        if b1.button("✔ Registrar", key=f"r_{d['id']}", type="primary", disabled=not (cuadra and fecha_ok and not invalidas)):
            if db.duplicado(owner, {**d, "tipo": tipo}) and not st.session_state.get(f"dup_{d['id']}"):
                st.session_state[f"dup_{d['id']}"] = True
                st.warning("Este comprobante ya está registrado. Pulsa Registrar otra vez si quieres duplicarlo.")
            else:
                db.actualizar_documento(owner, d["id"], estado="registrado", fecha=fecha, tipo=tipo, glosa=glosa, asiento=lineas,
                                        vence=vence or None)
                st.rerun()
        if b2.button("Guardar cambios", key=f"s_{d['id']}"):
            db.actualizar_documento(owner, d["id"], fecha=fecha, tipo=tipo, glosa=glosa, asiento=lineas, vence=vence or None)
            st.toast("Cambios guardados")
        if b3.button("Descartar", key=f"x_{d['id']}"):
            db.eliminar_documento(owner, d["id"])
            st.rerun()


def pg_diario(owner, emp, p, docs):
    st.header("Libro Diario")
    df = df_diario(docs)
    if df.empty:
        return st.info("Sin asientos registrados.")
    tabla(df)
    st.write(f"**Totales** — Debe: {money(df['Debe'].sum())} · Haber: {money(df['Haber'].sum())}")


def pg_registro(titulo, tipo, docs):
    st.header(titulo)
    df = df_registro(docs, tipo)
    if df.empty:
        return st.info("Sin registros.")
    tabla(df)
    t = df[["Base imponible", "Impuesto", "No gravado", "Total"]].sum()
    st.write("**Totales** — " + " · ".join(f"{k}: {money(v)}" for k, v in t.items()))


def pg_planillas(owner, emp, p, docs):
    st.header("Planillas y honorarios")
    nom = p["nomina"]
    f = []
    for d in docs:
        if d["estado"] == "registrado" and d["tipo"] in ("planilla", "honorarios"):
            suma = lambda toks, k: sum(l[k] for l in d["asiento"] if cont.coincide(str(l["cuenta"]), toks))  # noqa: E731
            f.append({"Fecha": d["fecha"], "Tipo": d["tipo"], "Detalle": d["glosa"],
                      "Gasto de personal / honorarios": suma(nom["gasto"], "debe"),
                      "Aportes y retenciones": suma(nom["aportes"], "haber"),
                      "Neto a pagar": suma(nom["neto"], "haber")})
    if not f:
        return st.info("Sin planillas ni honorarios registrados.")
    tabla(pd.DataFrame(f))


def pg_impuestos(owner, emp, p, docs):
    st.header(f"{p['impuesto']} y tributos")
    df = cont.impuestos_por_mes(docs, p, emp["pct_renta"] or 0)
    if df.empty:
        return st.info("Sin datos.")
    tabla(df)
    st.caption(f"Valores referenciales para tu declaración ({p['reporte_impuestos']}). El saldo a favor de un mes se arrastra al siguiente. "
               "Valida siempre con tu contador.")


def pg_eeff(owner, emp, p, docs):
    st.header("Estados financieros")
    per = selector_periodo(docs, "per_eeff")
    df_all = cont.lineas(docs)
    if df_all.empty:
        return st.info("Sin asientos registrados.")
    g, df = p["grupos"], cont.filtrar(df_all, per)
    opciones = ["Estado de Resultados", "Estado de Situación Financiera", "Balance de Comprobación", "Resumen financiero"]
    st.write("Seleccionar estado financiero")
    elegido = st.segmented_control("Seleccionar estado financiero", opciones, default=opciones[0], key="eeff_sel",
                                   label_visibility="collapsed") or opciones[0]
    st.subheader(elegido)
    if elegido == opciones[0]:
        e = cont.estado_resultados(df, g)
        t_renta = float(emp.get("tasa_renta") or 0)
        renta = round(max(0.0, e["antes_impuestos"]) * t_renta / 100, 2)
        extra = ([(f"(−) Impuesto a la renta estimado ({t_renta:g}%)", -renta),
                  ("RESULTADO NETO ESTIMADO", e["antes_impuestos"] - renta, "t")] if t_renta > 0 else [])
        estado([("Ventas", e["ventas"]), ("(−) Descuentos y devoluciones", -e["descuentos"]), ("VENTAS NETAS", e["ventas_netas"], "t"),
                ("(−) Costo de ventas / compras", -e["costo"]), ("UTILIDAD BRUTA", e["utilidad_bruta"], "t"),
                ("(−) Gastos de personal", -e["personal"]), ("(−) Servicios de terceros", -e["servicios"]),
                ("(−) Tributos", -e["tributos"]), ("(−) Otros gastos de gestión", -e["otros_gastos"]),
                ("(−) Depreciación", -e["depreciacion"]), ("UTILIDAD OPERATIVA", e["utilidad_operativa"], "t"),
                ("(+) Otros ingresos", e["otros_ingresos"]), ("(−) Gastos financieros", -e["financieros"]),
                ("RESULTADO ANTES DE IMPUESTOS", e["antes_impuestos"], "t")] + extra)
        if extra:
            st.caption("Estimación: la tasa anual se aplica a la utilidad del periodo elegido. La determinación definitiva del "
                       "impuesto la hace tu contador en la declaración anual.")
    elif elegido == opciones[1]:
        S = an.situacion_clasificada(docs, df_all, g, per)
        ta, tp, tpt = S["ta"], S["tp"], S["tpt"]
        estado([("ACTIVO", None, "t"), ("ACTIVO CORRIENTE", None, "s")] + S["ac"]
               + [("TOTAL ACTIVO CORRIENTE", S["tac"], "s"), ("ACTIVO NO CORRIENTE", None, "s")] + S["anc"]
               + [("TOTAL ACTIVO NO CORRIENTE", S["tanc"], "s"), ("TOTAL ACTIVO", ta, "s"),
                  ("PASIVO", None, "t"), ("PASIVO CORRIENTE", None, "s")] + S["pc"]
               + [("TOTAL PASIVO CORRIENTE", S["tpc"], "s"), ("PASIVO NO CORRIENTE", None, "s")] + S["pnc"]
               + [("TOTAL PASIVO NO CORRIENTE", S["tpnc"], "s"), ("TOTAL PASIVO", tp, "s"),
                  ("PATRIMONIO", None, "t")] + S["pt"]
               + [("TOTAL PATRIMONIO", tpt, "s"), ("TOTAL PASIVO Y PATRIMONIO", tp + tpt, "s")])
        st.caption("Corriente: vence dentro de 12 meses del corte. Las cuentas por cobrar y por pagar sin fecha límite se tratan como "
                   f"de corto plazo. Corte: {S['corte'].isoformat()}.")
        if abs(ta - tp - tpt) > 0.05:
            st.error("El balance no cuadra: revisa los asientos (puede faltar el aporte de capital o saldos iniciales).")
        else:
            st.success("Balance cuadrado")
    elif elegido == opciones[2]:
        tabla(cont.balance_comprobacion(df))
    else:
        st.write("Informe de la empresa en hojas A4: portada, situación financiera, resultados, indicadores, análisis de cuentas "
                 "y conclusiones. Elige el periodo arriba y pulsa el botón.")
        if st.button("Generar resumen", type="primary", key="gen_resumen"):
            with st.spinner("Preparando el informe…"):
                st.session_state["informe"] = (per, informe.construir(emp, p, docs, per, SIM(emp, p)))
        guardado = st.session_state.get("informe")
        if guardado:
            per_i, inf = guardado
            if per_i != per:
                st.caption(f"Este informe corresponde al periodo «{per_i}». Pulsa «Generar resumen» para actualizarlo al periodo elegido.")
            try:
                pdf = informe.a_pdf(inf)
                st.download_button("Descargar PDF", pdf, file_name=f"informe_financiero_{per_i}.pdf", mime="application/pdf", key="dl_inf")
            except Exception as e:  # noqa: BLE001
                st.error(f"No se pudo preparar el PDF: {e}")
            components.html(informe.a_html_doc(inf), height=len(inf["paginas"]) * 1141, scrolling=False)


def pg_documentos(owner, emp, p, docs):
    st.header("Documentos registrados")
    reg = [d for d in docs if d["estado"] == "registrado"][::-1]
    if not reg:
        return st.info("Sin documentos.")
    for d in reg:
        c = st.columns([1.2, 1, 2, 3, 1.2, 1])
        c[0].write(d["fecha"]); c[1].write(d["tipo"]); c[2].write(f"{d['serie']}-{d['numero']}")
        c[3].write(d["contraparte_nombre"]); c[4].write(money(d["total"], SIM(emp, p)))
        if c[5].button("🗑", key=f"del_{d['id']}", help="Eliminar documento y asiento"):
            db.eliminar_documento(owner, d["id"]); st.rerun()


def pg_config(owner, emp, p, docs):
    st.header("Configuración")
    acts = p["actividades"]
    actual = emp["actividad"] or ""
    en_lista = actual in acts and actual != paises.OTRA
    act_sel = st.selectbox("Giro del negocio", acts, index=acts.index(actual) if en_lista else acts.index(paises.OTRA), key="cfg_act")
    act_otra = st.text_input("Especificar giro", value="" if en_lista else (actual if actual != paises.OTRA else ""), max_chars=60,
                             key="cfg_act_otra", placeholder="Ej.: inmobiliaria, clínica, transporte") if act_sel == paises.OTRA else ""
    modo_actual = emp.get("modo") or "lector"
    modo_sel = st.selectbox("Modo de trabajo", list(MODOS), index=list(MODOS).index(modo_actual), format_func=lambda k: MODOS[k],
                            key="cfg_modo", help="Lector de facturas: la IA lee tus documentos. Modo simple: tú registras cada operación. "
                                                 "Tus datos y reportes se conservan al cambiar.")
    with st.form("cfg"):
        nombre = st.text_input("Razón social", emp["nombre"])
        idf = st.text_input(p["id_fiscal"], emp["id_fiscal"])
        if emp.get("logo"):
            st.image(bytes(emp["logo"]), width=120)
        logo_f = st.file_uploader("Logo de tu empresa (opcional)" if not emp.get("logo") else "Cambiar logo", type=["png", "jpg", "jpeg"])
        quitar_logo = st.checkbox("Quitar el logo actual") if emp.get("logo") else False
        if p.get("regimen_libre"):
            regimen = st.text_input("Régimen tributario", value=emp["regimen"] or "General", max_chars=100)
            r1, r2 = st.columns(2)
            tasa_renta = r1.number_input("Impuesto a la renta anual: tasa (%)", min_value=0.0, max_value=100.0,
                                         value=float(emp.get("tasa_renta") or 0), step=0.5)
            pct = r2.number_input("Pago a cuenta mensual sobre ventas (%)", min_value=0.0, max_value=100.0,
                                  value=float(emp["pct_renta"] or 0), step=0.1)
        else:
            regs = list(p["regimenes"])
            regimen = st.selectbox("Régimen tributario", regs, index=regs.index(emp["regimen"]) if emp["regimen"] in regs else 0)
            tasa_renta = st.number_input("Impuesto a la renta anual: tasa (%) (opcional)", min_value=0.0, max_value=100.0,
                                         value=float(emp.get("tasa_renta") or 0), step=0.5)
            con_pct = any(v is not None for v in p["regimenes"].values())
            pct = (st.number_input(f"% {p['pago_cuenta_label']} (sobre ventas)", value=float(emp["pct_renta"] or 0), step=0.1)
                   if con_pct else 0.0)
        notas = st.text_area("Instrucciones permanentes para la IA (opcional)", emp.get("notas_ia") or "", height=120,
                             placeholder="Ej.: Somos un restaurante. El gas, la limpieza y los útiles son gasto; "
                                         "solo las bebidas y abarrotes que revendemos son mercadería.",
                             help="La IA las lee en cada documento y tienen prioridad sobre sus reglas generales.")
        st.caption(f"País: {p['nombre']} (fijo) · Moneda: {emp['moneda']}")
        if st.form_submit_button("Guardar", type="primary"):
            idn = normalizar_id(idf)
            act = act_otra.strip() if act_sel == paises.OTRA else act_sel
            if not act:
                st.error("Especifica el giro del negocio.")
            elif not re.fullmatch(p["id_regex"], idn):
                st.error(f"El {p['id_fiscal']} no tiene un formato válido. Ejemplo: {p['id_ejemplo']}.")
            else:
                datos = dict(nombre=nombre.strip(), id_fiscal=idn, regimen=regimen.strip(), pct_renta=pct, actividad=act,
                             tasa_renta=tasa_renta, notas_ia=notas.strip(), modo=modo_sel)
                nuevo_logo = procesar_logo(logo_f)
                if nuevo_logo:
                    datos["logo"] = nuevo_logo
                elif quitar_logo:
                    datos["logo"] = None
                db.guardar_empresa(owner, datos)
                st.success("Guardado"); st.rerun()
    if True:   # el registro inteligente del modo simple también usa Claude en AWS
        st.subheader("Conexión con Claude (AWS)")
        st.caption(f"Modelo: `{ia.MODEL_ID}` · Región: `{ia.REGION}`")
        if st.button("Probar conexión con AWS"):
            with st.spinner("Probando…"):
                ok, msg = ia.probar_conexion()
            (st.success if ok else st.error)(msg)
    st.subheader("Respaldo y recuperación")
    st.download_button("⬇ Descargar respaldo en Excel", a_excel({
        "Libro diario": df_diario(docs), "Compras": df_registro(docs, "compra"), "Ventas": df_registro(docs, "venta"),
        "Impuestos": cont.impuestos_por_mes(docs, p, emp["pct_renta"] or 0),
        "Balance comprobación": cont.balance_comprobacion(cont.lineas(docs))}), file_name="contaia-respaldo.xlsx")
    st.write("Tus datos están ligados a **este navegador**. Si borras las cookies, usas modo incógnito o cambias de equipo, "
             "guarda este enlace privado para recuperarlos (no lo compartas: quien lo tenga ve tu contabilidad):")
    st.code(enlace_recuperacion(owner), language=None)
    n_arch, mb_arch = db.estadisticas_archivos(owner)
    if n_arch:
        st.subheader("Liberar espacio")
        st.write(f"Hay **{n_arch} archivo(s) original(es)** guardado(s) de versiones anteriores ({mb_arch:.1f} MB). "
                 "La app ya no guarda archivos nuevos. Borrarlos no afecta tus asientos ni tus reportes.")
        ok_arch = st.checkbox("Entiendo que ya no podré ver esos originales", key="ok_arch")
        if st.button("Borrar archivos originales", disabled=not ok_arch, key="btn_arch"):
            db.borrar_archivos(owner)
            st.session_state.pop("ok_arch", None)
            st.rerun()
    st.subheader("Empezar nuevamente")
    st.write("Vuelves a la pantalla inicial: eliges el modo de trabajo y registras los datos de una empresa (puedes cambiar de país). "
             "**Se borrarán los datos de la empresa, todos los documentos y los asientos.** Descarga antes tu respaldo.")
    ok_reset = st.checkbox("Entiendo que se borrará todo y no se puede deshacer", key="ok_reset")
    if st.button("Empezar nuevamente", disabled=not ok_reset, key="btn_reset"):
        db.borrar_empresa(owner)
        for k in ("pagina", "an_sel", "an_corte", "eeff_sel", "up_n", "up_err", "ok_reset", "nat_up", "nota_up", "per_dash", "per_eeff", "modo_sel",
                  "reg_n", "reg_tipo", "reg_ok", "cfg_modo", "cfg_act", "cfg_act_otra"):
            st.session_state.pop(k, None)
        st.rerun()
    with st.expander("Zona de peligro"):
        if st.checkbox("Entiendo que se borrarán todos mis documentos y asientos") and st.button("Borrar solo documentos y asientos"):
            db.borrar_todo(owner); st.rerun()


def con_total(df, cols, nombre_col):
    """Agrega una fila TOTAL sumando las columnas indicadas."""
    if df.empty:
        return df
    fila = {c: "" for c in df.columns}
    fila[nombre_col] = "TOTAL"
    for c in cols:
        fila[c] = round(float(df[c].sum()), 2)
    return pd.concat([df, pd.DataFrame([fila])], ignore_index=True)


def grafico_barras(nombres, valores, titulo):
    fig = go.Figure(go.Bar(x=nombres, y=valores, marker_color="#1f3a5f"))
    fig.update_layout(title=titulo, height=320, margin=dict(t=50, b=20), bargap=0.6)
    st.plotly_chart(fig, width="stretch")


def pg_analisis(owner, emp, p, docs):
    st.header("Análisis de cuenta")
    g, s = p["grupos"], SIM(emp, p)
    CUENTAS = {
        "Cuentas por cobrar": dict(tokens=g["cxc"], signo=1, tercero="Cliente", et=("Facturado", "Cobrado / abonos", "Saldo por cobrar")),
        "Cuentas por pagar": dict(tokens=g["cxp"], signo=-1, tercero="Proveedor", et=("Facturado", "Pagado / abonos", "Saldo por pagar")),
        "Tributos": dict(tokens=g["impuestos"], signo=-1, cols=("Debe", "Haber"), saldo="Saldo (por pagar +, a favor −)"),
        "Mercaderías e inventarios": dict(tokens=g["inventarios"], signo=1, cols=("Entradas", "Salidas"), saldo="Valor disponible",
                                          terceros="Compras por proveedor"),
        "Efectivo (caja y bancos)": dict(tokens=g["efectivo"], signo=1, cols=("Ingresos", "Egresos"), saldo="Saldo disponible"),
        "Remuneraciones por pagar": dict(tokens=g["remuneraciones"], signo=-1, cols=("Debe", "Haber"), saldo="Saldo por pagar"),
        "Activo fijo": dict(tokens=g["fijo"], signo=1, cols=("Adquisiciones", "Bajas y depreciación"), saldo="Valor neto",
                            terceros="Adquisiciones por proveedor"),
    }
    nombres = list(CUENTAS)
    sel = st.segmented_control("Seleccionar cuenta", nombres, default=nombres[0], key="an_sel") or nombres[0]
    corte = st.date_input("Corte al", value=date.today(), key="an_corte")
    cfg = CUENTAS[sel]
    mov = an.movimientos(docs, cfg["tokens"], hasta=corte.isoformat())
    st.subheader(sel)
    if mov.empty:
        return st.info("Todavía no hay movimientos registrados en esta cuenta hasta la fecha de corte.")

    if "tercero" in cfg:                                           # cuentas por cobrar y por pagar
        et, tercero, signo = cfg["et"], cfg["tercero"], cfg["signo"]
        plural = {"Cliente": "Clientes", "Proveedor": "Proveedores"}[tercero]
        mostrar_cero = st.checkbox(f"Mostrar también {plural.lower()} con saldo en cero", key=f"cero_{sel}")
        sal = an.saldos_por_tercero(mov, signo, et, solo_con_saldo=not mostrar_cero)
        total = float(sal[et[2]].sum()) if not sal.empty else 0.0
        k1, k2, k3 = st.columns(3)
        k1.metric(f"Total {et[2].lower()}", money(total, s))
        k2.metric(plural, f"{len(sal)}")
        if not sal.empty:
            k3.metric("Mayor saldo", money(float(sal[et[2]].iloc[0]), s), sal["Nombre"].iloc[0], delta_color="off")
        if (sal["Nombre"] == "(sin identificar)").any():
            st.warning(f"Hay movimientos sin {tercero.lower()} identificado. Escribe el nombre o el {p['id_fiscal']} al registrar "
                       "cada operación para que se asignen a la persona correcta.")
        t1, t2, t3 = st.tabs([f"Saldo por {tercero.lower()}", "Antigüedad de saldos", "Detalle"])
        with t1:
            if sal.empty:
                st.success("No hay saldos pendientes.")
            else:
                tabla(con_total(sal, list(et), "Nombre"))
                top = sal.head(10)
                grafico_barras(list(top["Nombre"]), list(top[et[2]]), f"Principales saldos – {sel.lower()}")
        with t2:
            ant = an.antiguedad(mov, signo, corte)
            if ant.empty:
                st.success("No hay saldos pendientes.")
            else:
                tabla(con_total(ant, an.TRAMOS + ["Saldo a favor", "Total"], "Nombre"))
                st.caption("Los cobros o pagos se aplican a las facturas más antiguas. La antigüedad se cuenta desde la fecha de cada "
                           f"documento hasta el corte ({corte.isoformat()}).")
        with t3:
            dfc = an.asignar_terceros(mov)
            ficha = an.ficha_terceros(dfc)
            claves = sorted(ficha, key=lambda c: ficha[c][1].upper())
            elegido = st.selectbox(tercero, claves, format_func=lambda c: f"{ficha[c][1]}  ·  {ficha[c][0]}" if ficha[c][0] else ficha[c][1],
                                   key=f"det_{sel}")
            det = dfc[dfc["clave"] == elegido].copy()
            det["Cargo"] = det["debe"] if signo > 0 else det["haber"]
            det["Abono"] = det["haber"] if signo > 0 else det["debe"]
            det["Saldo"] = (det["Cargo"] - det["Abono"]).cumsum()
            tabla(det.rename(columns={"fecha": "Fecha", "documento": "Documento", "tipo": "Tipo", "glosa": "Detalle"})
                  [["Fecha", "Documento", "Tipo", "Detalle", "Cargo", "Abono", "Saldo"]].round(2))
        return

    signo, (c_debe, c_haber) = cfg["signo"], cfg["cols"]           # tributos, existencias, efectivo, remuneraciones, activo fijo
    resumen = an.resumen_cuentas(mov, signo)
    saldo_total = float(resumen["Saldo"].sum())
    k1, k2, k3 = st.columns(3)
    k1.metric(cfg["saldo"], money(saldo_total, s))
    k2.metric(c_debe, money(float(mov["debe"].sum()), s))
    k3.metric(c_haber, money(float(mov["haber"].sum()), s))
    nombres_tabs = ["Resumen", "Movimientos", "Evolución"] + ([cfg["terceros"]] if "terceros" in cfg else [])
    tabs = st.tabs(nombres_tabs)
    with tabs[0]:
        r = resumen.rename(columns={"Debe": c_debe, "Haber": c_haber, "Saldo": cfg["saldo"]})
        tabla(con_total(r, [c_debe, c_haber, cfg["saldo"]], "Denominación"))
        mes = an.por_mes(mov, signo).rename(columns={"Debe": c_debe, "Haber": c_haber})
        st.markdown("**Por mes**")
        tabla(mes)
        if sel == "Mercaderías e inventarios":
            st.caption("El valor disponible sale de los asientos de destino a existencias. La app no registra unidades, almacenes ni productos.")
    with tabs[1]:
        cuentas = ["Todas"] + sorted(mov["cuenta"].unique())
        cta = st.selectbox("Cuenta", cuentas, key=f"cta_{sel}")
        m = an.mayor(mov, signo, cta)
        m = m.rename(columns={"fecha": "Fecha", "documento": "Documento", "tercero": "Tercero", "glosa": "Detalle", "cuenta": "Cuenta",
                              "debe": c_debe, "haber": c_haber, "saldo": "Saldo"})
        tabla(m[["Fecha", "Cuenta", "Documento", "Tercero", "Detalle", c_debe, c_haber, "Saldo"]].round(2))
    with tabs[2]:
        m = an.mayor(mov, signo, "Todas")
        fig = go.Figure(go.Scatter(x=m["fecha"], y=m["saldo"], mode="lines+markers", line=dict(color="#1f3a5f")))
        fig.update_layout(title=f"Evolución – {cfg['saldo'].lower()}", height=340, margin=dict(t=50, b=20))
        fig.update_xaxes(type="category")
        st.plotly_chart(fig, width="stretch")
    if "terceros" in cfg:
        with tabs[3]:
            ent = an.entradas_por_tercero(mov)
            if ent.empty:
                st.info("Sin entradas registradas.")
            else:
                tabla(con_total(ent, ["Entradas"], "Nombre"))
                grafico_barras(list(ent["Nombre"].head(10)), list(ent["Entradas"].head(10)), cfg["terceros"])


# ------------------------------------------------------------------ main
owner = identificar()
emp = db.get_empresa(owner)
if not emp:
    if "modo_sel" not in st.session_state:
        elegir_modo()
        st.stop()
    bienvenida(owner)
    st.stop()

p = paises.get_pais(emp["pais"])
modo = emp.get("modo") or "lector"
docs = db.listar(owner)
pend = sum(1 for d in docs if d["estado"] == "pendiente")

entrada = ("registrar", "✍️ Registrar operación", pg_registrar) if modo == "simple" else ("subir", "⬆️ Subir documentos", pg_subir)
LIBROS = {"compras": "Registro de Compras", "ventas": "Registro de Ventas", "planillas": "Planillas",
          "impuestos": f"{p['impuesto']} y tributos", "diario": "Libro Diario", "docs": "Documentos"}
RUTAS = {"dash": pg_dashboard, "eeff": pg_eeff, entrada[0]: entrada[2], "analisis": pg_analisis, "config": pg_config,
         "compras": lambda o, e, pp, d: pg_registro("Registro de Compras", "compra", d),
         "ventas": lambda o, e, pp, d: pg_registro("Registro de Ventas", "venta", d),
         "planillas": pg_planillas, "impuestos": pg_impuestos, "diario": pg_diario, "docs": pg_documentos}


def ir(destino):
    st.session_state["pagina"] = destino


def ir_libros():
    if st.session_state.get("pagina") not in LIBROS:
        st.session_state["pagina"] = "compras"


if st.session_state.get("pagina") not in RUTAS:           # p. ej. tras cambiar de modo
    st.session_state["pagina"] = "dash"
pag = st.session_state["pagina"]

with st.sidebar:
    if emp.get("logo"):
        st.image(bytes(emp["logo"]), width=110)
    st.markdown(f"### {MARCA}\n**{emp['nombre']}**  \n{p['id_fiscal']} {emp['id_fiscal']} · {p['nombre']}", unsafe_allow_html=True)

    def nav(clave, etiqueta):
        st.button(etiqueta, key=f"nav_{clave}", type="primary" if pag == clave else "secondary", width="stretch",
                  on_click=ir, args=(clave,))

    nav("dash", "📊 Dashboard")
    nav("eeff", "📑 Estados financieros")
    nav(entrada[0], entrada[1])
    en_libros = pag in LIBROS
    st.button("📚 Libros auxiliares " + ("▾" if en_libros else "▸"), key="nav_libros", type="primary" if en_libros else "secondary",
              width="stretch", on_click=ir_libros)
    if en_libros:
        for clave, etiqueta in LIBROS.items():
            st.button(etiqueta, key=f"sub_{clave}" + ("__activo" if pag == clave else ""), width="stretch", on_click=ir, args=(clave,))
    nav("analisis", "🔎 Análisis de cuenta")
    nav("config", "⚙️ Configuración")
    if pend:
        st.warning(f"Tienes {pend} {'operación(es)' if modo == 'simple' else 'documento(s)'} por revisar en «{entrada[1][2:].strip()}».")

if pag in LIBROS:
    st.caption(f"Libros auxiliares › {LIBROS[pag]}")
RUTAS[pag](owner, emp, p, docs)
