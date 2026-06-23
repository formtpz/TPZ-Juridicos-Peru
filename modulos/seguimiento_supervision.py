# modulos/supervisor_resumen.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from db import fetch_df

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

@st.cache_data(ttl=300)  # 5 minutos
def obtener_personal_asignado(supervisor_nombre):
    """Devuelve lista de nombres de usuarios cuyo supervisor es el dado."""
    df = fetch_df(
        "SELECT nombre FROM usuarios WHERE supervisor = %s AND estado = 'Activo' ORDER BY nombre",
        params=[supervisor_nombre]
    )
    return df['nombre'].tolist() if not df.empty else []


@st.cache_data(ttl=60)
def cargar_datos_personal(fechas, personal):
    """
    Carga datos de registro, capacitaciones y otros_registros para el personal
    en el rango de fechas, excluyendo horas extras y reposiciones.
    """
    fecha_inicio, fecha_fin = fechas
    if not personal:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # --- Registro (producción normal, sin horas extras) ---
    query_r = """
        SELECT 
            nombre, fecha, proceso, tipo,
            COALESCE(edificas::float, 0) AS edificas,
            COALESCE(unidades_catastrales::float, 0) AS unidades_catastrales,
            COALESCE(horas::float, 0) AS horas
        FROM registro
        WHERE nombre = ANY(%s)
          AND fecha::date >= %s AND fecha::date <= %s
          AND tipo NOT IN ('Producción Horas Extras', 'Inspección Horas Extras', 'Reproceso Horas Extras')
    """
    df_r = fetch_df(query_r, params=[personal, fecha_inicio, fecha_fin])

    # --- Capacitaciones ---
    query_c = """
        SELECT nombre, fecha, COALESCE(horas::float, 0) AS horas
        FROM capacitaciones
        WHERE nombre = ANY(%s)
          AND fecha::date >= %s AND fecha::date <= %s
    """
    df_c = fetch_df(query_c, params=[personal, fecha_inicio, fecha_fin])

    # --- Otros registros (excluyendo horas extra y reposición) ---
    query_o = """
        SELECT nombre, fecha, COALESCE(horas::float, 0) AS horas
        FROM otros_registros
        WHERE nombre = ANY(%s)
          AND fecha::date >= %s AND fecha::date <= %s
          AND motivo NOT IN ('Horas Extra', 'Horas Extra Apoyo Otros Proyectos', 'Horas Extras', 'Reposición de tiempo')
    """
    df_o = fetch_df(query_o, params=[personal, fecha_inicio, fecha_fin])

    return df_r, df_c, df_o


# ============================================================
# FUNCIONES DE PROCESAMIENTO
# ============================================================

def generar_resumen_horas(df_r, df_c, df_o):
    """
    Genera tabla con horas diarias por persona:
    horas_produccion, horas_capacitacion, horas_otros, total
    """
    # Producción: agrupar por nombre, fecha sumando horas
    if not df_r.empty:
        prod = df_r.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_produccion'})
    else:
        prod = pd.DataFrame(columns=['nombre', 'fecha', 'horas_produccion'])

    # Capacitación
    if not df_c.empty:
        cap = df_c.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_capacitacion'})
    else:
        cap = pd.DataFrame(columns=['nombre', 'fecha', 'horas_capacitacion'])

    # Otros
    if not df_o.empty:
        otros = df_o.groupby(['nombre', 'fecha'], as_index=False)['horas'].sum().rename(columns={'horas': 'horas_otros'})
    else:
        otros = pd.DataFrame(columns=['nombre', 'fecha', 'horas_otros'])

    # Combinar
    combined = pd.concat([prod, cap, otros], axis=0, ignore_index=True)
    if combined.empty:
        return pd.DataFrame()

    # Obtener todas las combinaciones nombre-fecha
    keys = combined[['nombre', 'fecha']].drop_duplicates()
    merged = keys.merge(prod, on=['nombre', 'fecha'], how='left')
    merged = merged.merge(cap, on=['nombre', 'fecha'], how='left')
    merged = merged.merge(otros, on=['nombre', 'fecha'], how='left')
    merged = merged.fillna(0)

    # Calcular total
    merged['total'] = merged['horas_produccion'] + merged['horas_capacitacion'] + merged['horas_otros']

    # Redondear a 2 decimales
    for col in ['horas_produccion', 'horas_capacitacion', 'horas_otros', 'total']:
        merged[col] = merged[col].round(2)

    return merged


def generar_produccion_diaria(df_r):
    """
    Genera tabla de producción diaria por persona y proceso:
    fecha, nombre, proceso, horas, edificas, unidades_catastrales,
    ratio, valor_esperado, diferencia
    """
    if df_r.empty:
        return pd.DataFrame()

    # Agrupar por nombre, fecha, proceso
    grouped = df_r.groupby(['nombre', 'fecha', 'proceso'], as_index=False).agg({
        'horas': 'sum',
        'edificas': 'sum',
        'unidades_catastrales': 'sum'
    })

    # Calcular ratio = (edificas + unidades) / horas (si horas > 0)
    grouped['ratio'] = np.where(
        grouped['horas'] > 0,
        (grouped['edificas'] + grouped['unidades_catastrales']) / grouped['horas'],
        0
    )
    grouped['ratio'] = grouped['ratio'].round(2)

    # Calcular valor esperado según tasa por hora
    grouped['tasa'] = grouped['proceso'].map(TASAS_POR_HORA).fillna(0)
    grouped['valor_esperado'] = grouped['tasa'] * grouped['horas']
    grouped['diferencia'] = (grouped['edificas'] + grouped['unidades_catastrales']) - grouped['valor_esperado']
    grouped['diferencia'] = grouped['diferencia'].round(2)

    # Ordenar
    grouped = grouped.sort_values(['fecha', 'nombre', 'proceso']).reset_index(drop=True)

    return grouped


# ============================================================
# FUNCIONES DE VISUALIZACIÓN (con estilo)
# ============================================================

def apply_color_to_total(df):
    """
    Aplica estilo a la columna 'total': verde si == 8.5, amarillo si no.
    Devuelve un DataFrame con columna 'estado' (opcional) o usa st.dataframe con styled.
    """
    def color_total(val):
        if val == 8.5:
            return 'background-color: #90EE90'  # verde claro
        else:
            return 'background-color: #FFD700'  # amarillo
    return df.style.applymap(color_total, subset=['total'])


# ============================================================
# FUNCIÓN PRINCIPAL RENDER
# ============================================================

def render():
    # Verificar que el usuario esté logueado y tenga rol de supervisor
    usuario = st.session_state.get("usuario")
    if not usuario:
        st.warning("Debe iniciar sesión")
        st.stop()

    nombre_supervisor = usuario.get("nombre")
    puesto = usuario.get("puesto", "")

    # Verificar que sea supervisor o coordinador (o que tenga personal a cargo)
    # Por simplicidad, asumimos que si tiene personal asignado, se le muestra el módulo.
    # Si no, mostramos mensaje.
    personal_asignado = obtener_personal_asignado(nombre_supervisor)
    if not personal_asignado:
        st.warning("No tiene personal a cargo para supervisar.")
        return

    st.title("📊 Resumen de Supervisor")
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

    # --- Cargar datos ---
    with st.spinner("Cargando datos..."):
        df_r, df_c, df_o = cargar_datos_personal((fecha_inicio, fecha_fin), personal_asignado)

    if df_r.empty and df_c.empty and df_o.empty:
        st.info("No hay datos para el período seleccionado.")
        return

    # --- 1. Resumen de Horas ---
    st.subheader("📋 Resumen de Horas Diarias")
    df_horas = generar_resumen_horas(df_r, df_c, df_o)
    if df_horas.empty:
        st.info("No se encontraron horas registradas.")
    else:
        # Aplicar estilo
        styled_horas = df_horas.style.applymap(
            lambda x: 'background-color: #90EE90' if x == 8.5 else ('background-color: #FFD700' if x != 8.5 else ''),
            subset=['total']
        )
        st.dataframe(styled_horas, use_container_width=True)

        # --- Tabla "Casos a revisar" ---
        st.subheader("🔍 Casos a revisar (horas diferentes a 8.5)")
        casos = df_horas[df_horas['total'] != 8.5].copy()
        if casos.empty:
            st.success("✅ Todos los días registran 8.5 horas exactas.")
        else:
            casos['Caso'] = casos['total'].apply(
                lambda x: f"Faltan {8.5 - x:.2f} horas" if x < 8.5 else f"Excedente de {x - 8.5:.2f} horas"
            )
            casos_vista = casos[['nombre', 'fecha', 'total', 'Caso']]
            st.dataframe(casos_vista, use_container_width=True)

    # --- 2. Producción Diaria por Proceso ---
    st.subheader("📈 Producción Diaria por Proceso")
    df_prod = generar_produccion_diaria(df_r)
    if df_prod.empty:
        st.info("No hay datos de producción.")
    else:
        # Mostrar tabla completa
        st.dataframe(df_prod, use_container_width=True)

        # --- Tabla de bajo rendimiento (diferencia negativa) ---
        st.subheader("⚠️ Personal con Bajo Rendimiento")
        bajo_rendimiento = df_prod[df_prod['diferencia'] < 0].copy()
        if bajo_rendimiento.empty:
            st.success("✅ Todo el personal cumple o supera las metas esperadas.")
        else:
            bajo_rendimiento['Faltante'] = bajo_rendimiento['diferencia'].abs().apply(lambda x: f"{x:.2f} unidades")
            bajo_vista = bajo_rendimiento[['fecha', 'nombre', 'proceso', 'diferencia', 'Faltante']]
            st.dataframe(bajo_vista, use_container_width=True)

    # --- Opcional: Exportar ---
    st.divider()
    if st.button("🔄 Actualizar datos", type="secondary"):
        st.cache_data.clear()
        st.rerun()
