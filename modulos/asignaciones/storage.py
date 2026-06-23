"""Persistencia de asignaciones en SQLite."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

REPO_DIR = Path(__file__).resolve().parents[2] / "Repositorio_de_Asignaciones"
DB_FILE = REPO_DIR / "asignaciones.db"

ESTADOS = ["Sin asignar", "En proceso", "Finalizada", "En conflicto"]
ESTADOS_CIERRE = ["Finalizada", "En conflicto"]



def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def _connect() -> sqlite3.Connection:
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn



def init_db() -> None:
    with _connect() as conn:
        conn.execute(
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
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manzana_id INTEGER NOT NULL,
                lote TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(manzana_id, lote),
                FOREIGN KEY(manzana_id) REFERENCES manzanas(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS historial_asignaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manzana_id INTEGER NOT NULL,
                poligono TEXT NOT NULL,
                manzana TEXT NOT NULL,
                operador TEXT,
                supervisor TEXT,
                estado_inicio TEXT,
                estado_fin TEXT,
                fecha_asignacion TEXT,
                fecha_cierre TEXT,
                detalle TEXT,
                FOREIGN KEY(manzana_id) REFERENCES manzanas(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()



def _normalizar_columnas(df: pd.DataFrame) -> dict[str, str]:
    mapping = {str(col).strip().lower(): col for col in df.columns}
    requeridas = ["poligono", "manzana", "lote"]
    faltantes = [col for col in requeridas if col not in mapping]
    if faltantes:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(faltantes)}")
    return mapping



def registrar_desde_dataframe(df: pd.DataFrame) -> tuple[int, int, int]:
    """Registra/actualiza manzanas y lotes desde un DataFrame."""
    init_db()
    cols = _normalizar_columnas(df)

    data = (
        df[[cols["poligono"], cols["manzana"], cols["lote"]]]
        .copy()
        .rename(columns={cols["poligono"]: "poligono", cols["manzana"]: "manzana", cols["lote"]: "lote"})
    )
    data = data.fillna("")
    data["poligono"] = data["poligono"].astype(str).str.strip()
    data["manzana"] = data["manzana"].astype(str).str.strip()
    data["lote"] = data["lote"].astype(str).str.strip()
    data = data[(data["poligono"] != "") & (data["manzana"] != "") & (data["lote"] != "")]
    data = data.drop_duplicates(subset=["poligono", "manzana", "lote"])

    if data.empty:
        return 0, 0, 0

    now = _now_iso()
    manzanas_creadas = 0
    manzanas_actualizadas = 0
    lotes_nuevos = 0

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for _, row in data.iterrows():
            poligono = row["poligono"]
            manzana = row["manzana"]
            lote = row["lote"]

            manzana_row = conn.execute(
                """
                SELECT id
                FROM manzanas
                WHERE poligono = ? AND manzana = ?
                """,
                (poligono, manzana),
            ).fetchone()

            if manzana_row is None:
                cursor = conn.execute(
                    """
                    INSERT INTO manzanas (
                        poligono, manzana, estado, operador_activo, supervisor_activo,
                        fecha_asignacion_activa, fecha_cierre_activa, created_at, updated_at
                    ) VALUES (?, ?, 'Sin asignar', NULL, NULL, NULL, NULL, ?, ?)
                    """,
                    (poligono, manzana, now, now),
                )
                manzana_id = cursor.lastrowid
                manzanas_creadas += 1
            else:
                manzana_id = manzana_row["id"]
                conn.execute(
                    """
                    UPDATE manzanas
                    SET updated_at = ?
                    WHERE id = ?
                    """,
                    (now, manzana_id),
                )
                manzanas_actualizadas += 1

            lote_existente = conn.execute(
                """
                SELECT id
                FROM lotes
                WHERE manzana_id = ? AND lote = ?
                """,
                (manzana_id, lote),
            ).fetchone()
            if lote_existente is None:
                conn.execute(
                    """
                    INSERT INTO lotes (manzana_id, lote, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (manzana_id, lote, now),
                )
                lotes_nuevos += 1

        conn.commit()

    return manzanas_creadas, manzanas_actualizadas, lotes_nuevos



def get_all() -> list[dict[str, Any]]:
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

    return [
        {
            "id": r["id"],
            "poligono": r["poligono"],
            "manzana": r["manzana"],
            "estado": r["estado"],
            "operador_activo": r["operador_activo"],
            "supervisor_activo": r["supervisor_activo"],
            "fecha_asignacion_activa": r["fecha_asignacion_activa"],
            "fecha_cierre_activa": r["fecha_cierre_activa"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "total_lotes": r["total_lotes"],
        }
        for r in rows
    ]



def listar_poligonos() -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT poligono
            FROM manzanas
            ORDER BY poligono
            """
        ).fetchall()
    return [r["poligono"] for r in rows]



def operador_tiene_activa(operador: str) -> dict[str, Any] | None:
    init_db()
    operador = (operador or "").strip()
    if not operador:
        return None

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, poligono, manzana, estado, operador_activo, supervisor_activo, fecha_asignacion_activa
            FROM manzanas
            WHERE operador_activo = ? AND estado = 'En proceso'
            LIMIT 1
            """,
            (operador,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "poligono": row["poligono"],
        "manzana": row["manzana"],
        "estado": row["estado"],
        "operador_activo": row["operador_activo"],
        "supervisor_activo": row["supervisor_activo"],
        "fecha_asignacion_activa": row["fecha_asignacion_activa"],
    }



def asignar_manzana(poligono: str, manzana: str, operador: str, supervisor: str) -> tuple[bool, str]:
    init_db()

    poligono = (poligono or "").strip()
    manzana = (manzana or "").strip()
    operador = (operador or "").strip()
    supervisor = (supervisor or "").strip()

    if not poligono or not manzana or not operador or not supervisor:
        return False, "Polígono, manzana, operador y supervisor son obligatorios."

    now = _now_iso()

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

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
                f"El operador '{operador}' ya tiene activa la manzana {activa['poligono']}-{activa['manzana']}.",
            )

        row = conn.execute(
            """
            SELECT id, estado
            FROM manzanas
            WHERE poligono = ? AND manzana = ?
            """,
            (poligono, manzana),
        ).fetchone()

        if row is None:
            conn.rollback()
            return False, f"No existe la manzana {poligono}-{manzana}."

        if row["estado"] not in {"Sin asignar", "En conflicto"}:
            conn.rollback()
            return False, f"La manzana {poligono}-{manzana} está en estado '{row['estado']}' y no se puede asignar."

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
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                poligono,
                manzana,
                operador,
                supervisor,
                row["estado"],
                "En proceso",
                now,
                None,
                "Asignación activa",
            ),
        )

        conn.commit()

    return True, f"Manzana {poligono}-{manzana} asignada a {operador}."



def cerrar_manzana(poligono: str, manzana: str, operador: str, estado_final: str) -> tuple[bool, str]:
    init_db()

    poligono = (poligono or "").strip()
    manzana = (manzana or "").strip()
    operador = (operador or "").strip()
    estado_final = (estado_final or "").strip()

    if estado_final not in ESTADOS_CIERRE:
        return False, "El estado final debe ser 'Finalizada' o 'En conflicto'."

    if not poligono or not manzana or not operador:
        return False, "Polígono, manzana y operador son obligatorios."

    now = _now_iso()

    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT id, estado, operador_activo, supervisor_activo, fecha_asignacion_activa
            FROM manzanas
            WHERE poligono = ? AND manzana = ?
            """,
            (poligono, manzana),
        ).fetchone()

        if row is None:
            conn.rollback()
            return False, f"No existe la manzana {poligono}-{manzana}."

        if row["estado"] != "En proceso":
            conn.rollback()
            return False, f"La manzana {poligono}-{manzana} está en estado '{row['estado']}' y no se puede cerrar."

        if row["operador_activo"] != operador:
            conn.rollback()
            return False, "Solo el operador asignado actualmente puede cerrar esta manzana."

        conn.execute(
            """
            UPDATE manzanas
            SET estado = ?,
                operador_activo = NULL,
                supervisor_activo = NULL,
                fecha_cierre_activa = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (estado_final, now, now, row["id"]),
        )

        conn.execute(
            """
            INSERT INTO historial_asignaciones (
                manzana_id, poligono, manzana, operador, supervisor,
                estado_inicio, estado_fin, fecha_asignacion, fecha_cierre, detalle
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                poligono,
                manzana,
                operador,
                row["supervisor_activo"],
                "En proceso",
                estado_final,
                row["fecha_asignacion_activa"],
                now,
                "Cierre operativo",
            ),
        )

        conn.commit()

    return True, f"Manzana {poligono}-{manzana} cerrada en estado '{estado_final}'."
