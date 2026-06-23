"""Persistencia de asignaciones en SQLite (colaborativa)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2] / "Repositorio_de_Asignaciones"
DB_FILE = REPO_DIR / "asignaciones.db"

ESTADOS = ["Sin asignar", "Asignada", "Pendiente QC", "Terminada"]


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
            CREATE TABLE IF NOT EXISTS asignaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manzana TEXT NOT NULL UNIQUE,
                estado TEXT NOT NULL,
                operador TEXT,
                supervisor TEXT,
                fecha_asignacion TEXT,
                fecha_cierre TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manzana TEXT NOT NULL,
                evento TEXT NOT NULL,
                operador TEXT,
                supervisor TEXT,
                estado_anterior TEXT,
                estado_nuevo TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _log_evento(
    conn: sqlite3.Connection,
    *,
    manzana: str,
    evento: str,
    operador: str | None,
    supervisor: str | None,
    estado_anterior: str | None,
    estado_nuevo: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO historial (
            manzana, evento, operador, supervisor, estado_anterior, estado_nuevo, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            manzana,
            evento,
            operador,
            supervisor,
            estado_anterior,
            estado_nuevo,
            _now_iso(),
        ),
    )


def get_all() -> dict:
    """Retorna todas las asignaciones en formato compatible con el flujo previo."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT manzana, estado, operador, supervisor, fecha_asignacion, fecha_cierre
            FROM asignaciones
            ORDER BY manzana
            """
        ).fetchall()

    data: dict[str, dict] = {}
    for r in rows:
        data[r["manzana"]] = {
            "estado": r["estado"],
            "operador": r["operador"],
            "supervisor": r["supervisor"],
            "fecha_asignacion": r["fecha_asignacion"],
            "fecha_cierre": r["fecha_cierre"],
        }
    return data


def get_manzana(manzana: str) -> dict | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """
            SELECT manzana, estado, operador, supervisor, fecha_asignacion, fecha_cierre
            FROM asignaciones
            WHERE manzana = ?
            """,
            (manzana,),
        ).fetchone()

    if not r:
        return None

    return {
        "estado": r["estado"],
        "operador": r["operador"],
        "supervisor": r["supervisor"],
        "fecha_asignacion": r["fecha_asignacion"],
        "fecha_cierre": r["fecha_cierre"],
    }


def registrar_manzanas(manzanas: list[str]) -> None:
    """Registra manzanas nuevas con estado 'Sin asignar'."""
    init_db()
    now = _now_iso()
    with _connect() as conn:
        for m in manzanas:
            manzana = (m or "").strip()
            if not manzana:
                continue

            cur = conn.execute(
                "SELECT manzana FROM asignaciones WHERE manzana = ?",
                (manzana,),
            ).fetchone()
            if cur:
                continue

            conn.execute(
                """
                INSERT INTO asignaciones (
                    manzana, estado, operador, supervisor, fecha_asignacion, fecha_cierre, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (manzana, "Sin asignar", None, None, None, None, now, now),
            )
            _log_evento(
                conn,
                manzana=manzana,
                evento="registro",
                operador=None,
                supervisor=None,
                estado_anterior=None,
                estado_nuevo="Sin asignar",
            )
        conn.commit()


def asignar_manzana(manzana: str, operador: str, supervisor: str) -> tuple[bool, str]:
    """
    Asigna una manzana a un operador.
    Retorna (éxito, mensaje).
    """
    init_db()

    manzana = (manzana or "").strip()
    operador = (operador or "").strip()
    supervisor = (supervisor or "").strip()

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT manzana, estado, operador
            FROM asignaciones
            WHERE manzana = ?
            """,
            (manzana,),
        ).fetchone()

        if not row:
            return False, f"Manzana '{manzana}' no encontrada."

        if row["estado"] == "Asignada":
            if row["operador"] == operador:
                return False, f"La manzana '{manzana}' ya está asignada a {operador}."
            return False, f"La manzana '{manzana}' ya está asignada a {row['operador']}."

        if row["estado"] != "Sin asignar":
            return (
                False,
                f"La manzana '{manzana}' está en estado '{row['estado']}' y no puede ser asignada.",
            )

        activa = conn.execute(
            """
            SELECT manzana
            FROM asignaciones
            WHERE operador = ? AND estado = 'Asignada'
            LIMIT 1
            """,
            (operador,),
        ).fetchone()
        if activa:
            return (
                False,
                f"El operador '{operador}' ya tiene la manzana '{activa['manzana']}' activa (Asignada).",
            )

        now = _now_iso()
        conn.execute(
            """
            UPDATE asignaciones
            SET estado = 'Asignada',
                operador = ?,
                supervisor = ?,
                fecha_asignacion = ?,
                fecha_cierre = NULL,
                updated_at = ?
            WHERE manzana = ?
            """,
            (operador, supervisor or None, now, now, manzana),
        )
        _log_evento(
            conn,
            manzana=manzana,
            evento="asignacion",
            operador=operador,
            supervisor=supervisor or None,
            estado_anterior="Sin asignar",
            estado_nuevo="Asignada",
        )
        conn.commit()

    return True, f"Manzana '{manzana}' asignada exitosamente a {operador}."


def cerrar_manzana(manzana: str) -> tuple[bool, str]:
    """
    Cierra una manzana pasándola a 'Pendiente QC'.
    Retorna (éxito, mensaje).
    """
    init_db()

    manzana = (manzana or "").strip()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT manzana, estado, operador, supervisor
            FROM asignaciones
            WHERE manzana = ?
            """,
            (manzana,),
        ).fetchone()

        if not row:
            return False, f"Manzana '{manzana}' no encontrada."

        if row["estado"] != "Asignada":
            return (
                False,
                f"La manzana '{manzana}' está en estado '{row['estado']}'. Solo se pueden cerrar manzanas en estado 'Asignada'.",
            )

        now = _now_iso()
        conn.execute(
            """
            UPDATE asignaciones
            SET estado = 'Pendiente QC',
                fecha_cierre = ?,
                updated_at = ?
            WHERE manzana = ?
            """,
            (now, now, manzana),
        )
        _log_evento(
            conn,
            manzana=manzana,
            evento="cierre",
            operador=row["operador"],
            supervisor=row["supervisor"],
            estado_anterior="Asignada",
            estado_nuevo="Pendiente QC",
        )
        conn.commit()

    return True, f"Manzana '{manzana}' cerrada → Pendiente QC."
