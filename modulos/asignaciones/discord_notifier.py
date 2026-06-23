"""Envío de notificaciones a Discord mediante webhook."""

import os
import logging
import requests

logger = logging.getLogger(__name__)


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
    except requests.RequestException as exc:
        logger.warning("No se pudo enviar notificación a Discord: %s", exc)
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


def notify_cierre(
    operador: str, supervisor: str, manzana: str, estado_final: str = "Finalizada"
) -> bool:
    """Notifica que una manzana fue cerrada con estado final."""
    payload = {
        "embeds": [
            {
                "title": f"✅ Manzana Cerrada → {estado_final}",
                "color": 0xF39C12,
                "fields": [
                    {"name": "Manzana", "value": manzana, "inline": True},
                    {"name": "Operador", "value": operador, "inline": True},
                    {"name": "Supervisor", "value": supervisor, "inline": True},
                    {"name": "Estado Final", "value": estado_final, "inline": True},
                ],
            }
        ]
    }
    return _send(payload)
