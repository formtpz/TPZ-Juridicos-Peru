# modulos/seguimiento_supervision.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db import fetch_df
import plotly.express as px

# Zona horaria
TZ = pytz.timezone('America/Guatemala')

# Tasas por proceso (unidades por hora)
TASAS_POR_HORA = {
    'Precampo': 8,
    'Control de Calidad Precampo': 10,
    'Postcampo': 7,
    'Control de Calidad Postcampo': 10,
    'Vinculación Precampo': 5,
    'Control de Calidad Vinculación Precampo': 10
}

# ============================================================
# FUNCIONES DE CARGA DE DATOS
# ============================================================

@st.cache_data(ttl=300)
def obtener_personal_asignado(supervisor_nombre):
    df = fetch_df(
        "SELECT nombre FROM usuarios WHERE supervisor = %s AND estado = 'Activo' ORDER BY nombre",
        params=[supervisor_nombre]
    )
    return df['nombre'].tolist() if not df.empty else []


@st.cache_data(ttl=60)
def cargar_datos_personal(fechas, personal):
    fecha_inicio, fecha_fin = fechas
    if not personal:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    query_r = """
        SELECT 
            nombre, 
            fecha::date as fecha,
            proceso,
            COALESCE(edificas::float, 0) AS edificas,
            COALESCE(unidades_catastrales::float, 0) AS unidades_catastrales,
            COALESCE(horas::float, 0) AS horas
        FROM registro
        WHERE nombre = ANY(%s)
          AND fecha::date >= %s 
          AND fecha::date <= %s
          AND tipo NOT IN ('Producción Horas Extras', 'Inspección Horas Extras', 'Reproceso Horas Extras')
    """
    df_r = fetch_df(query_r, params=[personal, fecha_inicio, fecha_fin])

    query_c = """
        SELECT 
            nombre, 
            fecha::date as fecha,
            COALESCE(horas::float, 0) AS horas
        FROM capacitaciones
        WHERE nombre = ANY(%s)
          AND fecha::date >= %s 
          AND fecha::date <= %s
    """
    df_c = fetch_df(query_c, params=[personal, fecha_inicio, fecha_fin])

    query_o = """
        SELECT 
            nombre, 
            fecha::date as fecha,
            COALESCE(horas::float, 0) AS horas
        FROM otros_registros
        WHERE nombre = ANY(%s)
          AND fecha::date >= %s 
          AND fecha::date <= %s
          AND motivo NOT IN ('Horas Extra', 'Horas Extra Apoyo Otros Proyectos', 'Horas Extras', 'Reposición de tiempo')
    """
    df_o = fetch_df(query_o, params=[personal, fecha_inicio, fecha_fin])

    return df_r, df_c, df_o


# ============================================================
# FUNCIONES DE PROCESAMIENTO
# ============================================================

def generar_resumen_horas(df_r, df_c, df_o):
    if not df_r.empty:
        prod = df_r.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_produccion'})
    else:
        prod = pd.DataFrame(columns=['nombre', 'fecha', 'horas_produccion'])

    if not df_c.empty:
        cap = df_c.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_capacitacion'})
    else:
        cap = pd.DataFrame(columns=['nombre', 'fecha', 'horas_capacitacion'])

    if not df_o.empty:
        otros = df_o.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_otros'})
    else:
        otros = pd.DataFrame(columns=['nombre', 'fecha', 'horas_otros'])

    combinados = pd.concat([prod[['nombre', 'fecha']], cap[['nombre', 'fecha']], otros[['nombre', 'fecha']]], axis=0)
    if combinados.empty:
        return pd.DataFrame()

    keys = combinados.drop_duplicates().reset_index(drop=True)
    merged = keys.merge(prod, on=['nombre', 'fecha'], how='left')
    merged = merged.merge(cap, on=['nombre', 'fecha'], how='left')
    merged = merged.merge(otros, on=['nombre', 'fecha'], how='left')
    merged = merged.fillna(0)

    merged['total'] = merged['horas_produccion'] + merged['horas_capacitacion'] + merged['horas_otros']
    for col in ['horas_produccion', 'horas_capacitacion', 'horas_otros', 'total']:
        if col in merged.columns:
            merged[col] = merged[col].round(2)

    return merged


def generar_produccion_diaria(df_r):
    """
    Genera tabla de producción diaria por persona y proceso.
    Columnas: nombre, fecha, proceso, horas, produccion (edificas+unidades),
    valor_esperado, cumplimiento (%).
    """
    if df_r.empty:
        return pd.DataFrame()

    grouped = df_r.groupby(['nombre', 'fecha', 'proceso'], as_index=False).agg({
        'horas': 'sum',
        'edificas': 'sum',
        'unidades_catastrales': 'sum'
    })

    # Producción total
    grouped['produccion'] = grouped['edificas'] + grouped['unidades_catastrales']

    # Valor esperado = tasa * horas
    grouped['tasa'] = grouped['proceso'].map(TASAS_POR_HORA).fillna(0)
    grouped['valor_esperado'] = grouped['tasa'] * grouped['horas']
    grouped['valor_esperado'] = grouped['valor_esperado'].round(2)

    # Cumplimiento = produccion / valor_esperado (en porcentaje)
    grouped['cumplimiento'] = np.where(
        grouped['valor_esperado'] > 0,
        (grouped['produccion'] / grouped['valor_esperado']) * 100,
        0
    )
    grouped['cumplimiento'] = grouped['cumplimiento'].round(1)

    # Ordenar
    grouped = grouped.sort_values(['fecha', 'nombre', 'proceso']).reset_index(drop=True)

    # Seleccionar columnas a mostrar
    return grouped[['nombre', 'fecha', 'proceso', 'horas', 'produccion', 'valor_esperado', 'cumplimiento']]


# ============================================================
# FUNCIÓN PRINCIPAL RENDER
# ============================================================

def render():
    usuario = st.session_state.get("usuario")
    if not usuario:
        st.warning("Debe iniciar sesión")
        st.stop()

    nombre_supervisor = usuario.get("nombre")
    personal_asignado = obtener_personal_asignado(nombre_supervisor)

    if not personal_asignado:
        st.warning("No tiene personal a cargo para supervisar.")
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

    # --- [DEPURACIÓN] ---
    with st.expander("🔍 Depuración (datos cargados)"):
        st.write("**Registro (df_r):**", f"Filas: {len(df_r)}")
        st.dataframe(df_r.head(10))
        st.write("**Capacitaciones (df_c):**", f"Filas: {len(df_c)}")
        st.dataframe(df_c.head(10))
        st.write("**Otros Registros (df_o):**", f"Filas: {len(df_o)}")
        st.dataframe(df_o.head(10))

    # --- 1. Resumen de Horas ---
    st.subheader("📋 Resumen de Horas Diarias")
    df_horas = generar_resumen_horas(df_r, df_c, df_o)

    if df_horas.empty:
        st.info("No se encontraron horas registradas en el período seleccionado.")
    else:
        def color_total(val):
            if val == 8.5:
                return 'background-color: #90EE90'
            else:
                return 'background-color: #FFD700'
        styled_horas = df_horas.style.map(color_total, subset=['total'])
        st.dataframe(styled_horas, use_container_width=True)

        # --- 2. Casos a revisar ---
        st.subheader("🔍 Casos a Revisar")
        fechas_range = pd.date_range(start=fecha_inicio, end=fecha_fin, freq='D')
        all_comb = pd.DataFrame([
            (nombre, fecha.date())
            for nombre in personal_asignado
            for fecha in fechas_range
        ], columns=['nombre', 'fecha'])

        df_completo = all_comb.merge(df_horas, on=['nombre', 'fecha'], how='left')
        for col in ['horas_produccion', 'horas_capacitacion', 'horas_otros', 'total']:
            if col in df_completo.columns:
                df_completo[col] = df_completo[col].fillna(0)

        df_completo['tiene_reporte'] = (
            (df_completo['horas_produccion'] > 0) | 
            (df_completo['horas_capacitacion'] > 0) | 
            (df_completo['horas_otros'] > 0)
        )

        df_casos = df_completo[df_completo['total'] != 8.5]
        if df_casos.empty:
            st.success("✅ Todos los días registran 8.5 horas exactas.")
        else:
            def determinar_caso(row):
                if not row['tiene_reporte']:
                    return "Sin Reportes"
                elif row['total'] < 8.5:
                    return f"Faltan {8.5 - row['total']:.2f} horas"
                else:
                    return f"Excedente de {row['total'] - 8.5:.2f} horas"

            df_casos['Caso'] = df_casos.apply(determinar_caso, axis=1)
            casos_vista = df_casos[['nombre', 'fecha', 'total', 'Caso']]

            def color_caso(val):
                if val == "Sin Reportes":
                    return 'color: red; font-weight: bold'
                return ''
            styled_casos = casos_vista.style.map(color_caso, subset=['Caso'])
            st.dataframe(styled_casos, use_container_width=True)

    # --- 3. Producción Diaria por Proceso (NUEVA VERSIÓN) ---
    st.subheader("📈 Producción Diaria por Proceso")
    df_prod = generar_produccion_diaria(df_r)
    if df_prod.empty:
        st.info("No hay datos de producción.")
    else:
        # Aplicar color al cumplimiento
        def color_cumplimiento(val):
            if val >= 90:
                return 'background-color: #90EE90'
            else:
                return 'background-color: #FFD700'
        styled_prod = df_prod.style.map(color_cumplimiento, subset=['cumplimiento'])
        st.dataframe(styled_prod, use_container_width=True)

    # --- 4. Gráfico de evolución del ratio ---
    if not df_r.empty:
        st.subheader("📉 Evolución del Ratio (Producción / Hora) por Persona")
        # Calcular ratio diario por persona y proceso (agrupado por persona y fecha)
        ratio_df = df_r.groupby(['nombre', 'fecha'], as_index=False).agg({
            'horas': 'sum',
            'edificas': 'sum',
            'unidades_catastrales': 'sum'
        })
        ratio_df['ratio'] = np.where(
            ratio_df['horas'] > 0,
            (ratio_df['edificas'] + ratio_df['unidades_catastrales']) / ratio_df['horas'],
            0
        )
        ratio_df['ratio'] = ratio_df['ratio'].round(2)

        # Ordenar por fecha
        ratio_df = ratio_df.sort_values(['nombre', 'fecha'])

        # Seleccionar personas para el gráfico
        personas_disponibles = sorted(ratio_df['nombre'].unique())
        personas_seleccionadas = st.multiselect(
            "Selecciona una o varias personas para ver su evolución",
            options=personas_disponibles,
            default=personas_disponibles[:3] if len(personas_disponibles) >= 3 else personas_disponibles
        )

        if personas_seleccionadas:
            df_filtrado = ratio_df[ratio_df['nombre'].isin(personas_seleccionadas)]
            if not df_filtrado.empty:
                fig = px.line(
                    df_filtrado,
                    x='fecha',
                    y='ratio',
                    color='nombre',
                    markers=True,
                    title='Evolución del Ratio (Producción / Hora)',
                    labels={'ratio': 'Ratio (Prod/Hora)', 'fecha': 'Fecha', 'nombre': 'Persona'}
                )
                # Añadir línea de referencia para ratio esperado (por ejemplo, el promedio ponderado o un valor objetivo)
                # Podemos calcular el ratio esperado promedio según las tasas de cada proceso, pero es complejo; 
                # dejamos solo la línea.
                st.plotly_chart(fig, use_container_width=True)

    # --- Actualizar ---
    st.divider()
    if st.button("🔄 Actualizar datos", type="secondary"):
        st.cache_data.clear()
        st.rerun()
