# app/db/database.py
import sqlite3
from pathlib import Path
from ..config import DB_PATH, DATA_DIR

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    # Tipos de IVA por defecto si no existen
    cur = conn.execute("SELECT COUNT(*) AS c FROM tipos_iva")
    if cur.fetchone()["c"] == 0:
        for pct, desc, orden in [(21, "IVA general", 1), (10, "IVA reducido", 2),
                                 (4, "IVA superreducido", 3), (0, "Exento", 4)]:
            conn.execute(
                "INSERT INTO tipos_iva (porcentaje, descripcion, activo, orden) VALUES (?,?,1,?)",
                (pct, desc, orden),
            )
    # Fila empresa placeholder (se rellena en Pestaña A)
    cur = conn.execute("SELECT COUNT(*) AS c FROM empresa")
    if cur.fetchone()["c"] == 0:
        conn.execute(
            "INSERT INTO empresa (id, nombre, nif, direccion, cp, ciudad, comunidad_autonoma, pais) "
            "VALUES (1, '', '', '', '', '', '', 'España')"
        )
    # Migración: columnas Verifactu (si no existen)
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(empresa)").fetchall()]
    if "verifactu_mode" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN verifactu_mode TEXT DEFAULT 'prueba'")
    if "verifactu_cert_path" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN verifactu_cert_path TEXT")
    if "verifactu_key_path" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN verifactu_key_path TEXT")
    if "verifactu_cert_password" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN verifactu_cert_password TEXT")
    if "verifactu_enabled" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN verifactu_enabled INTEGER DEFAULT 0")
    if "registro_mercantil" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN registro_mercantil TEXT")
    if "notas" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN notas TEXT")
    if "recargo_equivalencia_enabled" not in cols:
        conn.execute("ALTER TABLE empresa ADD COLUMN recargo_equivalencia_enabled INTEGER DEFAULT 0")
    # Migración clientes: teléfono, móvil, email, notas
    ccols = [r["name"] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()]
    if "telefono" not in ccols:
        conn.execute("ALTER TABLE clientes ADD COLUMN telefono TEXT")
    if "telefono_movil" not in ccols:
        conn.execute("ALTER TABLE clientes ADD COLUMN telefono_movil TEXT")
    if "email" not in ccols:
        conn.execute("ALTER TABLE clientes ADD COLUMN email TEXT")
    if "notas" not in ccols:
        conn.execute("ALTER TABLE clientes ADD COLUMN notas TEXT")
    if "recargo_equivalencia" not in ccols:
        conn.execute("ALTER TABLE clientes ADD COLUMN recargo_equivalencia INTEGER DEFAULT 0")
    # Migración tipos_iva: recargo de equivalencia
    tcols = [r["name"] for r in conn.execute("PRAGMA table_info(tipos_iva)").fetchall()]
    if "recargo_porcentaje" not in tcols:
        conn.execute("ALTER TABLE tipos_iva ADD COLUMN recargo_porcentaje REAL DEFAULT 0")

    # Migración facturas: retención IRPF
    fcols = [r["name"] for r in conn.execute("PRAGMA table_info(facturas)").fetchall()]
    if "irpf_porcentaje" not in fcols:
        conn.execute("ALTER TABLE facturas ADD COLUMN irpf_porcentaje REAL DEFAULT 0")
    if "irpf_importe" not in fcols:
        conn.execute("ALTER TABLE facturas ADD COLUMN irpf_importe REAL DEFAULT 0")
    if "total_a_pagar" not in fcols:
        conn.execute("ALTER TABLE facturas ADD COLUMN total_a_pagar REAL")
    if "recargo_importe" not in fcols:
        conn.execute("ALTER TABLE facturas ADD COLUMN recargo_importe REAL DEFAULT 0")
    # Migración lineas_factura: recargo de equivalencia
    lcols = [r["name"] for r in conn.execute("PRAGMA table_info(lineas_factura)").fetchall()]
    if "porcentaje_recargo" not in lcols:
        conn.execute("ALTER TABLE lineas_factura ADD COLUMN porcentaje_recargo REAL DEFAULT 0")
    if "recargo_linea" not in lcols:
        conn.execute("ALTER TABLE lineas_factura ADD COLUMN recargo_linea REAL DEFAULT 0")

    conn.commit()
    conn.close()

def rows_to_list(rows):
    return [dict(r) for r in rows]
