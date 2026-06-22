"""Persistencia de asignaciones en JSON local."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[2] / "Repositorio_de_Asignaciones"
STORAGE_FILE = REPO_DIR / "asignaciones.json"

ESTADOS = ["Sin asignar", "Asignada", "Pendiente QC", "Terminada"]


def _load() -> dict:
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    if STORAGE_FILE.exists():
        with open(STORAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(data: dict) -> None:
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    with open(STORAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_all() -> dict:
    """Retorna todas las asignaciones."""
    return _load()


def get_manzana(manzana: str) -> dict | None:
    data = _load()
    return data.get(manzana)


def registrar_manzanas(manzanas: list[str]) -> None:
    """Registra manzanas nuevas con estado 'Sin asignar'."""
    data = _load()
    for m in manzanas:
        if m not in data:
            data[m] = {
                "estado": "Sin asignar",
                "operador": None,
                "supervisor": None,
                "fecha_asignacion": None,
                "fecha_cierre": None,
            }
    _save(data)


def asignar_manzana(manzana: str, operador: str, supervisor: str) -> tuple[bool, str]:
    """
    Asigna una manzana a un operador.
    Retorna (éxito, mensaje).
    """
    data = _load()

    if manzana not in data:
        return False, f"Manzana '{manzana}' no encontrada."

    registro = data[manzana]
    if registro["estado"] == "Asignada":
        if registro["operador"] == operador:
            return False, f"La manzana '{manzana}' ya está asignada a {operador}."
        return False, (
            f"La manzana '{manzana}' ya está asignada a {registro['operador']}."
        )

    if registro["estado"] != "Sin asignar":
        return False, (
            f"La manzana '{manzana}' está en estado '{registro['estado']}' "
            "y no puede ser asignada."
        )

    # Un operador solo puede tener una manzana activa (Asignada)
    for m, r in data.items():
        if r.get("operador") == operador and r.get("estado") == "Asignada":
            return False, (
                f"El operador '{operador}' ya tiene la manzana '{m}' activa (Asignada)."
            )

    data[manzana] = {
        "estado": "Asignada",
        "operador": operador,
        "supervisor": supervisor,
        "fecha_asignacion": datetime.now(timezone.utc).isoformat(),
        "fecha_cierre": None,
    }
    _save(data)
    return True, f"Manzana '{manzana}' asignada exitosamente a {operador}."


def cerrar_manzana(manzana: str) -> tuple[bool, str]:
    """
    Cierra una manzana pasándola a 'Pendiente QC'.
    Retorna (éxito, mensaje).
    """
    data = _load()

    if manzana not in data:
        return False, f"Manzana '{manzana}' no encontrada."

    registro = data[manzana]
    if registro["estado"] != "Asignada":
        return False, (
            f"La manzana '{manzana}' está en estado '{registro['estado']}'. "
            "Solo se pueden cerrar manzanas en estado 'Asignada'."
        )

    data[manzana]["estado"] = "Pendiente QC"
    data[manzana]["fecha_cierre"] = datetime.now(timezone.utc).isoformat()
    _save(data)
    return True, f"Manzana '{manzana}' cerrada → Pendiente QC."
