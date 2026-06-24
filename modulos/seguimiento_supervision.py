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
    if df_r.empty:
        return pd.DataFrame()

    grouped = df_r.groupby(['nombre', 'fecha', 'proceso'], as_index=False).agg({
        'horas': 'sum',
        'edificas': 'sum',
        'unidades_catastrales': 'sum'
    })

    grouped['produccion'] = grouped['edificas'] + grouped['unidades_catastrales']
    grouped['ratio'] = np.where(
        grouped['horas'] > 0,
        grouped['produccion'] / grouped['horas'],
        0
    )
    grouped['ratio'] = grouped['ratio'].round(2)

    grouped['tasa'] = grouped['proceso'].map(TASAS_POR_HORA).fillna(0)
    grouped['valor_esperado'] = grouped['tasa'] * grouped['horas']
    grouped['valor_esperado'] = grouped['valor_esperado'].round(2)

    grouped['cumplimiento'] = np.where(
        grouped['valor_esperado'] > 0,
        (grouped['produccion'] / grouped['valor_esperado']) * 100,
        0
    )
    grouped['cumplimiento'] = grouped['cumplimiento'].round(1)

    grouped = grouped.sort_values(['fecha', 'nombre', 'proceso']).reset_index(drop=True)
    columnas_finales = ['nombre', 'fecha', 'proceso', 'horas', 'produccion', 'valor_esperado', 'cumplimiento', 'ratio']
    return grouped[columnas_finales]


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

    # --- Filtro de fechas ---
    hoy = datetime.now(TZ).date()
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha de inicio", value=hoy - timedelta(days=7), key="sup_fecha_ini")
    with col2:
        fecha_fin = st.date_input("Fecha de fin", value=hoy, key="sup_fecha_fin")

    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
        return

    # --- FILTRO POR OPERADOR (multiselect con todas seleccionadas por defecto) ---
    st.markdown("### 👥 Filtrar por Operador")
    personal_filtrado = st.multiselect(
        "Selecciona uno o varios operadores",
        options=personal_asignado,
        default=personal_asignado,  # Todas seleccionadas por defecto
        key="filtro_operador"
    )

    if not personal_filtrado:
        st.warning("Debe seleccionar al menos un operador.")
        return

    st.info(f"Mostrando datos para {len(personal_filtrado)} operador(es) de {len(personal_asignado)} totales.")

    # --- Cargar datos (solo para los operadores seleccionados) ---
    with st.spinner("Cargando datos..."):
        df_r, df_c, df_o = cargar_datos_personal((fecha_inicio, fecha_fin), personal_filtrado)

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
            return 'background-color: #90EE90' if val == 8.5 else 'background-color: #FFD700'
        styled_horas = df_horas.style.map(color_total, subset=['total'])
        st.dataframe(styled_horas, use_container_width=True)

        # --- Casos a revisar (usando personal_filtrado) ---
        st.subheader("🔍 Casos a Revisar")
        fechas_range = pd.date_range(start=fecha_inicio, end=fecha_fin, freq='D')
        all_comb = pd.DataFrame([
            (nombre, fecha.date())
            for nombre in personal_filtrado  # <--- Usamos la lista filtrada
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
                return 'color: red; font-weight: bold' if val == "Sin Reportes" else ''
            styled_casos = casos_vista.style.map(color_caso, subset=['Caso'])
            st.dataframe(styled_casos, use_container_width=True)

    # --- 2. Producción Diaria por Proceso ---
    st.subheader("📈 Producción Diaria por Proceso")
    df_prod = generar_produccion_diaria(df_r)
    if df_prod.empty:
        st.info("No hay datos de producción.")
    else:
        # Aplicar estilo al cumplimiento
        def color_cumplimiento(val):
            if val >= 90:
                return 'background-color: #90EE90'  # verde
            else:
                return 'background-color: #FFD700'  # amarillo

        styled_prod = df_prod.style.map(color_cumplimiento, subset=['cumplimiento'])
        st.dataframe(styled_prod, use_container_width=True)

        # --- Gráfico de evolución del ratio por persona ---
        st.subheader("📈 Evolución del Ratio por Persona (producción / horas)")

        # Calcular ratio agregado por fecha y persona (sin proceso)
        df_ratio_agg = df_r.groupby(['fecha', 'nombre'], as_index=False).agg({
            'edificas': 'sum',
            'unidades_catastrales': 'sum',
            'horas': 'sum'
        })
        df_ratio_agg['produccion'] = df_ratio_agg['edificas'] + df_ratio_agg['unidades_catastrales']
        df_ratio_agg['ratio'] = np.where(
            df_ratio_agg['horas'] > 0,
            df_ratio_agg['produccion'] / df_ratio_agg['horas'],
            0
        )
        df_ratio_agg['ratio'] = df_ratio_agg['ratio'].round(2)

        if not df_ratio_agg.empty:
            fig = px.line(
                df_ratio_agg,
                x='fecha',
                y='ratio',
                color='nombre',
                title='Evolución del Ratio (Producción/Horas) por Persona',
                labels={'fecha': 'Fecha', 'ratio': 'Ratio (producción/hora)', 'nombre': 'Persona'},
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay suficientes datos para generar el gráfico de ratios.")

    # --- Actualizar ---
    st.divider()
    if st.button("🔄 Actualizar datos", type="secondary"):
        st.cache_data.clear()
        st.rerun()
