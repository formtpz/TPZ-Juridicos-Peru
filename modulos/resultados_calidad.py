# modulos/resultados_calidad.py
import streamlit as st
import pandas as pd
from db import get_engine


# ============================================================
# CARGAR DESCRIPCIÓN DE ERRORES
# ============================================================
@st.cache_data
def cargar_descripcion():
    url = (
        "https://raw.githubusercontent.com/formtpz/TPZ-Juridicos-Peru"
        "/main/Reglas/Descripcion.csv"
    )
    try:
        df = pd.read_csv(url, sep=';')
        df.columns = [c.strip().lower() for c in df.columns]
        df['error'] = df['error'].str.strip().str.upper()
        df['condicion'] = df['condicion'].str.strip().str.lower()
        df['modulo'] = df['modulo'].str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"❌ No se pudo cargar Descripcion.csv: {e}")
        return pd.DataFrame(columns=['error', 'condicion', 'modulo'])


# ============================================================
# CARGAR DATOS DESDE BD
# ============================================================
@st.cache_data(ttl=60)
def cargar_datos_calidad():
    engine = get_engine()
    query = "SELECT * FROM public.calidad_externa"
    df = pd.read_sql(query, engine)
    return df


# ============================================================
# FUNCIÓN AUXILIAR: ¿Es un valor de error real?
# ============================================================
def es_error_real(valor):
    """
    Determina si un valor cuenta como error.
    No cuenta si es: NaN, vacío, '0', '0.0', espacios, '-', 'N/A', 'NA', 'null', 'None'
    """
    if pd.isna(valor):
        return False
    valor_str = str(valor).strip()
    if valor_str == '':
        return False
    # Valores que NO son errores
    no_errores = ['0', '0.0', '-', 'N/A', 'NA', 'NULL', 'NONE', '0,0']
    if valor_str.upper() in no_errores:
        return False
    # Intentar convertir a float: si es 0.0, ignorar
    try:
        if float(valor_str.replace(',', '.')) == 0:
            return False
    except ValueError:
        pass
    # Es un error real
    return True


# ============================================================
# PROCESAR DATOS
# ============================================================
def transformar_a_errores(df_calidad, df_desc):
    """
    Convierte el DataFrame ancho a formato largo,
    usando SOLO las columnas de error listadas en Descripcion.csv
    """
    # Columnas de metadatos para mantener en el resultado
    columnas_meta = [
        'distrito', 'entregable', 'poligono', 'pol_sicun',
        'fecha_recepcion', 'fecha_resultado', 'unidad_administrativa', 'crc'
    ]
    
    # Usar SOLO los códigos del CSV como columnas de error válidas
    # El CSV tiene los códigos en MAYÚSCULAS (FI_02_01), pero la BD en minúsculas (fi_02_01)
    codigos_csv = df_desc['error'].str.lower().tolist()
    
    # De esas, solo tomar las que existen en la BD
    columnas_error = [c for c in codigos_csv if c in df_calidad.columns]
    
    # Mapa error -> (condicion, modulo)
    mapa = dict(zip(
        df_desc['error'].str.lower(),
        zip(df_desc['condicion'], df_desc['modulo'])
    ))

    registros = []
    filas_con_error = set()

    for idx, row in df_calidad.iterrows():
        fila_tiene_error = False
        for col in columnas_error:
            valor = row[col]
            if es_error_real(valor):
                fila_tiene_error = True
                codigo = col.upper()
                condicion = mapa.get(col.lower(), (None, None))[0] or 'desconocido'
                modulo = mapa.get(col.lower(), (None, None))[1] or 'desconocido'
                partes = codigo.split('_')
                codigo_principal = f"{partes[0]}_{partes[1]}" if len(partes) >= 2 else codigo

                registros.append({
                    'distrito': row.get('distrito'),
                    'entregable': row.get('entregable'),
                    'fecha_recepcion': row.get('fecha_recepcion'),
                    'fecha_resultado': row.get('fecha_resultado'),
                    'codigo_completo': codigo,
                    'codigo_principal': codigo_principal,
                    'condicion': condicion,
                    'modulo': modulo,
                })
        if fila_tiene_error:
            filas_con_error.add(idx)

    df_largo = pd.DataFrame(registros)
    
    total_registros = len(df_calidad)
    aprobados = total_registros - len(filas_con_error)
    
    return df_largo, total_registros, aprobados


# ============================================================
# INTERFAZ STREAMLIT
# ============================================================
def render():
    from permisos import validar_acceso
    validar_acceso("Depuración de Datos")

    st.title("📊 Resultados de Calidad")
    st.markdown("Visualiza y analiza los errores de calidad externa.")

    # --- Cargar datos ---
    with st.spinner("Cargando datos..."):
        df_calidad = cargar_datos_calidad()
        df_desc = cargar_descripcion()

    if df_calidad.empty:
        st.warning("⚠️ No hay datos en calidad_externa.")
        return
    if df_desc.empty:
        st.warning("⚠️ No se pudo cargar Descripcion.csv.")
        return

    # --- Transformar ---
    df_errores, total_registros_bd, total_aprobados = transformar_a_errores(df_calidad, df_desc)

    # ============================================================
    # FILTROS EN SIDEBAR
    # ============================================================
    st.sidebar.header("🔍 Filtros")

    distritos = sorted(df_errores['distrito'].dropna().unique())
    filtro_distrito = st.sidebar.multiselect("Distrito", options=distritos, default=[])

    entregables = sorted(df_errores['entregable'].dropna().unique())
    filtro_entregable = st.sidebar.multiselect("Entregable", options=entregables, default=[])

    poligonos = sorted(df_errores['poligono'].dropna().unique())
    filtro_poligono = st.sidebar.multiselect("Polígono", options=poligonos, default=[])

    st.sidebar.markdown("---")
    st.sidebar.subheader("Fecha Recepción")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        fecha_rec_inicio = st.date_input("Inicio", value=None, key="rec_ini")
    with col2:
        fecha_rec_fin = st.date_input("Fin", value=None, key="rec_fin")

    st.sidebar.subheader("Fecha Resultado")
    col3, col4 = st.sidebar.columns(2)
    with col3:
        fecha_res_inicio = st.date_input("Inicio", value=None, key="res_ini")
    with col4:
        fecha_res_fin = st.date_input("Fin", value=None, key="res_fin")

    st.sidebar.markdown("---")
    modulos = sorted(df_errores['modulo'].dropna().unique())
    filtro_modulo = st.sidebar.multiselect("Módulo", options=modulos, default=[])

    condiciones = sorted(df_errores['condicion'].dropna().unique())
    filtro_condicion = st.sidebar.multiselect("Condición", options=condiciones, default=[])

    # --- Aplicar filtros ---
    df_filtrado = df_errores.copy()

    if filtro_distrito:
        df_filtrado = df_filtrado[df_filtrado['distrito'].isin(filtro_distrito)]
    if filtro_entregable:
        df_filtrado = df_filtrado[df_filtrado['entregable'].isin(filtro_entregable)]
    if filtro_poligono: 
        df_filtrado = df_filtrado[df_filtrado['poligono'].isin(filtro_poligono)]
    if filtro_modulo:
        df_filtrado = df_filtrado[df_filtrado['modulo'].isin(filtro_modulo)]
    if filtro_condicion:
        df_filtrado = df_filtrado[df_filtrado['condicion'].isin(filtro_condicion)]

    if fecha_rec_inicio:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_recepcion'], errors='coerce') >= pd.Timestamp(fecha_rec_inicio)
        ]
    if fecha_rec_fin:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_recepcion'], errors='coerce') <= pd.Timestamp(fecha_rec_fin)
        ]
    if fecha_res_inicio:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_resultado'], errors='coerce') >= pd.Timestamp(fecha_res_inicio)
        ]
    if fecha_res_fin:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_resultado'], errors='coerce') <= pd.Timestamp(fecha_res_fin)
        ]

    # ============================================================
    # KPI'S PRINCIPALES (ARRIBA DEL TODO)
    # ============================================================
    st.subheader("📈 Indicadores Generales")

    total_graves = len(df_filtrado[df_filtrado['condicion'] == 'grave'])
    total_leves = len(df_filtrado[df_filtrado['condicion'] == 'leve'])
    total_rechazados= total_registros_bd - total_aprobados
    total_noindica = len(df_filtrado[df_filtrado['condicion'] == 'noindica'])
    total_general = len(df_filtrado)

    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

    with col1:
        st.metric("🔴 Graves", total_graves)
    with col2:
        st.metric("🟡 Leves", total_leves)
    with col3:
        st.metric("⚪ No Indica", total_noindica)
    with col4:
        st.metric("📌 Total Errores", total_general)
    with col5:
        st.metric("✅ Aprobados", total_aprobados)
    with col6:
        st.metric("🚨 Rechazados", total_rechazados)
    with col7:
        st.metric("📦 Registros BD", total_registros_bd)

    if df_filtrado.empty:
        st.info("No hay errores con los filtros seleccionados.")
        return

    # ============================================================
    # GRÁFICO DE BARRAS
    # ============================================================
    st.markdown("---")
    st.subheader("📊 Errores por Módulo y Condición")

    df_grafico = df_filtrado.groupby(['modulo', 'condicion']).size().reset_index(name='total')
    df_pivot = df_grafico.pivot(index='modulo', columns='condicion', values='total').fillna(0)

    for cond in ['leve', 'grave', 'noindica']:
        if cond not in df_pivot.columns:
            df_pivot[cond] = 0

    st.bar_chart(
        df_pivot[['leve', 'grave', 'noindica']],
        use_container_width=True,
        height=400
    )

    # ============================================================
    # TABLA RESUMEN POR CÓDIGO BASE
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Resumen por Código Base")
    st.caption("Errores agrupados por código principal (ej: FI_02, BM_01)")

    df_resumen = (
        df_filtrado.groupby(['modulo', 'codigo_principal'])
        .size()
        .reset_index(name='total')
        .sort_values(['modulo', 'codigo_principal'])
        .rename(columns={
            'modulo': 'Módulo',
            'codigo_principal': 'Código Base',
            'total': 'Total'
        })
    )

    st.dataframe(df_resumen, use_container_width=True, hide_index=True)

    # ============================================================
    # TABLA DETALLE POR CÓDIGO COMPLETO
    # ============================================================
    st.markdown("---")
    st.subheader("📋 Detalle por Error Específico")

    df_detalle = (
        df_filtrado.groupby(['modulo', 'codigo_completo', 'condicion'])
        .size()
        .reset_index(name='total')
        .sort_values(['modulo', 'codigo_completo'])
        .rename(columns={
            'modulo': 'Módulo',
            'codigo_completo': 'Código Error',
            'condicion': 'Condición',
            'total': 'Total'
        })
    )

    st.dataframe(df_detalle, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.caption("Datos de tabla pública 'calidad_externa'")
