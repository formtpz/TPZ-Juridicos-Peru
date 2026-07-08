# modulos/seguimiento_extras.py
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
    'Control de Calidad Vinculación Precampo': 10,
    'Masivos QC Vinculación': 15,
    'Masivos QC Postcampo': 15
}

# ============================================================
# FUNCIONES DE CARGA DE DATOS
# ============================================================

@st.cache_data(ttl=300)
def obtener_todo_personal():
    """
    Trae a TODO el personal activo, sin filtrar por supervisor ni por puesto.
    Incluye operadores, supervisores, coordinadores, etc. — cualquiera que
    pueda reportar horas extra.
    """
    df = fetch_df(
        "SELECT nombre FROM usuarios WHERE estado = 'Activo' ORDER BY nombre"
    )
    return df['nombre'].tolist() if not df.empty else []


@st.cache_data(ttl=60)
def cargar_datos_extras(fechas, personal):
    """
    Carga datos de horas extra desde 'registro' (tipo LIKE '%Horas Extra%')
    y desde 'otros_registros' (motivo LIKE '%Extra%').
    Retorna dos DataFrames: df_r (registro) y df_o (otros_registros).
    """
    fecha_inicio, fecha_fin = fechas
    if not personal:
        return pd.DataFrame(), pd.DataFrame()

    fecha_inicio_str = fecha_inicio.strftime('%Y-%m-%d')
    fecha_fin_str = fecha_fin.strftime('%Y-%m-%d')

    # --- Registro (horas extra de producción/inspección) ---
    # NOTA: el patrón LIKE va como parámetro (%s), no escrito literal en el SQL,
    # para que psycopg2 no confunda el '%' del comodín con un placeholder.
    query_r = """
        SELECT 
            nombre, 
            NULLIF(TRIM(fecha), '')::date as fecha,
            proceso,
            COALESCE(edificas::float, 0) AS edificas,
            COALESCE(unidades_catastrales::float, 0) AS unidades_catastrales,
            COALESCE(horas::float, 0) AS horas
        FROM registro
        WHERE nombre = ANY(%s)
          AND NULLIF(TRIM(fecha), '')::date >= %s 
          AND NULLIF(TRIM(fecha), '')::date <= %s
          AND tipo LIKE %s
    """
    try:
        df_r = fetch_df(
            query_r,
            params=[personal, fecha_inicio_str, fecha_fin_str, '%Horas Extra%']
        )
    except Exception as e:
        st.error(f"Error al consultar registros de horas extra: {e}")
        return pd.DataFrame(), pd.DataFrame()

    # --- Otros registros (motivos extra) ---
    query_o = """
        SELECT 
            nombre, 
            NULLIF(TRIM(fecha), '')::date as fecha,
            COALESCE(horas::float, 0) AS horas
        FROM otros_registros
        WHERE nombre = ANY(%s)
          AND NULLIF(TRIM(fecha), '')::date >= %s 
          AND NULLIF(TRIM(fecha), '')::date <= %s
          AND motivo LIKE %s
    """
    try:
        df_o = fetch_df(
            query_o,
            params=[personal, fecha_inicio_str, fecha_fin_str, '%Extra%']
        )
    except Exception as e:
        st.error(f"Error al consultar otros registros extra: {e}")
        return df_r, pd.DataFrame()

    # Asegurar tipos de fecha
    for df in [df_r, df_o]:
        if not df.empty:
            df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce').dt.date

    return df_r, df_o


# ============================================================
# FUNCIONES DE PROCESAMIENTO
# ============================================================

def generar_resumen_horas_extras(df_r, df_o):
    """Resumen diario de horas extra con columnas separadas."""
    # Horas extra producción
    if not df_r.empty:
        prod = df_r.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum()
        prod.rename(columns={'horas': 'horas_extra_produccion'}, inplace=True)
    else:
        prod = pd.DataFrame(columns=['nombre', 'fecha', 'horas_extra_produccion'])

    # Horas extra otros
    if not df_o.empty:
        otros = df_o.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum()
        otros.rename(columns={'horas': 'horas_extra_otros'}, inplace=True)
    else:
        otros = pd.DataFrame(columns=['nombre', 'fecha', 'horas_extra_otros'])

    # Combinar todas las combinaciones nombre-fecha
    keys = pd.concat([prod[['nombre', 'fecha']], otros[['nombre', 'fecha']]], axis=0)
    if keys.empty:
        return pd.DataFrame(columns=['nombre', 'fecha', 'horas_extra_produccion', 'horas_extra_otros'])

    keys = keys.drop_duplicates().reset_index(drop=True)
    merged = keys.merge(prod, on=['nombre', 'fecha'], how='left')
    merged = merged.merge(otros, on=['nombre', 'fecha'], how='left')
    merged = merged.fillna(0)

    for col in ['horas_extra_produccion', 'horas_extra_otros']:
        merged[col] = merged[col].round(2)

    return merged


def generar_balance_extras(df_r, df_o):
    """
    Balance de horas extra por operador.
    'diferencia' = horas_extra_otros - horas_extra_produccion.
    No se suman ambas columnas porque suelen representar el MISMO evento
    reportado dos veces: una por el supervisor (otros_registros) y otra
    por el propio operador en producción (registro). La diferencia sirve
    para detectar descuadres entre ambos reportes (debería tender a 0
    cuando coinciden perfectamente).
    """
    if df_r.empty and df_o.empty:
        return pd.DataFrame(columns=['nombre', 'horas_extra_produccion', 'horas_extra_otros', 'diferencia'])

    bal_prod = pd.DataFrame(columns=['nombre', 'horas_extra_produccion'])
    bal_otros = pd.DataFrame(columns=['nombre', 'horas_extra_otros'])

    if not df_r.empty:
        bal_prod = df_r.groupby('nombre', as_index=False)['horas'].sum()
        bal_prod.rename(columns={'horas': 'horas_extra_produccion'}, inplace=True)

    if not df_o.empty:
        bal_otros = df_o.groupby('nombre', as_index=False)['horas'].sum()
        bal_otros.rename(columns={'horas': 'horas_extra_otros'}, inplace=True)

    balance = pd.merge(bal_prod, bal_otros, on='nombre', how='outer').fillna(0)
    balance['diferencia'] = balance['horas_extra_otros'] - balance['horas_extra_produccion']
    for col in ['horas_extra_produccion', 'horas_extra_otros', 'diferencia']:
        balance[col] = balance[col].round(2)

    return balance[['nombre', 'horas_extra_produccion', 'horas_extra_otros', 'diferencia']]


def generar_produccion_diaria_extras(df_r):
    """Producción, ratio y cumplimiento solo para horas extra (registro)."""
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
# RENDER PRINCIPAL
# ============================================================

def render():
    usuario = st.session_state.get("usuario")
    if not usuario:
        st.warning("Debe iniciar sesión")
        st.stop()

    nombre_usuario = usuario.get("nombre")
    personal_asignado = obtener_todo_personal()

    if not personal_asignado:
        st.warning("No se encontró personal activo en el sistema.")
        return

    st.title("⏱️ Seguimiento de Horas Extra (Administrador)")
    st.markdown(f"**Usuario:** {nombre_usuario} | **Personal activo total:** {len(personal_asignado)}")
    st.caption("Vista sin restricción de supervisor: incluye operadores, supervisores y coordinadores.")

    # --- Filtro de fechas ---
    hoy = datetime.now(TZ).date()
    col1, col2 = st.columns(2)
    with col1:
        fecha_inicio = st.date_input("Fecha de inicio", value=hoy - timedelta(days=7), key="ext_adm_fecha_ini")
    with col2:
        fecha_fin = st.date_input("Fecha de fin", value=hoy, key="ext_adm_fecha_fin")

    if fecha_inicio > fecha_fin:
        st.error("La fecha de inicio no puede ser mayor a la fecha fin.")
        return

    # --- Filtro por operador ---
    st.markdown("### 👥 Filtrar por Operador")
    personal_filtrado = st.multiselect(
        "Selecciona uno o varios operadores",
        options=personal_asignado,
        default=personal_asignado,
        key="ext_adm_filtro_operador"
    )

    if not personal_filtrado:
        st.warning("Debe seleccionar al menos un operador.")
        return

    st.info(f"Mostrando datos para {len(personal_filtrado)} operador(es) de {len(personal_asignado)} totales.")

    # --- Cargar datos ---
    with st.spinner("Cargando horas extra..."):
        df_r, df_o = cargar_datos_extras((fecha_inicio, fecha_fin), personal_filtrado)

    # Si ambos DataFrames están vacíos (sin datos en el período)
    if df_r.empty and df_o.empty:
        st.info("No se encontraron horas extra en el período seleccionado.")
        return

    # --- Depuración opcional ---
    with st.expander("🔍 Depuración (datos cargados)"):
        st.write("**Registro horas extra (df_r):**", f"Filas: {len(df_r)}")
        st.dataframe(df_r.head(10) if not df_r.empty else pd.DataFrame())
        st.write("**Otros registros extra (df_o):**", f"Filas: {len(df_o)}")
        st.dataframe(df_o.head(10) if not df_o.empty else pd.DataFrame())

    # --- 1. Resumen de Horas Diarias (horas extra) ---
    st.subheader("📋 Resumen de Horas Extra Diarias")
    df_horas = generar_resumen_horas_extras(df_r, df_o)
    if df_horas.empty:
        st.info("No se encontraron horas extra registradas en el período seleccionado.")
    else:
        st.dataframe(df_horas, width='stretch')

    # --- Balance de Horas Extra por Operador ---
    st.subheader("⚖️ Diferencia de Horas Extra por Operador")
    st.caption(
        "Diferencia = Horas Extra (Otros Registros, reportadas por el supervisor) − "
        "Horas Extra (Producción, reportadas por el operador). "
        "Sirve para detectar reportes duplicados o descuadrados entre ambas fuentes; "
        "en teoría debería tender a 0 cuando ambos reportes coinciden."
    )
    df_balance = generar_balance_extras(df_r, df_o)
    if df_balance.empty:
        st.info("No hay horas extra para calcular la diferencia.")
    else:
        def color_diferencia(val):
            if val == 0:
                return 'background-color: #90EE90'  # verde: cuadran ambos reportes
            else:
                return 'background-color: #FF6B6B; color: white'  # rojo: hay descuadre
        styled_balance = df_balance.style.map(color_diferencia, subset=['diferencia'])
        st.dataframe(styled_balance, width='stretch')

    # --- 2. Producción Diaria por Proceso (solo horas extra) ---
    st.subheader("📈 Producción Diaria por Proceso (Horas Extra)")
    df_prod = generar_produccion_diaria_extras(df_r)
    if df_prod.empty:
        st.info("No hay datos de producción en horas extra.")
    else:
        def color_cumplimiento(val):
            if val >= 90:
                return 'background-color: #90EE90'
            else:
                return 'background-color: #FFD700'

        styled_prod = df_prod.style.map(color_cumplimiento, subset=['cumplimiento'])
        st.dataframe(styled_prod, width='stretch')

        # --- Gráfico de evolución del ratio (solo horas extra) ---
        st.subheader("📈 Evolución del Ratio por Persona (Horas Extra)")
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
                title='Evolución del Ratio (Producción/Horas) – Horas Extra',
                labels={'fecha': 'Fecha', 'ratio': 'Ratio (producción/hora)', 'nombre': 'Persona'},
                markers=True
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No hay suficientes datos para generar el gráfico de ratios.")

    # --- Actualizar ---
    st.divider()
    if st.button("🔄 Actualizar datos", type="secondary"):
        st.cache_data.clear()
        st.rerun()
