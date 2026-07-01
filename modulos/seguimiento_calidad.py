# modulos/seguimiento_calidad.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db import fetch_df
import plotly.express as px

# Zona horaria
TZ = pytz.timezone('America/Guatemala')

# ============================================================
# FUNCIONES DE CARGA DE DATOS
# ============================================================

@st.cache_data(ttl=300)
def obtener_personal_asignado(supervisor_nombre):
    """Obtiene la lista de operadores a cargo del supervisor."""
    df = fetch_df(
        "SELECT nombre FROM usuarios WHERE supervisor = %s AND estado = 'Activo' ORDER BY nombre",
        params=[supervisor_nombre]
    )
    return df['nombre'].tolist() if not df.empty else []


@st.cache_data(ttl=60)
def cargar_datos_calidad(fechas, personal):
    """
    Carga los registros de calidad (aprobados/rechazados) y tipos de error
    para los operadores seleccionados.
    """
    fecha_inicio, fecha_fin = fechas
    if not personal:
        return pd.DataFrame()

    fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
    fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')

    query = """
        SELECT 
            NULLIF(TRIM(fecha), '')::date AS fecha,
            operador_cc AS nombre,
            proceso,
            COALESCE(aprobados::int, 0) AS aprobados,
            COALESCE(rechazados::int, 0) AS rechazados,
            tipo_de_errores
        FROM registro
        WHERE operador_cc = ANY(%s)
          AND NULLIF(TRIM(fecha), '')::date >= %s
          AND NULLIF(TRIM(fecha), '')::date <= %s
          AND operador_cc != 'N/A'
          AND tipo NOT IN ('Producción Horas Extras', 'Inspección Horas Extras', 'Reproceso Horas Extras')
    """
    df = fetch_df(query, params=[personal, fecha_inicio_str, fecha_fin_str])

    if df.empty:
        return df

    # Asegurar tipos
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce').dt.date
    df['aprobados'] = pd.to_numeric(df['aprobados'], errors='coerce').fillna(0).astype(int)
    df['rechazados'] = pd.to_numeric(df['rechazados'], errors='coerce').fillna(0).astype(int)

    # Agrupar por fecha, operador y proceso (por si hay múltiples registros el mismo día)
    # Para los tipos de error, concatenaremos los textos y luego los procesaremos por separado
    df = df.groupby(['fecha', 'nombre', 'proceso'], as_index=False).agg({
        'aprobados': 'sum',
        'rechazados': 'sum',
        'tipo_de_errores': lambda x: ', '.join(x.dropna().astype(str).str.strip().replace('', np.nan).dropna())
        # Concatenamos todos los tipos de error del día/proceso, separados por coma
    })

    # Reemplazar cadenas vacías o 'nan' por None
    df['tipo_de_errores'] = df['tipo_de_errores'].replace(['', 'nan', 'None'], np.nan)

    return df


# ============================================================
# FUNCIÓN PARA EXTRAER Y CONTAR TIPOS DE ERROR
# ============================================================

def procesar_tipo_de_error(df_calidad):
    """
    A partir del DataFrame con columna 'tipo_de_errores', genera un DataFrame
    con columnas: nombre, tipo_error, conteo
    donde cada tipo de error se separa por coma y se cuenta una vez por registro.
    """
    if df_calidad.empty or 'tipo_de_errores' not in df_calidad.columns:
        return pd.DataFrame(columns=['nombre', 'tipo_error', 'conteo'])

    # Filtrar solo registros que tengan algún error (tipo_de_errores no nulo)
    df_err = df_calidad[df_calidad['tipo_de_errores'].notna()].copy()
    if df_err.empty:
        return pd.DataFrame(columns=['nombre', 'tipo_error', 'conteo'])

    # Separar los tipos de error por coma y expandir en filas
    df_err['lista_errores'] = df_err['tipo_de_errores'].str.split(',')
    df_exploded = df_err.explode('lista_errores')

    # Limpiar espacios y eliminar vacíos
    df_exploded['tipo_error'] = df_exploded['lista_errores'].str.strip()
    df_exploded = df_exploded[df_exploded['tipo_error'] != '']

    # Contar por operador y tipo de error
    conteo = df_exploded.groupby(['nombre', 'tipo_error']).size().reset_index(name='conteo')

    return conteo


# ============================================================
# FUNCIÓN DE FORMATEO (COLORES CALIDAD)
# ============================================================

def color_calidad(val):
    """Retorna un color de fondo según el porcentaje de calidad."""
    if pd.isna(val):
        return ''
    if val >= 95:
        return 'background-color: #90EE90'   # verde
    elif val >= 85:
        return 'background-color: #FFD700'   # amarillo
    else:
        return 'background-color: #FF6B6B; color: white'  # rojo


# ============================================================
# RENDER PRINCIPAL
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

    st.title("📋 Control de Calidad")
    st.markdown(f"**Supervisor:** {nombre_supervisor} | **Personal a cargo:** {len(personal_asignado)}")

    # --- Filtro de fechas ---
    hoy = datetime.now(TZ).date()
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha de inicio", value=hoy - timedelta(days=7), key="cc_fecha_ini")
    with col2:
        fecha_fin = st.date_input("Fecha de fin", value=hoy, key="cc_fecha_fin")

    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
        return

    # --- Filtro de operadores ---
    st.markdown("### 👥 Seleccionar Operadores")
    personal_filtrado = st.multiselect(
        "Operadores a revisar",
        options=personal_asignado,
        default=personal_asignado,
        key="cc_filtro_operador"
    )

    if not personal_filtrado:
        st.warning("Debe seleccionar al menos un operador.")
        return

    # --- Cargar datos ---
    with st.spinner("Cargando datos de calidad..."):
        df_calidad = cargar_datos_calidad((fecha_inicio, fecha_fin), personal_filtrado)

    if df_calidad.empty:
        st.info("No se encontraron registros de calidad en el período seleccionado.")
        return

    # --- Calcular porcentaje de calidad ---
    df_calidad['total'] = df_calidad['aprobados'] + df_calidad['rechazados']
    df_calidad['calidad'] = np.where(
        df_calidad['total'] > 0,
        (df_calidad['aprobados'] / df_calidad['total']) * 100,
        0
    )
    df_calidad['calidad'] = df_calidad['calidad'].round(1)

    # --- Vista por proceso ---
    df_vista = df_calidad[['fecha', 'nombre', 'proceso', 'aprobados', 'rechazados', 'calidad']].copy()
    df_vista = df_vista.sort_values(['fecha', 'nombre', 'proceso']).reset_index(drop=True)
    df_vista.rename(columns={
        'fecha': 'Fecha',
        'nombre': 'Operador',
        'proceso': 'Proceso',
        'aprobados': 'Aprobados',
        'rechazados': 'Rechazados',
        'calidad': 'Calidad (%)'
    }, inplace=True)

    styled = df_vista.style.map(color_calidad, subset=['Calidad (%)'])
    st.subheader("📊 Calidad por Operador y Proceso")
    st.dataframe(styled, use_container_width=True)

    # --- Resumen por Operador y Proceso (total del período) ---
    st.subheader("📋 Resumen por Operador y Proceso (total del período)")
    resumen = df_calidad.groupby(['nombre', 'proceso'], as_index=False).agg({
        'aprobados': 'sum',
        'rechazados': 'sum'
    })
    resumen['total'] = resumen['aprobados'] + resumen['rechazados']
    resumen['calidad'] = np.where(
        resumen['total'] > 0,
        (resumen['aprobados'] / resumen['total']) * 100,
        0
    )
    resumen['calidad'] = resumen['calidad'].round(1)
    resumen.rename(columns={
        'nombre': 'Operador',
        'proceso': 'Proceso',
        'aprobados': 'Aprobados',
        'rechazados': 'Rechazados',
        'calidad': 'Calidad (%)'
    }, inplace=True)
    resumen_vista = resumen[['Operador', 'Proceso', 'Aprobados', 'Rechazados', 'Calidad (%)']]
    styled_resumen = resumen_vista.style.map(color_calidad, subset=['Calidad (%)'])
    st.dataframe(styled_resumen, use_container_width=True)

    # --- GRÁFICO DE TIPOS DE ERROR POR OPERADOR ---
    st.subheader("📊 Tipos de Errores por Operador")
    df_errores = procesar_tipo_de_error(df_calidad)

    if df_errores.empty:
        st.info("No se encontraron registros de tipos de error en el período seleccionado.")
    else:
        # --- Gráfico de barras simple: porcentaje de cada tipo de error ---
        errores_totales = df_errores.groupby('tipo_error')['conteo'].sum().reset_index()
        total_errores = errores_totales['conteo'].sum()
        errores_totales['porcentaje'] = (
            (errores_totales['conteo'] / total_errores * 100) if total_errores > 0 else 0
        ).round(1)
        errores_totales = errores_totales.sort_values('porcentaje', ascending=False)

        fig_pareto = px.bar(
            errores_totales,
            x='tipo_error',
            y='porcentaje',
            title='Porcentaje de cada tipo de error (todos los operadores)',
            labels={'tipo_error': 'Tipo de Error', 'porcentaje': 'Porcentaje (%)'},
            color='porcentaje',
            color_continuous_scale='Reds',
            text='porcentaje'   # muestra el porcentaje sobre la barra
        )
        fig_pareto.update_traces(
            texttemplate='%{text:.1f}%',
            textposition='outside'
        )
        fig_pareto.update_layout(
            xaxis_tickangle=-45,
            showlegend=False,
            yaxis_ticksuffix='%'
        )
        st.plotly_chart(fig_pareto, use_container_width=True)

        # --- Gráfico de barras apiladas por operador ---
        fig = px.bar(
            df_errores,
            x='nombre',
            y='conteo',
            color='tipo_error',
            title='Distribución de tipos de error por operador',
            labels={'nombre': 'Operador', 'conteo': 'Cantidad de errores', 'tipo_error': 'Tipo de Error'},
            barmode='stack'
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # También podemos mostrar una tabla con el detalle
        with st.expander("📋 Ver tabla de errores"):
            pivot = df_errores.pivot_table(
                index='nombre',
                columns='tipo_error',
                values='conteo',
                fill_value=0
            ).astype(int)
            st.dataframe(pivot)

    # --- Botón de actualización ---
    st.divider()
    if st.button("🔄 Actualizar datos", type="secondary"):
        st.cache_data.clear()
        st.rerun()
