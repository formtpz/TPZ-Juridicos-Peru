"""App Streamlit para asignaciones con notificaciones Discord."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from modulos.asignaciones import discord_notifier, storage

st.set_page_config(page_title="Asignaciones de Manzanas", page_icon="🏘️", layout="wide")
st.title("🏘️ Asignaciones de Manzanas")


def _leer_excel(raw: bytes, nombre: str) -> pd.DataFrame:
    if nombre.lower().endswith(".xlsb"):
        return pd.read_excel(io.BytesIO(raw), engine="pyxlsb")
    return pd.read_excel(io.BytesIO(raw), engine="openpyxl")


def _to_df(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(
            columns=[
                "Poligono",
                "Manzana",
                "Estado",
                "Operador",
                "Supervisor",
                "Lotes",
                "Fecha Asignación",
                "Fecha Cierre",
            ]
        )

    data = pd.DataFrame(rows)
    return data.rename(
        columns={
            "poligono": "Poligono",
            "manzana": "Manzana",
            "estado": "Estado",
            "operador_activo": "Operador",
            "supervisor_activo": "Supervisor",
            "total_lotes": "Lotes",
            "fecha_asignacion_activa": "Fecha Asignación",
            "fecha_cierre_activa": "Fecha Cierre",
        }
    )[
        [
            "Poligono",
            "Manzana",
            "Estado",
            "Operador",
            "Supervisor",
            "Lotes",
            "Fecha Asignación",
            "Fecha Cierre",
        ]
    ]


storage.init_db()

# 1) Carga de Excel
st.header("1) Cargar Excel inicial")
archivo = st.file_uploader("Archivo (.xlsx o .xlsb) con Poligono/Manzana/Lote", type=["xlsx", "xlsb"])

if archivo is not None:
    try:
        df_excel = _leer_excel(archivo.read(), archivo.name)
        st.success(f"Archivo cargado: {archivo.name} ({len(df_excel)} filas)")
        st.dataframe(df_excel.head(10), use_container_width=True)

        if st.button("📥 Registrar o actualizar datos"):
            creadas, actualizadas, lotes_nuevos = storage.registrar_desde_dataframe(df_excel)
            st.success(
                f"Proceso completado: {creadas} manzanas nuevas, {actualizadas} actualizadas, {lotes_nuevos} lotes nuevos."
            )
            st.rerun()
    except Exception as e:
        st.error(f"No se pudo procesar el Excel: {e}")

rows = storage.get_all()
df_estado = _to_df(rows)

# 2) Operarios (arriba)
st.divider()
st.header("2) Operarios")
col_asignar, col_cerrar = st.columns(2)

with col_asignar:
    st.subheader("Asignar manzana")
    with st.form("form_asignar"):
        operador = st.text_input("Operador", key="operador_asignar")
        supervisor = st.text_input("Supervisor", key="supervisor_asignar")

        disponibles = [
            f"{r['poligono']}|{r['manzana']}"
            for r in rows
            if r["estado"] in {"Sin asignar", "En conflicto"}
        ]
        seleccion = st.selectbox(
            "Manzanas disponibles",
            options=disponibles,
            format_func=lambda x: x.replace("|", " - "),
            disabled=not bool(disponibles),
        )
        enviar_asignacion = st.form_submit_button("✅ Asignar")

    if enviar_asignacion:
        if not disponibles:
            st.warning("No hay manzanas disponibles para asignación.")
        else:
            poligono, manzana = seleccion.split("|", maxsplit=1)
            ok, msg = storage.asignar_manzana(poligono, manzana, operador, supervisor)
            if ok:
                notif_ok = discord_notifier.notify_asignacion(
                    operador.strip(),
                    supervisor.strip(),
                    f"{poligono}-{manzana}",
                )
                st.success(msg)
                st.caption("📨 Notificación Discord enviada." if notif_ok else "⚠️ No se pudo enviar notificación Discord.")
                st.rerun()
            else:
                st.error(msg)

with col_cerrar:
    st.subheader("Cerrar manzana")
    with st.form("form_cerrar"):
        operador_cierre = st.text_input("Operador (cierre)", key="operador_cierre")
        en_proceso = [f"{r['poligono']}|{r['manzana']}" for r in rows if r["estado"] == "En proceso"]
        seleccion_cierre = st.selectbox(
            "Manzanas en proceso",
            options=en_proceso,
            format_func=lambda x: x.replace("|", " - "),
            disabled=not bool(en_proceso),
        )
        estado_final = st.radio("Estado final", options=storage.ESTADOS_CIERRE, horizontal=True)
        enviar_cierre = st.form_submit_button("🔒 Cerrar")

    if enviar_cierre:
        if not en_proceso:
            st.warning("No hay manzanas en proceso para cerrar.")
        else:
            poligono_c, manzana_c = seleccion_cierre.split("|", maxsplit=1)
            ok, msg = storage.cerrar_manzana(poligono_c, manzana_c, operador_cierre, estado_final)
            if ok:
                registro = next(
                    (
                        r
                        for r in rows
                        if r["poligono"] == poligono_c and r["manzana"] == manzana_c
                    ),
                    None,
                )
                notif_ok = discord_notifier.notify_cierre(
                    operador_cierre.strip(),
                    (registro or {}).get("supervisor_activo", "") or "-",
                    f"{poligono_c}-{manzana_c} ({estado_final})",
                )
                st.success(msg)
                st.caption("📨 Notificación Discord enviada." if notif_ok else "⚠️ No se pudo enviar notificación Discord.")
                st.rerun()
            else:
                st.error(msg)

# 3) Supervisión
st.divider()
st.header("3) Supervisión")

if df_estado.empty:
    st.info("Aún no hay manzanas registradas.")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total manzanas", len(df_estado))
    c2.metric("En proceso", int((df_estado["Estado"] == "En proceso").sum()))
    c3.metric("Finalizadas", int((df_estado["Estado"] == "Finalizada").sum()))
    c4.metric("En conflicto", int((df_estado["Estado"] == "En conflicto").sum()))

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        poligonos = ["Todos"] + storage.listar_poligonos()
        filtro_poligono = st.selectbox("Filtrar por polígono", poligonos)
    with col_f2:
        filtro_estado = st.multiselect("Filtrar por estado", storage.ESTADOS, default=storage.ESTADOS)
    with col_f3:
        operadores = ["Todos"] + sorted([op for op in df_estado["Operador"].dropna().unique() if str(op).strip()])
        filtro_operador = st.selectbox("Filtrar por operario", operadores)

    df_filtrado = df_estado.copy()
    if filtro_poligono != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Poligono"] == filtro_poligono]
    df_filtrado = df_filtrado[df_filtrado["Estado"].isin(filtro_estado)]
    if filtro_operador != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Operador"] == filtro_operador]

    st.dataframe(df_filtrado.fillna("—"), use_container_width=True)

    avance_poligono = (
        df_estado.groupby("Poligono", dropna=False)
        .agg(
            total=("Manzana", "count"),
            finalizadas=("Estado", lambda s: int((s == "Finalizada").sum())),
            en_proceso=("Estado", lambda s: int((s == "En proceso").sum())),
            en_conflicto=("Estado", lambda s: int((s == "En conflicto").sum())),
        )
        .reset_index()
    )
    avance_poligono["avance_%"] = (
        avance_poligono["finalizadas"].div(avance_poligono["total"].replace(0, pd.NA)).fillna(0) * 100
    ).round(2)

    st.subheader("Avance por polígono")
    st.dataframe(avance_poligono, use_container_width=True)

    salida = io.BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        df_filtrado.fillna("").to_excel(writer, index=False, sheet_name="estado_actual")
        avance_poligono.to_excel(writer, index=False, sheet_name="avance_poligono")

    st.download_button(
        "📤 Exportar excel colaborativo",
        data=salida.getvalue(),
        file_name="estado_colaborativo_asignaciones.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
