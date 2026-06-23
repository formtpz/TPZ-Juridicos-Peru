# modulos/seguimiento_supervision.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db import fetch_df

TZ = pytz.timezone('America/Guatemala')

TASAS_POR_HORA = {
    'Precampo': 8,
    'Control de Calidad Precampo': 10,
    'Postcampo': 7,
    'Control de Calidad Postcampo': 10,
    'Vinculación Precampo': 5,
    'Control de Calidad Vinculación Precampo': 10
}

@st.cache_data(ttl=300)
def obtener_personal_asignado(supervisor_nombre):
    df = fetch_df(
        "SELECT nombre FROM usuarios WHERE supervisor = %s AND estado = 'Activo' ORDER BY nombre",
        params=[supervisor_nombre]
    )
    return df['nombre'].tolist() if not df.empty else []


def cargar_datos_personal(fechas, personal):
    """Carga datos de registro, capacitaciones y otros_registros."""
    fecha_inicio, fecha_fin = fechas
    if not personal:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Construir placeholders para IN
    placeholders = ', '.join(['%s'] * len(personal))
    params_r = personal + [fecha_inicio, fecha_fin]
    query_r = f"""
        SELECT 
            nombre, fecha, proceso, tipo,
            COALESCE(edificas::float, 0) AS edificas,
            COALESCE(unidades_catastrales::float, 0) AS unidades_catastrales,
            COALESCE(horas::float, 0) AS horas
        FROM registro
        WHERE nombre IN ({placeholders})
          AND fecha::date >= %s AND fecha::date <= %s
          AND tipo NOT IN ('Producción Horas Extras', 'Inspección Horas Extras', 'Reproceso Horas Extras')
    """
    df_r = fetch_df(query_r, params=params_r)

    params_c = personal + [fecha_inicio, fecha_fin]
    query_c = f"""
        SELECT nombre, fecha, COALESCE(horas::float, 0) AS horas
        FROM capacitaciones
        WHERE nombre IN ({placeholders})
          AND fecha::date >= %s AND fecha::date <= %s
    """
    df_c = fetch_df(query_c, params=params_c)

    params_o = personal + [fecha_inicio, fecha_fin]
    query_o = f"""
        SELECT nombre, fecha, COALESCE(horas::float, 0) AS horas
        FROM otros_registros
        WHERE nombre IN ({placeholders})
          AND fecha::date >= %s AND fecha::date <= %s
          AND motivo NOT IN ('Horas Extra', 'Horas Extra Apoyo Otros Proyectos', 'Horas Extras', 'Reposición de tiempo')
    """
    df_o = fetch_df(query_o, params=params_o)

    return df_r, df_c, df_o


def generar_resumen_horas(df_r, df_c, df_o, personal, fechas):
    """Genera resumen de horas con todas las combinaciones nombre-fecha."""
    fechas_range = pd.date_range(start=fechas[0], end=fechas[1], freq='D')
    all_comb = pd.DataFrame([
        (nombre, fecha.date())
        for nombre in personal
        for fecha in fechas_range
    ], columns=['nombre', 'fecha'])

    # Agrupar
    prod = df_r.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_produccion'}) if not df_r.empty else pd.DataFrame(columns=['nombre', 'fecha', 'horas_produccion'])
    cap = df_c.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_capacitacion'}) if not df_c.empty else pd.DataFrame(columns=['nombre', 'fecha', 'horas_capacitacion'])
    otros = df_o.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_otros'}) if not df_o.empty else pd.DataFrame(columns=['nombre', 'fecha', 'horas_otros'])

    merged = all_comb.merge(prod, on=['nombre', 'fecha'], how='left')
    merged = merged.merge(cap, on=['nombre', 'fecha'], how='left')
    merged = merged.merge(otros, on=['nombre', 'fecha'], how='left')
    merged = merged.fillna(0)
    merged['total'] = merged['horas_produccion'] + merged['horas_capacitacion'] + merged['horas_otros']
    for col in ['horas_produccion', 'horas_capacitacion', 'horas_otros', 'total']:
        merged[col] = merged[col].round(2)
    # Marcar si tiene algún reporte (si alguna columna de horas > 0)
    merged['tiene_reporte'] = (merged['horas_produccion'] > 0) | (merged['horas_capacitacion'] > 0) | (merged['horas_otros'] > 0)
    return merged


def generar_produccion_diaria(df_r):
    if df_r.empty:
        return pd.DataFrame()
    grouped = df_r.groupby(['nombre', 'fecha', 'proceso'], as_index=False).agg({
        'horas': 'sum',
        'edificas': 'sum',
        'unidades_catastrales': 'sum'
    })
    grouped['ratio'] = np.where(
        grouped['horas'] > 0,
        (grouped['edificas'] + grouped['unidades_catastrales']) / grouped['horas'],
        0
    )
    grouped['ratio'] = grouped['ratio'].round(2)
    grouped['tasa'] = grouped['proceso'].map(TASAS_POR_HORA).fillna(0)
    grouped['valor_esperado'] = grouped['tasa'] * grouped['horas']
    grouped['diferencia'] = (grouped['edificas'] + grouped['unidades_catastrales']) - grouped['valor_esperado']
    grouped['diferencia'] = grouped['diferencia'].round(2)
    return grouped.sort_values(['fecha', 'nombre', 'proceso']).reset_index(drop=True)


def render():
    usuario = st.session_state.get("usuario")
    if not usuario:
        st.warning("Debe iniciar sesión")
        st.stop()

    nombre_supervisor = usuario.get("nombre")
    personal_asignado = obtener_personal_asignado(nombre_supervisor)
    if not personal_asignado:
        st.warning("No tiene personal a cargo.")
        return

    st.title("📊 Seguimiento de Supervisor")
    st.markdown(f"**Supervisor:** {nombre_supervisor} | **Personal a cargo:** {len(personal_asignado)}")

    hoy = datetime.now(TZ).date()
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha de inicio", value=hoy - timedelta(days=7), key="sup_fecha_ini")
    with col2:
        fecha_fin = st.date_input("Fecha de fin", value=hoy, key="sup_fecha_fin")

    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
        return

    with st.spinner("Cargando datos..."):
        df_r, df_c, df_o = cargar_datos_personal((fecha_inicio, fecha_fin), personal_asignado)

    # --- Depuración opcional (descomentar para ver si hay datos) ---
    # with st.expander("Depuración (datos crudos)"):
    #     st.write("Registro (df_r):", df_r.head() if not df_r.empty else "vacío")
    #     st.write("Capacitaciones (df_c):", df_c.head() if not df_c.empty else "vacío")
    #     st.write("Otros (df_o):", df_o.head() if not df_o.empty else "vacío")

    # --- Resumen de Horas (todos los días, con colores) ---
    st.subheader("📋 Resumen de Horas Diarias")
    df_horas = generar_resumen_horas(df_r, df_c, df_o, personal_asignado, (fecha_inicio, fecha_fin))

    # Aplicar estilo: verde si total == 8.5, amarillo si no (incluyendo 0)
    def color_total(val):
        if val == 8.5:
            return 'background-color: #90EE90'
        else:
            return 'background-color: #FFD700'
    styled_horas = df_horas.style.map(color_total, subset=['total'])
    st.dataframe(styled_horas, use_container_width=True)

    # --- Detalle de Casos a Revisar (total != 8.5) ---
    st.subheader("🔍 Detalle de Casos a Revisar")
    casos = df_horas[df_horas['total'] != 8.5].copy()
    if casos.empty:
        st.success("✅ Todos los días registran 8.5 horas exactas.")
    else:
        # Crear columna 'Caso'
        def determinar_caso(row):
            if not row['tiene_reporte']:
                return "Sin Reportes"
            elif row['total'] < 8.5:
                return f"Faltan {8.5 - row['total']:.2f} horas"
            else:
                return f"Excedente de {row['total'] - 8.5:.2f} horas"
        casos['Caso'] = casos.apply(determinar_caso, axis=1)
        casos_vista = casos[['nombre', 'fecha', 'total', 'Caso']]

        # Resaltar "Sin Reportes" en rojo
        def color_caso(val):
            if val == "Sin Reportes":
                return 'color: red; font-weight: bold'
            return ''
        styled_casos = casos_vista.style.map(color_caso, subset=['Caso'])
        st.dataframe(styled_casos, use_container_width=True)

    # --- Producción Diaria y Bajo Rendimiento ---
    st.subheader("📈 Producción Diaria por Proceso")
    df_prod = generar_produccion_diaria(df_r)
    if df_prod.empty:
        st.info("No hay datos de producción.")
    else:
        st.dataframe(df_prod, use_container_width=True)

        st.subheader("⚠️ Personal con Bajo Rendimiento")
        bajo = df_prod[df_prod['diferencia'] < 0].copy()
        if bajo.empty:
            st.success("✅ Todo el personal cumple las metas.")
        else:
            bajo['Faltante'] = bajo['diferencia'].abs().apply(lambda x: f"{x:.2f} unidades")
            st.dataframe(bajo[['fecha', 'nombre', 'proceso', 'diferencia', 'Faltante']], use_container_width=True)

    # Actualizar
    if st.button("🔄 Actualizar datos", type="secondary"):
        st.cache_data.clear()
        st.rerun()
