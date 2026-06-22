# Módulo de Asignaciones de Manzanas — Piloto Discord

Módulo desacoplado para gestionar la asignación de manzanas a operadores, con notificaciones automáticas a Discord.

## Archivos

| Archivo | Descripción |
|---|---|
| `__init__.py` | Marca el directorio como paquete Python |
| `discord_notifier.py` | Envío de notificaciones a Discord vía webhook |
| `storage.py` | Lectura/escritura de asignaciones en JSON local |
| `app_asignaciones_discord.py` | Interfaz Streamlit para gestionar asignaciones |

Las asignaciones se persisten en `Repositorio_de_Asignaciones/asignaciones.json` en la raíz del repositorio.

## Configuración

Crea un archivo `.env` en la raíz del repositorio (o configura la variable de entorno):

```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/TU_WEBHOOK_AQUI
```

> Si la variable no está configurada, la app funciona normalmente pero no envía notificaciones Discord.

## Cómo ejecutar

```bash
streamlit run modulos/asignaciones/app_asignaciones_discord.py
```

## Estados de manzanas

| Estado | Descripción |
|---|---|
| Sin asignar | Manzana disponible para asignar |
| Asignada | Asignada a un operador activo |
| Pendiente QC | Trabajo completado, en espera de revisión |
| Terminada | Revisión completada |

## Reglas de negocio

- Una manzana solo puede estar asignada a un operador a la vez.
- Un operador solo puede tener **una** manzana en estado `Asignada` simultáneamente.
- El flujo de estados es: `Sin asignar` → `Asignada` → `Pendiente QC` → `Terminada`.

## Dependencias necesarias

```
streamlit
pandas
openpyxl
pyxlsb
requests
python-dotenv
```

## Notas

- Este módulo es **independiente** de `modulos/filtro_errores.py`.
- No usar en producción sin pruebas previas.
