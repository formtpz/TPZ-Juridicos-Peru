"""Persistencia de asignaciones en SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2] / "Repositorio_de_Asignaciones"
DB_FILE = REPO_DIR / "asignaciones.sqlite3"

ESTADOS = ["Sin asignar", "En proceso", "Finalizada", "En conflicto"]
ESTADOS_CIERRE = ["Finalizada", "En conflicto"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS manzanas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                poligono TEXT NOT NULL,
                manzana TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Sin asignar',
                operador_activo TEXT,
                supervisor_activo TEXT,
                fecha_asignacion_activa TEXT,
                fecha_cierre_activa TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(poligono, manzana)
            );

            CREATE TABLE IF NOT EXISTS lotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manzana_id INTEGER NOT NULL,
                lote TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(manzana_id, lote),
                FOREIGN KEY(manzana_id) REFERENCES manzanas(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS historial_asignaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manzana_id INTEGER NOT NULL,
                poligono TEXT NOT NULL,
                manzana TEXT NOT NULL,
                operador TEXT NOT NULL,
                supervisor TEXT,
                estado_inicio TEXT NOT NULL,
                estado_fin TEXT,
                fecha_asignacion TEXT NOT NULL,
                fecha_cierre TEXT,
                detalle TEXT,
                FOREIGN KEY(manzana_id) REFERENCES manzanas(id) ON DELETE CASCADE
            );
            """
        )


def _normalize_columns(df):
    col_map = {str(c).strip().lower(): c for c in df.columns}
    required = {"poligono", "manzana", "lote"}
    missing = required.difference(col_map.keys())
    if missing:
        faltan = ", ".join(sorted(missing))
        raise ValueError(f"Faltan columnas requeridas en Excel: {faltan}.")
    return col_map["poligono"], col_map["manzana"], col_map["lote"]


def registrar_desde_dataframe(df) -> dict:
    """
    Registra/actualiza datos desde DataFrame con columnas Poligono/Manzana/Lote.
    Retorna resumen de inserciones.
    """
    init_db()
    col_poligono, col_manzana, col_lote = _normalize_columns(df)

    manzanas_set = set()
    lotes_set = set()
    for _, row in df.iterrows():
        poligono = str(row[col_poligono]).strip() if row[col_poligono] is not None else ""
        manzana = str(row[col_manzana]).strip() if row[col_manzana] is not None else ""
        lote = str(row[col_lote]).strip() if row[col_lote] is not None else ""
        if not poligono or not manzana or not lote:
            continue
        manzanas_set.add((poligono, manzana))
        lotes_set.add((poligono, manzana, lote))

    manzanas_insertadas = 0
    lotes_insertados = 0
    now = _now_iso()

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE;")
        try:
            for poligono, manzana in sorted(manzanas_set):
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO manzanas (
                        poligono, manzana, estado, created_at, updated_at
                    ) VALUES (?, ?, 'Sin asignar', ?, ?)
                    """,
                    (poligono, manzana, now, now),
                )
                if cur.rowcount:
                    manzanas_insertadas += 1
                conn.execute(
                    "UPDATE manzanas SET updated_at = ? WHERE poligono = ? AND manzana = ?",
                    (now, poligono, manzana),
                )

            for poligono, manzana, lote in sorted(lotes_set):
                row = conn.execute(
                    "SELECT id FROM manzanas WHERE poligono = ? AND manzana = ?",
                    (poligono, manzana),
                ).fetchone()
                if not row:
                    continue
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO lotes (manzana_id, lote, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (row["id"], lote, now),
                )
                if cur.rowcount:
                    lotes_insertados += 1

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {
        "manzanas_detectadas": len(manzanas_set),
        "lotes_detectados": len(lotes_set),
        "manzanas_insertadas": manzanas_insertadas,
        "lotes_insertados": lotes_insertados,
    }


def get_all() -> list[dict]:
    """Retorna estado actual de manzanas para vistas operativa y supervisor."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                m.id,
                m.poligono,
                m.manzana,
                m.estado,
                m.operador_activo,
                m.supervisor_activo,
                m.fecha_asignacion_activa,
                m.fecha_cierre_activa,
                m.created_at,
                m.updated_at,
                COUNT(l.id) AS total_lotes
            FROM manzanas m
            LEFT JOIN lotes l ON l.manzana_id = m.id
            GROUP BY m.id
            ORDER BY m.poligono, m.manzana
            """
        ).fetchall()
    return [dict(r) for r in rows]


def listar_poligonos() -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT poligono FROM manzanas ORDER BY poligono"
        ).fetchall()
    return [r["poligono"] for r in rows]


def operador_tiene_activa(operador: str) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM manzanas
            WHERE operador_activo = ? AND estado = 'En proceso'
            LIMIT 1
            """,
            (operador,),
        ).fetchone()
    return row is not None


def asignar_manzana(poligono: str, manzana: str, operador: str, supervisor: str) -> tuple[bool, str]:
    """Asigna manzana en transacción y registra historial."""
    init_db()
    now = _now_iso()

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE;")
        try:
            activa = conn.execute(
                """
                SELECT poligono, manzana
                FROM manzanas
                WHERE operador_activo = ? AND estado = 'En proceso'
                LIMIT 1
                """,
                (operador,),
            ).fetchone()
            if activa:
                conn.rollback()
                return (
                    False,
                    f"El operador '{operador}' ya tiene activa la manzana "
                    f"'{activa['poligono']}-{activa['manzana']}'.",
                )

            row = conn.execute(
                "SELECT * FROM manzanas WHERE poligono = ? AND manzana = ?",
                (poligono, manzana),
            ).fetchone()
            if not row:
                conn.rollback()
                return False, "Manzana no encontrada."
            if row["estado"] != "Sin asignar":
                conn.rollback()
                return False, f"La manzana está en estado '{row['estado']}' y no se puede asignar."

            conn.execute(
                """
                UPDATE manzanas
                SET estado = 'En proceso',
                    operador_activo = ?,
                    supervisor_activo = ?,
                    fecha_asignacion_activa = ?,
                    fecha_cierre_activa = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (operador, supervisor, now, now, row["id"]),
            )
            conn.execute(
                """
                INSERT INTO historial_asignaciones (
                    manzana_id, poligono, manzana, operador, supervisor,
                    estado_inicio, estado_fin, fecha_asignacion, fecha_cierre, detalle
                ) VALUES (?, ?, ?, ?, ?, 'En proceso', NULL, ?, NULL, ?)
                """,
                (
                    row["id"],
                    row["poligono"],
                    row["manzana"],
                    operador,
                    supervisor,
                    now,
                    "Asignación operativa de manzana.",
                ),
            )
            conn.commit()
            return True, f"Manzana '{poligono}-{manzana}' asignada a {operador}."
        except Exception:
            conn.rollback()
            raise


def cerrar_manzana(poligono: str, manzana: str, operador: str, estado_final: str) -> tuple[bool, str]:
    """Cierra manzana en Finalizada o En conflicto, validando operador activo."""
    init_db()
    if estado_final not in ESTADOS_CIERRE:
        return False, "Estado de cierre inválido. Usa Finalizada o En conflicto."

    now = _now_iso()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE;")
        try:
            row = conn.execute(
                "SELECT * FROM manzanas WHERE poligono = ? AND manzana = ?",
                (poligono, manzana),
            ).fetchone()
            if not row:
                conn.rollback()
                return False, "Manzana no encontrada."
            if row["estado"] != "En proceso":
                conn.rollback()
                return False, f"La manzana está en estado '{row['estado']}'."
            if (row["operador_activo"] or "").strip() != operador.strip():
                conn.rollback()
                return False, "Solo el operador asignado puede cerrar la manzana."

            conn.execute(
                """
                UPDATE manzanas
                SET estado = ?,
                    fecha_cierre_activa = ?,
                    operador_activo = NULL,
                    supervisor_activo = NULL,
                    fecha_asignacion_activa = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (estado_final, now, now, row["id"]),
            )
            conn.execute(
                """
                UPDATE historial_asignaciones
                SET estado_fin = ?, fecha_cierre = ?, detalle = ?
                WHERE id = (
                    SELECT id
                    FROM historial_asignaciones
                    WHERE manzana_id = ?
                      AND operador = ?
                      AND fecha_cierre IS NULL
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,
                (
                    estado_final,
                    now,
                    f"Cierre de manzana en estado '{estado_final}'.",
                    row["id"],
                    operador,
                ),
            )
            conn.commit()
            return True, f"Manzana '{poligono}-{manzana}' cerrada en estado '{estado_final}'."
        except Exception:
            conn.rollback()
            raise
