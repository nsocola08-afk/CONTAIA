"""
Base de datos. En Railway usa PostgreSQL (variable DATABASE_URL).
En tu computadora, si no existe DATABASE_URL, usa un archivo SQLite local.
Cada fila lleva owner_id: así cada persona solo ve lo suyo.
"""
import json
import os
from datetime import datetime

from sqlalchemy import (Column, DateTime, Float, Integer, LargeBinary, MetaData, String, Table, Text,
                        create_engine, delete, insert, select, update)


def _url():
    u = os.environ.get("DATABASE_URL", "").strip()
    if not u:
        return "sqlite:///contaia.db"
    # Railway entrega "postgres://" o "postgresql://". Se fuerza el conector psycopg2 (el instalado),
    # porque las versiones nuevas de SQLAlchemy usan otro por defecto.
    for prefijo in ("postgres://", "postgresql://"):
        if u.startswith(prefijo):
            u = "postgresql+psycopg2://" + u[len(prefijo):]
            break
    return u


_engine = None
meta = MetaData()

empresas = Table(
    "empresas", meta,
    Column("owner_id", String(64), primary_key=True),
    Column("nombre", String(200)), Column("pais", String(4)), Column("id_fiscal", String(30)),
    Column("regimen", String(100)), Column("moneda", String(8)), Column("actividad", String(60)),
    Column("pct_renta", Float, default=0), Column("creado", DateTime, default=datetime.utcnow),
    Column("notas_ia", Text),                           # instrucciones permanentes para la IA
    Column("modo", String(10)),                         # lector | simple
    Column("tasa_renta", Float),                        # tasa anual del impuesto a la renta (%), para estimar el resultado neto
)

documentos = Table(
    "documentos", meta,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("owner_id", String(64), index=True),
    Column("estado", String(12), index=True),          # pendiente | registrado
    Column("tipo", String(20)),                         # compra | venta | planilla | honorarios | otro
    Column("tipo_comprobante", String(60)), Column("serie", String(30)), Column("numero", String(40)),
    Column("fecha", String(10)),                        # AAAA-MM-DD
    Column("contraparte_id", String(30)), Column("contraparte_nombre", String(250)),
    Column("moneda", String(8)), Column("tipo_cambio", Float),
    Column("base", Float, default=0), Column("impuesto", Float, default=0),
    Column("no_gravado", Float, default=0), Column("total", Float, default=0),
    Column("glosa", Text), Column("alertas", Text),     # alertas: lista JSON
    Column("asiento", Text),                            # lista JSON de líneas
    Column("archivo_nombre", String(250)),
    Column("creado", DateTime, default=datetime.utcnow),
)

archivos = Table(
    "archivos", meta,
    Column("doc_id", Integer, primary_key=True),
    Column("owner_id", String(64), index=True),
    Column("mime", String(80)), Column("contenido", LargeBinary),
)


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_url(), pool_pre_ping=True, future=True)
        meta.create_all(_engine)
        # Migración: bases creadas antes de agregar la columna notas_ia (no pierde datos)
        from sqlalchemy import inspect, text
        existentes = {c["name"] for c in inspect(_engine).get_columns("empresas")}
        for nombre_col, tipo_col in (("notas_ia", "TEXT"), ("modo", "VARCHAR(10)"), ("tasa_renta", "FLOAT")):
            if nombre_col not in existentes:
                with _engine.begin() as c:
                    c.execute(text(f"ALTER TABLE empresas ADD COLUMN {nombre_col} {tipo_col}"))
    return _engine


# ---------- empresa ----------
def get_empresa(owner):
    with engine().connect() as c:
        r = c.execute(select(empresas).where(empresas.c.owner_id == owner)).mappings().first()
    return dict(r) if r else None


def existe_owner(owner):
    return get_empresa(owner) is not None


def guardar_empresa(owner, datos):
    with engine().begin() as c:
        if c.execute(select(empresas.c.owner_id).where(empresas.c.owner_id == owner)).first():
            datos = {k: v for k, v in datos.items() if k != "pais"}  # el país no se cambia
            c.execute(update(empresas).where(empresas.c.owner_id == owner).values(**datos))
        else:
            c.execute(insert(empresas).values(owner_id=owner, **datos))


# ---------- documentos ----------
def _fila(r):
    d = dict(r)
    d["asiento"] = json.loads(d["asiento"] or "[]")
    d["alertas"] = json.loads(d["alertas"] or "[]")
    return d


def crear_documento(owner, doc, archivo_nombre, mime, contenido, estado="pendiente"):
    valores = dict(
        owner_id=owner, estado=estado, tipo=doc["tipo"], tipo_comprobante=doc["tipo_comprobante"],
        serie=doc["serie"], numero=doc["numero"], fecha=doc["fecha"],
        contraparte_id=doc["contraparte_id"], contraparte_nombre=doc["contraparte_nombre"],
        moneda=doc["moneda"], tipo_cambio=doc["tipo_cambio"], base=doc["base"], impuesto=doc["impuesto"],
        no_gravado=doc["no_gravado"], total=doc["total"], glosa=doc["glosa"],
        alertas=json.dumps(doc["alertas"], ensure_ascii=False),
        asiento=json.dumps(doc["asiento"], ensure_ascii=False), archivo_nombre=archivo_nombre,
    )
    with engine().begin() as c:
        doc_id = c.execute(insert(documentos).values(**valores)).inserted_primary_key[0]
        if contenido:
            c.execute(insert(archivos).values(doc_id=doc_id, owner_id=owner, mime=mime, contenido=contenido))
    return doc_id


def listar(owner, estado=None):
    q = select(documentos).where(documentos.c.owner_id == owner)
    if estado:
        q = q.where(documentos.c.estado == estado)
    q = q.order_by(documentos.c.fecha, documentos.c.id)
    with engine().connect() as c:
        return [_fila(r) for r in c.execute(q).mappings()]


def actualizar_documento(owner, doc_id, **campos):
    if "asiento" in campos:
        campos["asiento"] = json.dumps(campos["asiento"], ensure_ascii=False)
    if "alertas" in campos:
        campos["alertas"] = json.dumps(campos["alertas"], ensure_ascii=False)
    with engine().begin() as c:
        c.execute(update(documentos).where(documentos.c.id == doc_id, documentos.c.owner_id == owner).values(**campos))


def eliminar_documento(owner, doc_id):
    with engine().begin() as c:
        c.execute(delete(archivos).where(archivos.c.doc_id == doc_id, archivos.c.owner_id == owner))
        c.execute(delete(documentos).where(documentos.c.id == doc_id, documentos.c.owner_id == owner))


def obtener_archivo(owner, doc_id):
    with engine().connect() as c:
        r = c.execute(select(archivos).where(archivos.c.doc_id == doc_id, archivos.c.owner_id == owner)).mappings().first()
    return (r["mime"], r["contenido"]) if r else None


def duplicado(owner, doc):
    q = select(documentos.c.id).where(
        documentos.c.owner_id == owner, documentos.c.estado == "registrado",
        documentos.c.contraparte_id == doc["contraparte_id"], documentos.c.serie == doc["serie"],
        documentos.c.numero == doc["numero"], documentos.c.tipo == doc["tipo"])
    with engine().connect() as c:
        return c.execute(q).first() is not None


def estadisticas_archivos(owner):
    """(cantidad, MB) de archivos originales guardados por versiones anteriores."""
    from sqlalchemy import func
    with engine().connect() as c:
        n, total = c.execute(select(func.count(archivos.c.doc_id), func.coalesce(func.sum(func.length(archivos.c.contenido)), 0))
                             .where(archivos.c.owner_id == owner)).one()
    return int(n), float(total) / 1048576


def borrar_archivos(owner):
    """Borra solo los archivos originales; los documentos y asientos se conservan."""
    with engine().begin() as c:
        c.execute(delete(archivos).where(archivos.c.owner_id == owner))


def borrar_empresa(owner):
    """Empezar de nuevo: borra documentos, archivos y los datos de la empresa de esta persona."""
    with engine().begin() as c:
        c.execute(delete(archivos).where(archivos.c.owner_id == owner))
        c.execute(delete(documentos).where(documentos.c.owner_id == owner))
        c.execute(delete(empresas).where(empresas.c.owner_id == owner))


def borrar_todo(owner):
    with engine().begin() as c:
        c.execute(delete(archivos).where(archivos.c.owner_id == owner))
        c.execute(delete(documentos).where(documentos.c.owner_id == owner))
