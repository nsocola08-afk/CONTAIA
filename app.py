import io
import os
import re
import uuid
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_cookies_controller import CookieController

import claude_bedrock as ia
import contabilidad as cont
import db
import paises

st.set_page_config(page_title="ContaIA", page_icon="📒", layout="wide")
COOKIE = "contaia_id"
ESTILO = """
<style>
.block-container{padding-top:2rem}
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
def bienvenida(owner):
    st.title("📒 Bienvenido a ContaIA")
    st.write("Antes de empezar, cuéntanos sobre tu empresa. Con estos datos Claude usará el plan contable y los impuestos de tu país.")
    disp = {p["nombre"]: c for c, p in paises.PAISES.items()}
    pais_nombre = st.selectbox("País", list(disp), help="Cada país usa su propio plan de cuentas e impuestos.")
    st.caption("Próximamente: " + ", ".join(paises.PROXIMAMENTE))
    p = paises.get_pais(disp[pais_nombre])
    with st.form("alta"):
        nombre = st.text_input("Nombre o razón social de la empresa")
        idf = st.text_input(f"{p['id_fiscal']} (número de identificación tributaria)", max_chars=20)
        regimen = st.selectbox("Régimen tributario", list(p["regimenes"]))
        actividad = st.selectbox("Actividad principal", p["actividades"])
        c1, c2 = st.columns(2)
        c1.text_input("Moneda principal", value=f"{p['moneda']} ({p['simbolo']})", disabled=True)
        c2.text_input("Inicio del ejercicio", value=p["inicio_ejercicio"], disabled=True)
        st.info(f"Plan de cuentas: {p['plan_nombre']}. El país no se puede cambiar después.")
        ok = st.form_submit_button("Comenzar", type="primary")
    if ok:
        digitos = re.sub(r"\D", "", idf)
        if not nombre.strip():
            st.error("Escribe el nombre de la empresa.")
        elif p["id_fiscal_largo"] and len(digitos) != p["id_fiscal_largo"]:
            st.error(f"El {p['id_fiscal']} debe tener {p['id_fiscal_largo']} dígitos.")
        else:
            db.guardar_empresa(owner, dict(nombre=nombre.strip(), pais=p["codigo"], id_fiscal=digitos or idf.strip(),
                                           regimen=regimen, moneda=p["moneda"], actividad=actividad,
                                           pct_renta=p["regimenes"][regimen]))
            st.rerun()


# ------------------------------------------------------------------ utilidades de vistas
def tabla(df, **kw):
    cfg = {c: st.column_config.NumberColumn(c, format="%.2f") for c in df.columns if df[c].dtype.kind == "f"}
    st.dataframe(df, hide_index=True, width="stretch", column_config=cfg, **kw)


def estado(filas):
    """Estado financiero completo, sin scroll interno. Los títulos de sección no llevan importe."""
    df = pd.DataFrame([(c, "" if v is None else money(v)) for c, v in filas], columns=["Concepto", "Importe"])
    st.table(df.set_index("Concepto"))


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


def df_diario(docs):
    filas, n = [], 0
    for d in docs:
        if d["estado"] != "registrado":
            continue
        n += 1
        for l in d["asiento"]:
            filas.append({"N°": n, "Fecha": d["fecha"], "Cuenta": l["cuenta"], "Denominación": l["nombre"],
                          "Debe": l["debe"], "Haber": l["haber"], "Glosa": d["glosa"]})
    return pd.DataFrame(filas)


def selector_periodo(docs, key):
    meses = sorted({d["fecha"][:7] for d in docs if d["estado"] == "registrado"})
    return st.selectbox("Periodo", ["Todo"] + meses, key=key)


# ------------------------------------------------------------------ páginas
def pg_dashboard(owner, emp, p, docs):
    st.header("Dashboard")
    if not any(d["estado"] == "registrado" for d in docs):
        st.info("Aún no hay documentos registrados. Ve a **Subir documentos** para cargar tu primera factura.")
        return
    per = selector_periodo(docs, "per_dash")
    df_all = cont.lineas(docs)
    df = cont.filtrar(df_all, per)
    docs_p = [d for d in docs if per == "Todo" or d["fecha"][:7] == per]
    g = p["grupos"]
    er, A, P, imp = cont.kpis(docs_p, df, g, p)
    _, _, _, ta, tp, tpt = cont.situacion_financiera(df_all, g, per)
    s = p["simbolo"]
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
    n = st.session_state.setdefault("up_n", 0)
    archivos = st.file_uploader("Arrastra tus documentos aquí", type=["pdf", "png", "jpg", "jpeg", "webp"],
                                accept_multiple_files=True, key=f"up_{n}")
    if archivos and st.button(f"Procesar {len(archivos)} documento(s) con Claude", type="primary"):
        barra, errores = st.progress(0.0), []
        for i, f in enumerate(archivos):
            with st.spinner(f"Claude está leyendo {f.name}…"):
                try:
                    datos = f.getvalue()
                    doc = ia.extraer(f.name, f.type or "", datos, emp, p)
                    db.crear_documento(owner, doc, f.name, f.type or "", datos)
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


def revisar(owner, emp, p, d):
    plan = dict(p["plan"])
    ok_cuadre, td, th = ia.validar_asiento(d["asiento"])
    etiqueta = f"{d['archivo_nombre']} — {d['tipo']} · {d['tipo_comprobante']} {d['serie']}-{d['numero']} · {money(d['total'], p['simbolo'])}"
    with st.expander(("✅ " if ok_cuadre and not d["alertas"] else "⚠️ ") + etiqueta, expanded=True):
        for a in d["alertas"]:
            st.warning(a)
        c1, c2, c3 = st.columns([1, 1, 2])
        fecha = c1.text_input("Fecha (AAAA-MM-DD)", d["fecha"], key=f"f_{d['id']}")
        tipos = ["compra", "venta", "planilla", "honorarios", "otro"]
        tipo = c2.selectbox("Tipo", tipos, index=tipos.index(d["tipo"]) if d["tipo"] in tipos else 4, key=f"t_{d['id']}")
        glosa = c3.text_input("Glosa", d["glosa"], key=f"g_{d['id']}")
        st.caption(f"{d['contraparte_nombre']} ({d['contraparte_id']}) · Base {money(d['base'])} · "
                   f"{p['impuesto']} {money(d['impuesto'])} · Total {money(d['total'])}")
        base = pd.DataFrame(d["asiento"] or [{"cuenta": "", "nombre": "", "debe": 0.0, "haber": 0.0}])[["cuenta", "nombre", "debe", "haber"]]
        ed = st.data_editor(base, num_rows="dynamic", width="stretch", hide_index=True, key=f"ed_{d['id']}",
                            column_config={"cuenta": st.column_config.SelectboxColumn("Cuenta", options=list(plan), required=True),
                                           "nombre": st.column_config.TextColumn("Denominación", disabled=True),
                                           "debe": st.column_config.NumberColumn("Debe", format="%.2f", default=0.0),
                                           "haber": st.column_config.NumberColumn("Haber", format="%.2f", default=0.0)})
        lineas = [{"cuenta": str(r["cuenta"]), "nombre": plan.get(str(r["cuenta"]), ""), "debe": float(r["debe"] or 0),
                   "haber": float(r["haber"] or 0)} for _, r in ed.iterrows() if str(r["cuenta"]).strip()]
        cuadra, td, th = ia.validar_asiento(lineas)
        (st.success if cuadra else st.error)(f"Debe {money(td)}  |  Haber {money(th)}" + ("" if cuadra else "  — el asiento no cuadra"))
        b1, b2, b3, b4 = st.columns(4)
        fecha_ok = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha))
        if b1.button("✔ Registrar", key=f"r_{d['id']}", type="primary", disabled=not (cuadra and fecha_ok)):
            if db.duplicado(owner, {**d, "tipo": tipo}) and not st.session_state.get(f"dup_{d['id']}"):
                st.session_state[f"dup_{d['id']}"] = True
                st.warning("Este comprobante ya está registrado. Pulsa Registrar otra vez si quieres duplicarlo.")
            else:
                db.actualizar_documento(owner, d["id"], estado="registrado", fecha=fecha, tipo=tipo, glosa=glosa, asiento=lineas)
                st.rerun()
        if b2.button("Guardar cambios", key=f"s_{d['id']}"):
            db.actualizar_documento(owner, d["id"], fecha=fecha, tipo=tipo, glosa=glosa, asiento=lineas)
            st.toast("Cambios guardados")
        if b3.button("Descartar", key=f"x_{d['id']}"):
            db.eliminar_documento(owner, d["id"])
            st.rerun()
        arch = db.obtener_archivo(owner, d["id"])
        if arch:
            b4.download_button("Ver original", arch[1], file_name=d["archivo_nombre"], mime=arch[0] or None, key=f"v_{d['id']}")


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
    f = []
    for d in docs:
        if d["estado"] == "registrado" and d["tipo"] in ("planilla", "honorarios"):
            s = lambda pre, k: sum(l[k] for l in d["asiento"] if str(l["cuenta"]).startswith(pre))  # noqa: E731
            f.append({"Fecha": d["fecha"], "Tipo": d["tipo"], "Detalle": d["glosa"], "Gasto de personal/servicio": s("62", "debe") + s("6321", "debe"),
                      "EsSalud": s("4031", "haber"), "ONP/AFP": s("4032", "haber") + s("407", "haber"),
                      "Retención 4ta": s("40172", "haber"), "Neto a pagar": s("4111", "haber") + s("4212", "haber")})
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
    c1, c2 = st.columns(2)
    e = cont.estado_resultados(df, g)
    filas = [("Ventas", e["ventas"]), ("(−) Descuentos y devoluciones", -e["descuentos"]), ("VENTAS NETAS", e["ventas_netas"]),
             ("(−) Costo de ventas / compras", -e["costo"]), ("UTILIDAD BRUTA", e["utilidad_bruta"]),
             ("(−) Gastos de personal", -e["personal"]), ("(−) Servicios de terceros", -e["servicios"]),
             ("(−) Tributos", -e["tributos"]), ("(−) Otros gastos de gestión", -e["otros_gastos"]),
             ("(−) Depreciación", -e["depreciacion"]), ("UTILIDAD OPERATIVA", e["utilidad_operativa"]),
             ("(+) Otros ingresos", e["otros_ingresos"]), ("(−) Gastos financieros", -e["financieros"]),
             ("RESULTADO ANTES DE IMPUESTOS", e["antes_impuestos"])]
    c1.subheader("Estado de Resultados")
    with c1:
        estado(filas)
    A, P, Pt, ta, tp, tpt = cont.situacion_financiera(df_all, g, per)
    f2 = [("ACTIVO", None)] + list(A.items()) + [("TOTAL ACTIVO", ta), ("PASIVO", None)] + list(P.items()) + [("Total pasivo", tp),
          ("PATRIMONIO", None)] + list(Pt.items()) + [("Total patrimonio", tpt), ("TOTAL PASIVO + PATRIMONIO", tp + tpt)]
    c2.subheader("Estado de Situación Financiera")
    with c2:
        estado(f2)
        if abs(ta - tp - tpt) > 0.05:
            st.error("El balance no cuadra: revisa los asientos (puede faltar el aporte de capital o saldos iniciales).")
        else:
            st.success("Balance cuadrado")
    st.subheader("Balance de Comprobación")
    tabla(cont.balance_comprobacion(df))


def pg_documentos(owner, emp, p, docs):
    st.header("Documentos registrados")
    reg = [d for d in docs if d["estado"] == "registrado"][::-1]
    if not reg:
        return st.info("Sin documentos.")
    for d in reg:
        c = st.columns([1.2, 1, 2, 3, 1.2, 1, 1])
        c[0].write(d["fecha"]); c[1].write(d["tipo"]); c[2].write(f"{d['serie']}-{d['numero']}")
        c[3].write(d["contraparte_nombre"]); c[4].write(money(d["total"], p["simbolo"]))
        arch = db.obtener_archivo(owner, d["id"])
        if arch:
            c[5].download_button("⬇", arch[1], file_name=d["archivo_nombre"], mime=arch[0] or None, key=f"dl_{d['id']}")
        if c[6].button("🗑", key=f"del_{d['id']}", help="Eliminar documento y asiento"):
            db.eliminar_documento(owner, d["id"]); st.rerun()


def pg_config(owner, emp, p, docs):
    st.header("Configuración")
    with st.form("cfg"):
        nombre = st.text_input("Razón social", emp["nombre"])
        idf = st.text_input(p["id_fiscal"], emp["id_fiscal"])
        regs = list(p["regimenes"])
        regimen = st.selectbox("Régimen tributario", regs, index=regs.index(emp["regimen"]) if emp["regimen"] in regs else 0)
        pct = st.number_input("% de pago a cuenta de renta", value=float(emp["pct_renta"] or 0), step=0.1)
        act = st.selectbox("Actividad", p["actividades"], index=p["actividades"].index(emp["actividad"]) if emp["actividad"] in p["actividades"] else 0)
        st.caption(f"País: {p['nombre']} (fijo) · Moneda: {p['moneda']}")
        if st.form_submit_button("Guardar", type="primary"):
            db.guardar_empresa(owner, dict(nombre=nombre.strip(), id_fiscal=idf.strip(), regimen=regimen, pct_renta=pct, actividad=act))
            st.success("Guardado"); st.rerun()
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
    with st.expander("Zona de peligro"):
        if st.checkbox("Entiendo que se borrarán todos mis documentos y asientos") and st.button("Borrar todo"):
            db.borrar_todo(owner); st.rerun()


# ------------------------------------------------------------------ main
owner = identificar()
emp = db.get_empresa(owner)
if not emp:
    bienvenida(owner)
    st.stop()

p = paises.get_pais(emp["pais"])
docs = db.listar(owner)
pend = sum(1 for d in docs if d["estado"] == "pendiente")

with st.sidebar:
    st.markdown(f"### 📒 ContaIA\n**{emp['nombre']}**  \n{p['id_fiscal']} {emp['id_fiscal']} · {p['nombre']}")
    paginas = {"dash": ("📊 Dashboard", pg_dashboard),
               "subir": ("⬆️ Subir documentos", pg_subir),
               "diario": ("📘 Libro Diario", pg_diario),
               "compras": ("🧾 Registro de Compras", lambda o, e, pp, d: pg_registro("Registro de Compras", "compra", d)),
               "ventas": ("💰 Registro de Ventas", lambda o, e, pp, d: pg_registro("Registro de Ventas", "venta", d)),
               "planillas": ("👥 Planillas", pg_planillas),
               "impuestos": (f"🏛️ {p['impuesto']} y tributos", pg_impuestos),
               "eeff": ("📑 Estados financieros", pg_eeff),
               "docs": ("🗂️ Documentos", pg_documentos),
               "config": ("⚙️ Configuración", pg_config)}

    sel = st.radio("Menú", list(paginas), format_func=lambda k: paginas[k][0], label_visibility="collapsed", key="menu")
    if pend:
        st.warning(f"Tienes {pend} documento(s) por revisar en «Subir documentos».")
    st.caption("Tus datos están ligados a este navegador. No borres las cookies ni uses modo incógnito; "
               "en Configuración tienes un enlace de recuperación y un respaldo.")

paginas[sel][1](owner, emp, p, docs)
