# Módulo de Asignaciones (SQLite + Streamlit + Discord)

## Archivos principales
- `app_asignaciones_discord.py`: interfaz colaborativa Streamlit.
- `storage.py`: persistencia SQLite y reglas transaccionales.
- `discord_notifier.py`: envío de notificaciones por webhook Discord.
- `REGLAS_ASIGNACIONES.md`: reglas funcionales y checklist operativo.

## Base de datos
Se usa `Repositorio_de_Asignaciones/asignaciones.db` con tablas:
- `manzanas`
- `lotes`
- `historial_asignaciones`

## Ejecución
```bash
streamlit run modulos/asignaciones/app_asignaciones_discord.py
```

## Configuración Discord
Variable esperada:
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```
