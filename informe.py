"""
Resumen financiero: informe de varias hojas A4 (portada, situación financiera, resultados, indicadores, análisis de
cuentas y conclusiones). El mismo contenido se muestra en pantalla (HTML) y se descarga como PDF.
Todo se calcula con los asientos registrados; los comentarios y conclusiones son reglas automáticas, no opiniones de la IA.
"""
import io
from datetime import date
from html import escape

import analisis as an
import contabilidad as cont

AZUL, CELESTE, CELESTE2 = "#1f3a5f", "#e2ecf7", "#eff5fb"
TXT_ESTADO = {"t": CELESTE, "s": CELESTE2}


def _m(x, s=""):
    x = round(float(x or 0), 2) + 0.0
    return f"{s} {x:,.2f}".strip()


def _pct(x):
    return f"{x * 100:,.1f}%"


# ------------------------------------------------------------------------------------------ contenido
def _tabla(head, rows, estilos=None, alin=None):
    return ("table", {"head": head, "rows": rows, "estilos": estilos or [""] * len(rows),
                      "alin": alin or ["l"] + ["r"] * (len(head) - 1)})


def _estado(titulo, filas, s):
    rows = [[c, "" if v is None else _m(v, s)] for c, v, *_ in filas]
    est = [(f[2] if len(f) > 2 else "") for f in filas]
    return _tabla(["Concepto", "Importe"], rows, est)


def construir(emp, p, docs, per, s):
    """Devuelve {'titulo', 'paginas': [[bloques]]}. `per` es 'Todo' o un mes AAAA-MM."""
    g = p["grupos"]
    df_all = cont.lineas(docs)
    df = cont.filtrar(df_all, per)
    er = cont.estado_resultados(df, g)
    S = an.situacion_clasificada(docs, df_all, g, per)
    ta, tp, tpt = S["ta"], S["tp"], S["tpt"]
    periodo = "Todos los periodos registrados" if per in (None, "Todo") else f"Mes {per}"
    corte = S["corte"]
    reg = [d for d in docs if d["estado"] == "registrado"]
    docs_p = [d for d in reg if per in (None, "Todo") or d["fecha"][:7] == per]
    paginas = []

    # 1. Portada
    paginas.append([
        ("portada", {"empresa": emp["nombre"] or "Empresa", "titulo": "Informe de situación financiera", "periodo": periodo}),
        ("kv", [("País", p["nombre"]), (p["id_fiscal"], emp.get("id_fiscal") or "—"), ("Actividad", emp.get("actividad") or "—"),
                ("Régimen tributario", emp.get("regimen") or "—"), ("Moneda", emp["moneda"]),
                ("Fecha de corte", corte.isoformat()), ("Fecha de emisión", date.today().isoformat()),
                ("Operaciones consideradas", f"{len(docs_p)} en el periodo · {len(reg)} en total")]),
        ("h2", "Contenido"),
        ("bullets", ["Estado de Situación Financiera", "Estado de Resultados", "Indicadores y evolución mensual",
                     "Análisis de cuentas: por cobrar y por pagar", "Otras cuentas principales",
                     "Resumen y conclusiones de la situación de la empresa"]),
        ("nota", "Informe elaborado automáticamente con los asientos registrados en ContaIA. Es una herramienta de apoyo: "
                 "las cifras y conclusiones deben ser revisadas por tu contador antes de usarse en trámites oficiales."),
    ])

    # 2. Situación financiera
    paginas.append([
        ("h1", "Estado de Situación Financiera"), ("sub", f"Al {corte.isoformat()} · expresado en {emp['moneda']}"),
        _estado("", [("ACTIVO", None, "t"), ("ACTIVO CORRIENTE", None, "s")] + S["ac"]
                + [("TOTAL ACTIVO CORRIENTE", S["tac"], "s"), ("ACTIVO NO CORRIENTE", None, "s")] + S["anc"]
                + [("TOTAL ACTIVO NO CORRIENTE", S["tanc"], "s"), ("TOTAL ACTIVO", ta, "s"),
                   ("PASIVO", None, "t"), ("PASIVO CORRIENTE", None, "s")] + S["pc"]
                + [("TOTAL PASIVO CORRIENTE", S["tpc"], "s"), ("PASIVO NO CORRIENTE", None, "s")] + S["pnc"]
                + [("TOTAL PASIVO NO CORRIENTE", S["tpnc"], "s"), ("TOTAL PASIVO", tp, "s"), ("PATRIMONIO", None, "t")] + S["pt"]
                + [("TOTAL PATRIMONIO", tpt, "s"), ("TOTAL PASIVO Y PATRIMONIO", tp + tpt, "s")], s),
        ("nota", "Corriente: vence o se realiza dentro de 12 meses del corte. Las cuentas por cobrar y por pagar sin fecha límite se "
                 "consideran de corto plazo." + ("" if abs(ta - tp - tpt) <= 0.05 else " ATENCIÓN: el balance no cuadra; revisa los asientos.")),
    ])

    # 3. Resultados
    t_renta = float(emp.get("tasa_renta") or 0)
    renta = round(max(0.0, er["antes_impuestos"]) * t_renta / 100, 2)
    filas_er = [("Ventas", er["ventas"]), ("(-) Descuentos y devoluciones", -er["descuentos"]), ("VENTAS NETAS", er["ventas_netas"], "t"),
                ("(-) Costo de ventas / compras", -er["costo"]), ("UTILIDAD BRUTA", er["utilidad_bruta"], "t"),
                ("(-) Gastos de personal", -er["personal"]), ("(-) Servicios de terceros", -er["servicios"]),
                ("(-) Tributos", -er["tributos"]), ("(-) Otros gastos de gestión", -er["otros_gastos"]),
                ("(-) Depreciación", -er["depreciacion"]), ("UTILIDAD OPERATIVA", er["utilidad_operativa"], "t"),
                ("(+) Otros ingresos", er["otros_ingresos"]), ("(-) Gastos financieros", -er["financieros"]),
                ("RESULTADO ANTES DE IMPUESTOS", er["antes_impuestos"], "t")]
    if t_renta > 0:
        filas_er += [(f"(-) Impuesto a la renta estimado ({t_renta:g}%)", -renta),
                     ("RESULTADO NETO ESTIMADO", er["antes_impuestos"] - renta, "t")]
    paginas.append([("h1", "Estado de Resultados"), ("sub", f"{periodo} · expresado en {emp['moneda']}"),
                    _estado("", filas_er, s),
                    ("nota", "El impuesto a la renta es una estimación con la tasa anual configurada; la determinación definitiva "
                             "corresponde a la declaración anual." if t_renta > 0 else
                             "No se estimó impuesto a la renta (no hay tasa configurada).")])

    # 4. Indicadores y evolución
    vn = er["ventas_netas"]
    liq = S["tac"] / S["tpc"] if S["tpc"] > 0 else None
    capital_trab = S["tac"] - S["tpc"]
    endeud = (tp / ta) if ta > 0 else None
    m_bruto, m_oper, m_neto = (er["utilidad_bruta"] / vn, er["utilidad_operativa"] / vn, er["antes_impuestos"] / vn) if vn > 0 else (None,) * 3
    ind = [["Liquidez corriente", f"{liq:,.2f}" if liq is not None else "—", "Activo corriente / pasivo corriente. Sobre 1 indica que alcanza para pagar el corto plazo."],
           ["Capital de trabajo", _m(capital_trab, s), "Activo corriente menos pasivo corriente."],
           ["Endeudamiento", _pct(endeud) if endeud is not None else "—", "Parte de los activos financiada con deudas."],
           ["Margen bruto", _pct(m_bruto) if m_bruto is not None else "—", "Utilidad bruta sobre ventas netas."],
           ["Margen operativo", _pct(m_oper) if m_oper is not None else "—", "Utilidad operativa sobre ventas netas."],
           ["Margen antes de impuestos", _pct(m_neto) if m_neto is not None else "—", "Resultado antes de impuestos sobre ventas netas."]]
    meses = sorted(df_all["mes"].unique())[-12:] if not df_all.empty else []
    v = [-cont.saldo(df_all[df_all["mes"] == m], g["ventas"]) for m in meses]
    k = [cont.saldo(df_all[df_all["mes"] == m], g["costo"] + g["servicios"] + g["personal"] + g["otros_gastos"]) for m in meses]
    bloques = [("h1", "Indicadores y evolución mensual"), ("sub", periodo),
               _tabla(["Indicador", "Valor", "Qué significa"], ind, alin=["l", "r", "l"])]
    if meses:
        bloques += [("h2", "Ventas y gastos por mes"),
                    ("bars", {"labels": meses, "series": [("Ventas", v, "#2f7d5b"), ("Compras y gastos", k, "#c46a5a")]}),
                    _tabla(["Mes", "Ventas", "Compras y gastos", "Diferencia"],
                           [[m, _m(a, s), _m(b, s), _m(a - b, s)] for m, a, b in zip(meses, v, k)])]
    paginas.append(bloques)

    # 5. Cuentas por cobrar y por pagar
    hasta = None if per in (None, "Todo") else corte.isoformat()
    bl = [("h1", "Análisis de cuentas por cobrar y por pagar"), ("sub", f"Al {corte.isoformat()}")]
    info = {}
    for titulo, tokens, signo, tercero, et in (("Cuentas por cobrar", g["cxc"], 1, "Clientes", ("Facturado", "Cobrado", "Saldo")),
                                              ("Cuentas por pagar", g["cxp"], -1, "Proveedores", ("Facturado", "Pagado", "Saldo"))):
        mov = an.movimientos(docs, tokens, hasta=hasta)
        sal = an.saldos_por_tercero(mov, signo, et) if not mov.empty else None
        total = float(sal["Saldo"].sum()) if sal is not None and not sal.empty else 0.0
        bl.append(("h2", f"{titulo}: {_m(total, s)}"))
        top1 = 0.0
        if sal is None or sal.empty:
            bl.append(("p", "No hay saldos pendientes."))
        else:
            top = sal.head(5)
            top1 = float(top["Saldo"].iloc[0]) / total if total > 0 else 0.0
            bl.append(_tabla([f"Principales {tercero.lower()}", "Saldo", "% del total"],
                             [[(r["Nombre"] or "(sin identificar)"), _m(r["Saldo"], s), _pct(r["Saldo"] / total) if total else "—"]
                              for _, r in top.iterrows()]))
            ant = an.antiguedad(mov, signo, corte)
            if not ant.empty:
                tr = [float(ant[c].sum()) for c in an.TRAMOS]
                bl.append(_tabla(["Antigüedad"] + an.TRAMOS, [["Saldo"] + [_m(x, s) for x in tr]]))
                info[titulo] = dict(total=total, tramos=tr, top1=top1, top1_nombre=str(top["Nombre"].iloc[0]))
                continue
        info[titulo] = dict(total=total, tramos=[0.0] * 4, top1=top1, top1_nombre="")
    paginas.append(bl)

    # 6. Otras cuentas
    otras = []
    for nombre, tokens, signo in (("Efectivo (caja y bancos)", g["efectivo"], 1), ("Mercaderías e inventarios", g["inventarios"], 1),
                                  ("Activo fijo (neto)", g["fijo"], 1), ("Remuneraciones por pagar", g["remuneraciones"], -1)):
        mov = an.movimientos(docs, tokens, hasta=hasta)
        ent = float(mov["debe"].sum()) if not mov.empty else 0.0
        sal_ = float(mov["haber"].sum()) if not mov.empty else 0.0
        otras.append([nombre, _m(ent if signo > 0 else sal_, s), _m(sal_ if signo > 0 else ent, s), _m((ent - sal_) * signo, s)])
    deb = sum(d["impuesto"] for d in docs_p if d["tipo"] == "venta")
    cre = sum(d["impuesto"] for d in docs_p if d["tipo"] == "compra")
    imp_n = p["impuesto"]
    paginas.append([("h1", "Otras cuentas principales"), ("sub", "Movimiento acumulado hasta el corte"),
                    _tabla(["Cuenta", "Aumentos", "Disminuciones", "Saldo"], otras),
                    ("h2", f"{imp_n} del periodo"),
                    _tabla(["Concepto", "Importe"], [[f"{imp_n} de ventas (débito)", _m(deb, s)], [f"{imp_n} de compras (crédito)", _m(cre, s)],
                                                     [f"{imp_n} por pagar (+) / a favor (−)", _m(deb - cre, s)]]),
                    ("h2", "Gasto de personal y resultado"),
                    _tabla(["Concepto", "Importe"], [["Gastos de personal", _m(er["personal"], s)], ["Servicios de terceros", _m(er["servicios"], s)],
                                                     ["Utilidad operativa", _m(er["utilidad_operativa"], s)]])])

    # 7. Conclusiones
    c, rec = [], []
    ub = er["antes_impuestos"]
    if vn <= 0 and not er["costo"] and not er["personal"]:
        c.append("No hay ventas ni gastos en el periodo elegido, por lo que no se puede evaluar el desempeño.")
    elif ub >= 0:
        c.append(f"El periodo cierra con utilidad antes de impuestos de {_m(ub, s)}" + (f", un margen de {_pct(m_neto)} sobre las ventas netas." if m_neto is not None else "."))
    else:
        c.append(f"El periodo cierra con pérdida antes de impuestos de {_m(-ub, s)}: los costos y gastos superan a las ventas netas.")
        rec.append("Revisar los gastos más altos y los precios de venta para volver a márgenes positivos.")
    if m_bruto is not None and m_bruto < 0.2:
        rec.append("El margen bruto es bajo (menos de 20%): conviene revisar costos de compra o precios.")
    if liq is not None:
        if liq < 1:
            c.append(f"La liquidez corriente es {liq:,.2f}: el activo corriente no cubre las deudas de corto plazo; hay presión de caja.")
            rec.append("Acelerar cobranzas o negociar plazos con proveedores para cubrir las deudas de corto plazo.")
        elif liq < 1.5:
            c.append(f"La liquidez corriente es {liq:,.2f}: cubre el corto plazo, pero con poco margen.")
        else:
            c.append(f"La liquidez corriente es {liq:,.2f}: la empresa cubre con holgura sus deudas de corto plazo.")
    elif S["tac"] > 0:
        c.append("No hay deudas de corto plazo registradas; todo el activo corriente está libre.")
    if endeud is not None:
        c.append(f"El {_pct(endeud)} de los activos está financiado con deudas" + (" (nivel alto)." if endeud > 0.7 else "."))
        if endeud > 0.7:
            rec.append("El endeudamiento es alto: evitar nuevas deudas hasta mejorar el resultado o aumentar el capital.")
    cx = info.get("Cuentas por cobrar")
    if cx and cx["total"] > 0:
        vencido = sum(cx["tramos"][2:])
        c.append(f"Por cobrar: {_m(cx['total'], s)}; el {_pct(vencido / cx['total'])} tiene más de 60 días de antigüedad.")
        if vencido / cx["total"] > 0.3:
            rec.append("Más de 30% de lo por cobrar tiene más de 60 días: reforzar el seguimiento de cobranza.")
        if cx["top1"] > 0.5 and cx["top1_nombre"]:
            c.append(f"El cliente {cx['top1_nombre']} concentra {_pct(cx['top1'])} de lo por cobrar.")
            rec.append("Reducir la dependencia de un solo cliente.")
    cp = info.get("Cuentas por pagar")
    if cp and cp["total"] > 0:
        c.append(f"Por pagar a proveedores: {_m(cp['total'], s)}; el {_pct(sum(cp['tramos'][2:]) / cp['total'])} tiene más de 60 días.")
        if sum(cp["tramos"][2:]) / cp["total"] > 0.3:
            rec.append("Hay deudas antiguas con proveedores: priorizar su pago para cuidar la relación comercial.")
    if S["pc"][0][1] > 0:
        c.append(f"Hay {imp_n} y otros tributos por pagar por {_m(S['pc'][0][1], s)}; conviene reservar caja para su vencimiento.")
    if S["ac"][0][1] < 0:
        rec.append("El efectivo resulta negativo: faltan registrar ingresos o aportes de capital.")
    if abs(ta - tp - tpt) > 0.05:
        rec.append("El balance no cuadra: revisar asientos, aportes de capital y saldos iniciales antes de usar este informe.")
    if not rec:
        rec.append("Sin alertas relevantes. Mantener el registro al día y revisar este informe cada mes.")
    paginas.append([("h1", "Resumen y conclusiones"), ("sub", f"{emp['nombre']} · {periodo}"),
                    ("h2", "Situación de la empresa"), ("bullets", c), ("h2", "Recomendaciones"), ("bullets", rec),
                    ("nota", "Conclusiones generadas con reglas automáticas a partir de las cifras registradas; no sustituyen el criterio del contador.")])
    return {"titulo": f"Informe financiero - {emp['nombre']}", "paginas": paginas}


# ------------------------------------------------------------------------------------------ HTML (hojas A4 en pantalla)
def _svg_barras(labels, series, ancho=700, alto=230):
    mx = max([abs(x) for _, vals, _ in series for x in vals] + [1])
    n, ns = len(labels), len(series)
    izq, abajo = 8, 28
    paso = (ancho - izq) / n
    w = min(paso * 0.8 / ns, 38)
    base = alto - abajo
    out = [f'<svg viewBox="0 0 {ancho} {alto}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">',
           f'<line x1="{izq}" y1="{base}" x2="{ancho}" y2="{base}" stroke="#9aa5b5" stroke-width="1"/>']
    for i, lab in enumerate(labels):
        for j, (nom, vals, col) in enumerate(series):
            h = max(0.0, vals[i]) / mx * (base - 14)
            x = izq + i * paso + (paso - w * ns) / 2 + j * w
            out.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{col}"/>')
        out.append(f'<text x="{izq + i * paso + paso / 2:.1f}" y="{base + 16}" font-size="13" text-anchor="middle" fill="#445">{escape(lab[2:] if len(lab) == 7 else lab)}</text>')
    lx = izq
    for nom, _, col in series:
        out.append(f'<rect x="{lx}" y="2" width="10" height="10" fill="{col}"/><text x="{lx + 14}" y="11" font-size="12" fill="#445">{escape(nom)}</text>')
        lx += 150
    out.append("</svg>")
    return "".join(out)


def a_html(inf):
    """Hojas A4 apiladas. El tamaño se adapta al ancho disponible (unidades cqw)."""
    css = ("<style>.hoja{width:100%;max-width:794px;aspect-ratio:210/297;margin:0 auto 18px auto;background:#fff;border:1px solid #c9d1dc;"
           "container-type:inline-size;box-sizing:border-box;padding:7cqw;overflow:hidden;color:#1b2430;font-family:Arial,Helvetica,sans-serif;position:relative}"
           ".hoja *{box-sizing:border-box}.hoja h1{font-size:3.1cqw;color:#1f3a5f;margin:0 0 .6cqw 0;padding:0 0 1cqw 0;border-bottom:.35cqw solid #1f3a5f}"
           ".hoja h2{font-size:2.1cqw;color:#1f3a5f;margin:2cqw 0 .8cqw 0}.hoja .sub{font-size:1.6cqw;color:#5b6778;margin:0 0 1.6cqw 0}"
           ".hoja p,.hoja li{font-size:1.65cqw;line-height:1.5;margin:.5cqw 0}.hoja ul{padding-left:3cqw;margin:.5cqw 0}"
           ".hoja table{width:100%;border-collapse:collapse;margin:.8cqw 0}.hoja td,.hoja th{font-size:1.55cqw;padding:.55cqw 1cqw;border-bottom:.1cqw solid #dde3ec;vertical-align:top}"
           ".hoja th{background:#1f3a5f;color:#fff;text-align:left;font-weight:600}.hoja .r{text-align:right;white-space:nowrap}"
           ".hoja .nota{font-size:1.35cqw;color:#5b6778;margin-top:2cqw;border-top:.1cqw solid #dde3ec;padding-top:1cqw}"
           ".hoja .pie{position:absolute;bottom:2.4cqw;left:7cqw;right:7cqw;font-size:1.2cqw;color:#8a94a3;display:flex;justify-content:space-between}"
           ".hoja .kv td{border:none;padding:.5cqw 1cqw .5cqw 0}.hoja .kv td:first-child{color:#5b6778;width:32%}"
           ".hoja .portada{margin:14cqw 0 6cqw 0;padding-left:2.5cqw;border-left:1cqw solid #1f3a5f}"
           ".hoja .portada .e{font-size:5.2cqw;font-weight:700;color:#1f3a5f;line-height:1.15}.hoja .portada .t{font-size:2.8cqw;color:#445;margin-top:1.2cqw}"
           ".hoja .portada .p{font-size:2cqw;color:#5b6778;margin-top:1cqw}</style>")
    total = len(inf["paginas"])
    out = [css]
    for n, bloques in enumerate(inf["paginas"], 1):
        h = ['<div class="hoja">']
        for tipo, dato in bloques:
            if tipo == "portada":
                h.append(f'<div class="portada"><div class="e">{escape(dato["empresa"])}</div><div class="t">{escape(dato["titulo"])}</div>'
                         f'<div class="p">{escape(dato["periodo"])}</div></div>')
            elif tipo == "h1":
                h.append(f"<h1>{escape(dato)}</h1>")
            elif tipo == "h2":
                h.append(f"<h2>{escape(dato)}</h2>")
            elif tipo == "sub":
                h.append(f'<div class="sub">{escape(dato)}</div>')
            elif tipo == "p":
                h.append(f"<p>{escape(dato)}</p>")
            elif tipo == "nota":
                h.append(f'<div class="nota">{escape(dato)}</div>')
            elif tipo == "bullets":
                h.append("<ul>" + "".join(f"<li>{escape(x)}</li>" for x in dato) + "</ul>")
            elif tipo == "kv":
                h.append('<table class="kv">' + "".join(f"<tr><td>{escape(a)}</td><td>{escape(str(b))}</td></tr>" for a, b in dato) + "</table>")
            elif tipo == "bars":
                h.append(_svg_barras(dato["labels"], dato["series"]))
            elif tipo == "table":
                al = dato["alin"]
                t = ["<table><tr>" + "".join(f'<th class="{"r" if a == "r" else ""}">{escape(x)}</th>' for x, a in zip(dato["head"], al)) + "</tr>"]
                for fila, est in zip(dato["rows"], dato["estilos"]):
                    bg = f' style="background:{TXT_ESTADO[est]};font-weight:700;color:#14284a"' if est in TXT_ESTADO else ""
                    t.append(f"<tr{bg}>" + "".join(f'<td class="{"r" if a == "r" else ""}">{escape(str(x))}</td>' for x, a in zip(fila, al)) + "</tr>")
                h.append("".join(t) + "</table>")
        h.append(f'<div class="pie"><span>{escape(inf["titulo"])}</span><span>Hoja {n} de {total}</span></div></div>')
        out.append("".join(h))
    return "".join(out)


# ------------------------------------------------------------------------------------------ PDF
def a_pdf(inf):
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def limpio(t):
        return str(t).replace("−", "-").replace("—", "-").replace("·", "-").replace("→", "->")

    azul = colors.HexColor(AZUL)
    st_h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=azul, spaceAfter=4)
    st_h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=azul, spaceBefore=10, spaceAfter=4)
    st_p = ParagraphStyle("p", fontName="Helvetica", fontSize=9.5, leading=14, spaceAfter=3)
    st_sub = ParagraphStyle("sub", parent=st_p, textColor=colors.HexColor("#5b6778"), spaceAfter=8)
    st_nota = ParagraphStyle("nota", parent=st_p, fontSize=8, textColor=colors.HexColor("#5b6778"), spaceBefore=10)
    st_c = ParagraphStyle("c", fontName="Helvetica", fontSize=8.8, leading=11)
    st_cb = ParagraphStyle("cb", parent=st_c, fontName="Helvetica-Bold", textColor=colors.HexColor("#14284a"))
    st_ch = ParagraphStyle("ch", parent=st_c, fontName="Helvetica-Bold", textColor=colors.white)
    st_r = ParagraphStyle("r", parent=st_c, alignment=2)
    st_rb = ParagraphStyle("rb", parent=st_cb, alignment=2)
    st_rh = ParagraphStyle("rh", parent=st_ch, alignment=2)
    ancho = A4[0] - 40 * mm
    total = len(inf["paginas"])
    el = []
    for n, bloques in enumerate(inf["paginas"]):
        if n:
            el.append(PageBreak())
        for tipo, dato in bloques:
            if tipo == "portada":
                el += [Spacer(1, 50 * mm), Paragraph(limpio(dato["empresa"]), ParagraphStyle("pe", fontName="Helvetica-Bold", fontSize=28, leading=33, textColor=azul)),
                       Spacer(1, 4 * mm), Paragraph(limpio(dato["titulo"]), ParagraphStyle("pt", fontName="Helvetica", fontSize=16, textColor=colors.HexColor("#445"))),
                       Paragraph(limpio(dato["periodo"]), ParagraphStyle("pp", fontName="Helvetica", fontSize=12, textColor=colors.HexColor("#5b6778"), spaceBefore=4)),
                       Spacer(1, 22 * mm)]
            elif tipo == "h1":
                el.append(Paragraph(limpio(dato), st_h1))
            elif tipo == "h2":
                el.append(Paragraph(limpio(dato), st_h2))
            elif tipo == "sub":
                el.append(Paragraph(limpio(dato), st_sub))
            elif tipo == "p":
                el.append(Paragraph(limpio(dato), st_p))
            elif tipo == "nota":
                el.append(Paragraph(limpio(dato), st_nota))
            elif tipo == "bullets":
                for x in dato:
                    el.append(Paragraph("&bull; " + limpio(x).replace("&", "&amp;").replace("<", "&lt;"), st_p))
            elif tipo == "kv":
                t = Table([[Paragraph(limpio(a), st_c), Paragraph(limpio(b), st_cb)] for a, b in dato], colWidths=[ancho * 0.32, ancho * 0.68])
                t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
                el.append(t)
            elif tipo == "bars":
                labels, series = dato["labels"], dato["series"]
                W, H = ancho, 150
                dr = Drawing(W, H)
                mx = max([abs(x) for _, vals, _ in series for x in vals] + [1])
                k, ns = len(labels), len(series)
                paso = (W - 6) / k
                w = min(paso * 0.8 / ns, 38)
                base = 22
                dr.add(Line(4, base, W, base, strokeColor=colors.HexColor("#9aa5b5")))
                for i, lab in enumerate(labels):
                    for j, (nom, vals, col) in enumerate(series):
                        h = max(0.0, vals[i]) / mx * (H - base - 22)
                        dr.add(Rect(4 + i * paso + (paso - w * ns) / 2 + j * w, base, w, h, fillColor=colors.HexColor(col), strokeColor=None))
                    dr.add(String(4 + i * paso + paso / 2, 8, lab[2:] if len(lab) == 7 else lab, fontSize=7, textAnchor="middle"))
                lx = 4
                for nom, _, col in series:
                    dr.add(Rect(lx, H - 10, 8, 8, fillColor=colors.HexColor(col), strokeColor=None))
                    dr.add(String(lx + 12, H - 9, limpio(nom), fontSize=8))
                    lx += 110
                el.append(dr)
            elif tipo == "table":
                al = dato["alin"]
                filas = [[Paragraph(limpio(x), st_rh if a == "r" else st_ch) for x, a in zip(dato["head"], al)]]
                estilo = [("BACKGROUND", (0, 0), (-1, 0), azul), ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dde3ec")),
                          ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2)]
                for i, (fila, est) in enumerate(zip(dato["rows"], dato["estilos"]), 1):
                    en = est in TXT_ESTADO
                    filas.append([Paragraph(limpio(x), (st_rb if en else st_r) if a == "r" else (st_cb if en else st_c)) for x, a in zip(fila, al)])
                    if en:
                        estilo.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(TXT_ESTADO[est])))
                nc = len(dato["head"])
                cw = [ancho * 0.62, ancho * 0.38] if nc == 2 else [ancho * 0.28, ancho * 0.14, ancho * 0.58] if al == ["l", "r", "l"] else [ancho / nc] * nc
                t = Table(filas, colWidths=cw, repeatRows=1)
                t.setStyle(TableStyle(estilo))
                el.append(t)

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#8a94a3"))
        canvas.drawString(20 * mm, 10 * mm, limpio(inf["titulo"]))
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Hoja {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                      title=limpio(inf["titulo"]), author="ContaIA").build(el, onFirstPage=pie, onLaterPages=pie)
    return buf.getvalue()


def a_html_doc(inf):
    """Documento HTML completo para mostrarlo en un marco (iframe) con estilos propios; el marco ajusta su altura."""
    n = len(inf["paginas"])
    js = ("<script>function aj(){try{var h=document.body.scrollHeight+8;"
          "window.frameElement.style.height=h+'px';}catch(e){}}window.addEventListener('load',aj);window.addEventListener('resize',aj);"
          "setTimeout(aj,300);</script>")
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{margin:0;padding:4px 0;background:transparent}</style></head><body>"
            + a_html(inf) + js + "</body></html>")
