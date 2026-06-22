"""
App Streamlit para asignación de manzanas con notificaciones Discord.

Ejecutar:
    streamlit run modulos/asignaciones/app_asignaciones_discord.py
"""

import io

import pandas as pd
import streamlit as st

from modulos.asignaciones import discord_notifier, storage

st.set_page_config(page_title="Asignaciones de Manzanas", page_icon="🏘️", layout="wide")
st.title("🏘️ Asignaciones de Manzanas — Piloto Discord")

# ---------------------------------------------------------------------------
# Sidebar: datos del operador / supervisor
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("👤 Datos del operador")
    operador = st.text_input("Operador", placeholder="Nombre del operador")
    supervisor = st.text_input("Supervisor", placeholder="Nombre del supervisor")
    st.divider()
    st.caption("Las notificaciones Discord se envían automáticamente al asignar o cerrar manzanas.")

# ---------------------------------------------------------------------------
# Sección 1: Carga de Excel
# ---------------------------------------------------------------------------
st.header("1. Cargar Excel con manzanas")

archivo = st.file_uploader(
    "Selecciona un archivo Excel (.xlsx o .xlsb)",
    type=["xlsx", "xlsb"],
)

if archivo is not None:
    nombre = archivo.name
    raw = archivo.read()
    try:
        if nombre.endswith(".xlsb"):
            df = pd.read_excel(io.BytesIO(raw), engine="pyxlsb")
        else:
            df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")

        st.success(f"Archivo cargado: {nombre} — {len(df)} filas, {len(df.columns)} columnas.")
        st.dataframe(df.head(10), use_container_width=True)

        col_manzana = None
        for c in df.columns:
            if "manzana" in str(c).lower():
                col_manzana = c
                break

        if col_manzana is None:
            col_manzana = st.selectbox(
                "No se detectó columna 'manzana'. Selecciona la columna correcta:",
                options=list(df.columns),
            )

        if col_manzana:
            manzanas_raw = df[col_manzana].dropna().astype(str).str.strip().unique().tolist()
            manzanas_raw = [m for m in manzanas_raw if m]
            st.info(f"Manzanas detectadas: **{len(manzanas_raw)}**")
            st.write(manzanas_raw[:20])

            if st.button("📥 Registrar manzanas en el sistema"):
                storage.registrar_manzanas(manzanas_raw)
                st.success(f"{len(manzanas_raw)} manzanas registradas (las nuevas en estado 'Sin asignar').")

    except Exception as e:
        st.error(f"Error al leer el archivo: {e}")

# ---------------------------------------------------------------------------
# Sección 2: Asignar manzana
# ---------------------------------------------------------------------------
st.divider()
st.header("2. Asignar manzana")

data = storage.get_all()
manzanas_sin_asignar = [m for m, r in data.items() if r["estado"] == "Sin asignar"]

if not manzanas_sin_asignar:
    st.info("No hay manzanas disponibles para asignar. Carga un Excel y regístralas primero.")
else:
    manzana_sel = st.selectbox("Selecciona manzana a asignar:", manzanas_sin_asignar)

    if st.button("✅ Asignar manzana"):
        if not operador.strip():
            st.warning("Ingresa el nombre del operador en el panel lateral.")
        elif not supervisor.strip():
            st.warning("Ingresa el nombre del supervisor en el panel lateral.")
        else:
            ok, msg = storage.asignar_manzana(manzana_sel, operador.strip(), supervisor.strip())
            if ok:
                notif_ok = discord_notifier.notify_asignacion(
                    operador.strip(), supervisor.strip(), manzana_sel
                )
                st.success(msg)
                if notif_ok:
                    st.caption("📨 Notificación Discord enviada.")
                else:
                    st.caption("⚠️ No se pudo enviar la notificación Discord (revisa DISCORD_WEBHOOK_URL).")
            else:
                st.error(msg)

# ---------------------------------------------------------------------------
# Sección 3: Cerrar manzana (→ Pendiente QC)
# ---------------------------------------------------------------------------
st.divider()
st.header("3. Cerrar manzana → Pendiente QC")

data = storage.get_all()
manzanas_asignadas = [m for m, r in data.items() if r["estado"] == "Asignada"]

if not manzanas_asignadas:
    st.info("No hay manzanas en estado 'Asignada' para cerrar.")
else:
    manzana_cierre = st.selectbox("Selecciona manzana a cerrar:", manzanas_asignadas)

    if st.button("🔒 Cerrar manzana"):
        registro = storage.get_manzana(manzana_cierre)
        ok, msg = storage.cerrar_manzana(manzana_cierre)
        if ok:
            notif_ok = discord_notifier.notify_cierre(
                registro.get("operador", ""), registro.get("supervisor", ""), manzana_cierre
            )
            st.success(msg)
            if notif_ok:
                st.caption("📨 Notificación Discord enviada.")
            else:
                st.caption("⚠️ No se pudo enviar la notificación Discord (revisa DISCORD_WEBHOOK_URL).")
        else:
            st.error(msg)

# ---------------------------------------------------------------------------
# Sección 4: Tabla resumen
# ---------------------------------------------------------------------------
st.divider()
st.header("4. Resumen de asignaciones")

data = storage.get_all()
if not data:
    st.info("Aún no hay manzanas registradas.")
else:
    rows = []
    for manzana, r in data.items():
        rows.append(
            {
                "Manzana": manzana,
                "Estado": r["estado"],
                "Operador": r["operador"] or "—",
                "Supervisor": r["supervisor"] or "—",
                "Fecha Asignación": r["fecha_asignacion"] or "—",
                "Fecha Cierre": r["fecha_cierre"] or "—",
            }
        )
    df_resumen = pd.DataFrame(rows)

    estado_filtro = st.multiselect(
        "Filtrar por estado:",
        options=storage.ESTADOS,
        default=storage.ESTADOS,
    )
    df_filtrado = df_resumen[df_resumen["Estado"].isin(estado_filtro)]
    st.dataframe(df_filtrado, use_container_width=True)
    st.caption(f"Total: {len(df_filtrado)} manzanas")
