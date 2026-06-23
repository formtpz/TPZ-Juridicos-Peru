"""App Streamlit para asignaciones por manzana con SQLite y Discord."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from modulos.asignaciones import discord_notifier, storage

st.set_page_config(page_title="Asignaciones de Manzanas", page_icon="🏘️", layout="wide")
st.title("🏘️ Asignaciones de Manzanas")
storage.init_db()


def _leer_excel(archivo) -> pd.DataFrame:
    nombre = archivo.name.lower()
    raw = archivo.read()
    if nombre.endswith(".xlsb"):
        return pd.read_excel(io.BytesIO(raw), engine="pyxlsb")
    return pd.read_excel(io.BytesIO(raw), engine="openpyxl")


def _to_df() -> pd.DataFrame:
    data = storage.get_all()
    if not data:
        return pd.DataFrame(
            columns=[
                "Poligono",
                "Manzana",
                "Estado",
                "Operador",
                "Supervisor",
                "Fecha Asignacion",
                "Fecha Cierre",
                "Total Lotes",
            ]
        )
    return pd.DataFrame(
        [
            {
                "Poligono": r["poligono"],
                "Manzana": r["manzana"],
                "Estado": r["estado"],
                "Operador": r["operador_activo"] or "—",
                "Supervisor": r["supervisor_activo"] or "—",
                "Fecha Asignacion": r["fecha_asignacion_activa"] or "—",
                "Fecha Cierre": r["fecha_cierre_activa"] or "—",
                "Total Lotes": r["total_lotes"],
            }
            for r in data
        ]
    )


def _parse_seleccion(valor: str) -> tuple[str, str] | None:
    if not valor or "|" not in valor:
        return None
    parts = [x.strip() for x in valor.split("|", maxsplit=1)]
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


st.header("1) Carga de Excel (Poligono / Manzana / Lote)")
archivo = st.file_uploader("Sube archivo .xlsx o .xlsb", type=["xlsx", "xlsb"])
if archivo is not None:
    try:
        df_excel = _leer_excel(archivo)
        st.success(
            f"Archivo cargado: {archivo.name} — {len(df_excel)} filas y {len(df_excel.columns)} columnas."
        )
        st.dataframe(df_excel.head(20), use_container_width=True)
        if st.button("📥 Registrar / actualizar en base SQLite", use_container_width=True):
            resumen = storage.registrar_desde_dataframe(df_excel)
            st.success(
                "Carga completada. "
                f"Manzanas detectadas: {resumen['manzanas_detectadas']}, "
                f"manzanas nuevas: {resumen['manzanas_insertadas']}, "
                f"lotes detectados: {resumen['lotes_detectados']}, "
                f"lotes nuevos: {resumen['lotes_insertados']}."
            )
            st.rerun()
    except Exception as exc:
        st.error(f"No se pudo procesar el Excel: {exc}")


st.divider()
st.header("2) Operarios (asignar / cerrar)")

col_op, col_sup = st.columns(2)
operador = col_op.text_input("Operario", placeholder="Nombre del operario")
supervisor = col_sup.text_input("Supervisor", placeholder="Nombre del supervisor")

df_estado = _to_df()

col_asig, col_cierre = st.columns(2)
with col_asig:
    st.subheader("Asignar manzana")
    disponibles_df = df_estado[df_estado["Estado"] == "Sin asignar"]
    opciones_asignar = [
        f"{r['Poligono']} | {r['Manzana']}" for _, r in disponibles_df.iterrows()
    ]
    manzana_asignar = st.selectbox(
        "Manzanas disponibles",
        options=opciones_asignar,
        index=None,
        placeholder="Selecciona polígono/manzana",
        key="sel_asignar",
    )
    if st.button("✅ Asignar", use_container_width=True):
        if not operador.strip() or not supervisor.strip():
            st.warning("Debes ingresar operario y supervisor.")
        elif not manzana_asignar:
            st.warning("Selecciona una manzana disponible.")
        else:
            seleccion = _parse_seleccion(manzana_asignar)
            if not seleccion:
                st.error("Selección inválida de manzana.")
            else:
                poligono, manzana = seleccion
                ok, msg = storage.asignar_manzana(poligono, manzana, operador.strip(), supervisor.strip())
                if ok:
                    notif_ok = discord_notifier.notify_asignacion(
                        operador.strip(), supervisor.strip(), f"{poligono}-{manzana}"
                    )
                    st.success(msg)
                    st.caption(
                        "📨 Notificación Discord enviada."
                        if notif_ok
                        else "⚠️ No se pudo enviar la notificación Discord."
                    )
                    st.rerun()
                else:
                    st.error(msg)

with col_cierre:
    st.subheader("Cerrar manzana")
    operador_limpio = operador.strip().lower()
    if operador_limpio:
        en_proceso_df = df_estado[
            (df_estado["Estado"] == "En proceso")
            & (df_estado["Operador"].str.strip().str.lower() == operador_limpio)
        ]
    else:
        en_proceso_df = pd.DataFrame()
    opciones_cierre = [f"{r['Poligono']} | {r['Manzana']}" for _, r in en_proceso_df.iterrows()]
    manzana_cierre = st.selectbox(
        "Manzanas activas del operario",
        options=opciones_cierre,
        index=None,
        placeholder="Selecciona manzana a cerrar",
        key="sel_cierre",
    )
    estado_final = st.radio("Estado final", options=storage.ESTADOS_CIERRE, horizontal=True)
    if st.button("🔒 Cerrar", use_container_width=True):
        if not operador.strip():
            st.warning("Debes ingresar operario.")
        elif not manzana_cierre:
            st.warning("No hay manzana activa seleccionada para cierre.")
        else:
            seleccion = _parse_seleccion(manzana_cierre)
            if not seleccion:
                st.error("Selección inválida de manzana.")
            else:
                poligono, manzana = seleccion
                supervisor_actual = "—"
                match = df_estado[
                    (df_estado["Poligono"] == poligono) & (df_estado["Manzana"] == manzana)
                ]
                if not match.empty:
                    supervisor_actual = match.iloc[0]["Supervisor"]
                ok, msg = storage.cerrar_manzana(poligono, manzana, operador.strip(), estado_final)
                if ok:
                    notif_ok = discord_notifier.notify_cierre(
                        operador.strip(), supervisor_actual, f"{poligono}-{manzana}", estado_final
                    )
                    st.success(msg)
                    st.caption(
                        "📨 Notificación Discord enviada."
                        if notif_ok
                        else "⚠️ No se pudo enviar la notificación Discord."
                    )
                    st.rerun()
                else:
                    st.error(msg)


st.divider()
st.header("3) Supervisión (vista colaborativa)")

df_estado = _to_df()
if df_estado.empty:
    st.info("Aún no hay manzanas cargadas.")
else:
    poligonos = sorted(df_estado["Poligono"].astype(str).unique().tolist())
    operadores = sorted(
        [o for o in df_estado["Operador"].astype(str).unique().tolist() if o != "—"]
    )

    f1, f2, f3 = st.columns(3)
    poligonos_sel = f1.multiselect("Filtrar polígono", options=poligonos)
    estados_sel = f2.multiselect("Filtrar estado", options=storage.ESTADOS, default=storage.ESTADOS)
    operadores_sel = f3.multiselect("Filtrar operario", options=operadores)

    if poligonos_sel:
        filtro_poligonos = df_estado["Poligono"].isin(poligonos_sel)
    else:
        filtro_poligonos = df_estado["Poligono"].notna()

    df_f = df_estado[filtro_poligonos & df_estado["Estado"].isin(estados_sel)]
    if operadores_sel:
        df_f = df_f[df_f["Operador"].isin(operadores_sel)]

    total = len(df_f)
    en_proceso = int((df_f["Estado"] == "En proceso").sum())
    finalizadas = int((df_f["Estado"] == "Finalizada").sum())
    conflicto = int((df_f["Estado"] == "En conflicto").sum())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total manzanas", total)
    k2.metric("En proceso", en_proceso)
    k3.metric("Finalizadas", finalizadas)
    k4.metric("En conflicto", conflicto)

    avance = (
        df_f.groupby("Poligono", as_index=False)
        .agg(total_manzanas=("Manzana", "count"), finalizadas=("Estado", lambda s: (s == "Finalizada").sum()))
    )
    if not avance.empty:
        avance["avance_%"] = (avance["finalizadas"] / avance["total_manzanas"] * 100).round(2)
        st.subheader("Avance por polígono")
        st.dataframe(avance, use_container_width=True)

    st.subheader("Tabla colaborativa")
    st.dataframe(df_f.sort_values(["Poligono", "Manzana"]), use_container_width=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_f.sort_values(["Poligono", "Manzana"]).to_excel(
            writer, sheet_name="estado_actual", index=False
        )
        if not avance.empty:
            avance.to_excel(writer, sheet_name="avance_poligono", index=False)
    output.seek(0)

    st.download_button(
        "📤 Exportar excel colaborativo",
        data=output.getvalue(),
        file_name="asignaciones_estado_actual.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
