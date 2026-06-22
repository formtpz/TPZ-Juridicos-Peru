"""Envío de notificaciones a Discord mediante webhook."""

import os
import requests


def _get_webhook_url() -> str | None:
    return os.environ.get("DISCORD_WEBHOOK_URL")


def _send(payload: dict) -> bool:
    """Envía payload a Discord. Retorna True si fue exitoso."""
    url = _get_webhook_url()
    if not url:
        return False
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception:
        return False


def notify_asignacion(operador: str, supervisor: str, manzana: str) -> bool:
    """Notifica que una manzana fue asignada a un operador."""
    payload = {
        "embeds": [
            {
                "title": "🏘️ Manzana Asignada",
                "color": 0x2ECC71,
                "fields": [
                    {"name": "Manzana", "value": manzana, "inline": True},
                    {"name": "Operador", "value": operador, "inline": True},
                    {"name": "Supervisor", "value": supervisor, "inline": True},
                ],
            }
        ]
    }
    return _send(payload)


def notify_cierre(operador: str, supervisor: str, manzana: str) -> bool:
    """Notifica que una manzana fue cerrada y pasa a Pendiente QC."""
    payload = {
        "embeds": [
            {
                "title": "✅ Manzana Cerrada → Pendiente QC",
                "color": 0xF39C12,
                "fields": [
                    {"name": "Manzana", "value": manzana, "inline": True},
                    {"name": "Operador", "value": operador, "inline": True},
                    {"name": "Supervisor", "value": supervisor, "inline": True},
                ],
            }
        ]
    }
    return _send(payload)
