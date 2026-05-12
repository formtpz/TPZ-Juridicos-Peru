import streamlit as st
import pandas as pd
from db import get_connection


# ============================================================
# CARGAR DESCRIPCIÓN DE ERRORES (DESDE CSV EN REPO)
# ============================================================
@st.cache_data
def cargar_descripcion():
    """
    Carga el archivo Descripcion.csv desde el repositorio GitHub.
    Columnas: error, condicion, modulo
    """
    url = (
        "https://raw.githubusercontent.com/formtpz/TPZ-Juridicos-Peru"
        "/main/Reglas/Descripcion.csv"
    )
    try:
        df = pd.read_csv(url, sep=';')
        # Normalizar nombres de columnas
        df.columns = [c.strip().lower() for c in df.columns]
        # Normalizar valores
        df['error'] = df['error'].str.strip().str.upper()
        df['condicion'] = df['condicion'].str.strip().str.lower()
        df['modulo'] = df['modulo'].str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"❌ No se pudo cargar Descripcion.csv: {e}")
        return pd.DataFrame(columns=['error', 'condicion', 'modulo'])


# ============================================================
# CONSULTAR DATOS DESDE LA BD
# ============================================================
@st.cache_data(ttl=60)
def cargar_datos_calidad():
    """
    Consulta todos los registros de public.calidad_externa.
    """
    conn = get_connection()
    query = "SELECT * FROM public.calidad_externa"
    df = pd.read_sql(query, conn)
    conn.close()
    return df


# ============================================================
# PROCESAR DATOS: TRANSFORMAR A FORMATO LARGO (FILA POR ERROR)
# ============================================================
def transformar_a_errores(df_calidad, df_desc):
    """
    Convierte el DataFrame ancho (una columna por código de error)
    a un formato largo con columnas: [codigo_completo, valor, condicion, modulo, codigo_principal].
    Solo filas donde el valor NO sea nulo/vacío.
    """
    # Columnas de error en la BD (excluyendo metadatos)
    columnas_meta = [
        'distrito', 'entregable', 'poligono', 'pol_sicun',
        'fecha_recepcion', 'fecha_resultado', 'unidad_administrativa', 'crc'
    ]
    columnas_error = [c for c in df_calidad.columns if c not in columnas_meta]

    # Diccionario error -> (condicion, modulo)
    mapa = dict(zip(
        df_desc['error'].str.lower(),
        zip(df_desc['condicion'], df_desc['modulo'])
    ))

    registros = []
    for _, row in df_calidad.iterrows():
        for col in columnas_error:
            valor = row[col]
            if pd.notna(valor) and str(valor).strip() != '':
                codigo = col.upper()
                condicion = mapa.get(col.lower(), (None, None))[0] or 'desconocido'
                modulo = mapa.get(col.lower(), (None, None))[1] or 'desconocido'
                # Código principal: tomar los dos primeros bloques (ej: FI_02_01 → FI_02)
                partes = codigo.split('_')
                if len(partes) >= 2:
                    codigo_principal = f"{partes[0]}_{partes[1]}"
                else:
                    codigo_principal = codigo

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

    df_largo = pd.DataFrame(registros)
    return df_largo


# ============================================================
# INTERFAZ DE STREAMLIT
# ============================================================
def render():
    # Verificar acceso
    from permisos import validar_acceso
    validar_acceso("Depuración de Datos")

    st.title("📊 Resultados de Calidad")
    st.markdown("""
    Visualiza y analiza los errores de calidad externa.
    Filtra por distrito, entregable, fechas, módulo o condición.
    """)

    # --- Cargar datos ---
    with st.spinner("Cargando datos desde la base de datos..."):
        df_calidad = cargar_datos_calidad()
        df_desc = cargar_descripcion()

    if df_calidad.empty:
        st.warning("⚠️ No hay datos en la tabla calidad_externa.")
        return

    if df_desc.empty:
        st.warning("⚠️ No se pudo cargar la descripción de errores.")
        return

    # --- Transformar a formato largo ---
    df_errores = transformar_a_errores(df_calidad, df_desc)

    if df_errores.empty:
        st.info("No se encontraron errores registrados.")
        return

    # ============================================================
    # FILTROS
    # ============================================================
    st.sidebar.header("🔍 Filtros")

    # Filtro Distrito
    distritos = sorted(df_errores['distrito'].dropna().unique())
    filtro_distrito = st.sidebar.multiselect(
        "Distrito", options=distritos, default=[]
    )

    # Filtro Entregable
    entregables = sorted(df_errores['entregable'].dropna().unique())
    filtro_entregable = st.sidebar.multiselect(
        "Entregable", options=entregables, default=[]
    )

    # Filtro Fecha Recepción
    st.sidebar.markdown("---")
    st.sidebar.subheader("Fecha Recepción")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        fecha_rec_inicio = st.date_input("Inicio", value=None, key="fecha_rec_ini")
    with col2:
        fecha_rec_fin = st.date_input("Fin", value=None, key="fecha_rec_fin")

    # Filtro Fecha Resultado
    st.sidebar.subheader("Fecha Resultado")
    col3, col4 = st.sidebar.columns(2)
    with col3:
        fecha_res_inicio = st.date_input("Inicio", value=None, key="fecha_res_ini")
    with col4:
        fecha_res_fin = st.date_input("Fin", value=None, key="fecha_res_fin")

    # Filtro Módulo
    st.sidebar.markdown("---")
    modulos = sorted(df_errores['modulo'].dropna().unique())
    filtro_modulo = st.sidebar.multiselect(
        "Módulo", options=modulos, default=[]
    )

    # Filtro Condición
    condiciones = sorted(df_errores['condicion'].dropna().unique())
    filtro_condicion = st.sidebar.multiselect(
        "Condición", options=condiciones, default=[]
    )

    # --- Aplicar filtros ---
    df_filtrado = df_errores.copy()

    if filtro_distrito:
        df_filtrado = df_filtrado[df_filtrado['distrito'].isin(filtro_distrito)]
    if filtro_entregable:
        df_filtrado = df_filtrado[df_filtrado['entregable'].isin(filtro_entregable)]
    if filtro_modulo:
        df_filtrado = df_filtrado[df_filtrado['modulo'].isin(filtro_modulo)]
    if filtro_condicion:
        df_filtrado = df_filtrado[df_filtrado['condicion'].isin(filtro_condicion)]

    # Filtro por fecha de recepción
    if fecha_rec_inicio:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_recepcion'], errors='coerce') >= pd.Timestamp(fecha_rec_inicio)
        ]
    if fecha_rec_fin:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_recepcion'], errors='coerce') <= pd.Timestamp(fecha_rec_fin)
        ]

    # Filtro por fecha de resultado
    if fecha_res_inicio:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_resultado'], errors='coerce') >= pd.Timestamp(fecha_res_inicio)
        ]
    if fecha_res_fin:
        df_filtrado = df_filtrado[
            pd.to_datetime(df_filtrado['fecha_resultado'], errors='coerce') <= pd.Timestamp(fecha_res_fin)
        ]

    if df_filtrado.empty:
        st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados.")
        return

    # ============================================================
    # 1. GRÁFICO DE BARRAS: Errores por Módulo y Condición
    # ============================================================
    st.subheader("📊 Errores por Módulo y Condición")

    df_grafico = (
        df_filtrado.groupby(['modulo', 'condicion'])
        .size()
        .reset_index(name='total')
    )

    # Pivot para gráfico agrupado
    df_pivot = df_grafico.pivot(index='modulo', columns='condicion', values='total').fillna(0)

    # Asegurar que existan columnas 'leve', 'grave', 'noindica'
    for cond in ['leve', 'grave', 'noindica']:
        if cond not in df_pivot.columns:
            df_pivot[cond] = 0

    st.bar_chart(
        df_pivot[['leve', 'grave', 'noindica']],
        use_container_width=True,
        height=400
    )

    # ============================================================
    # 2. TABLA RESUMEN AGRUPADA POR CÓDIGO PRINCIPAL (FI_02, BM_01...)
    # ============================================================
    st.subheader("📋 Resumen por Código Base")
    st.markdown("*Errores agrupados por código principal (ej: FI_02, BM_01)*")

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

    st.dataframe(
        df_resumen,
        use_container_width=True,
        hide_index=True
    )

    # ============================================================
    # 3. TABLA DETALLE POR CÓDIGO COMPLETO
    # ============================================================
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

    st.dataframe(
        df_detalle,
        use_container_width=True,
        hide_index=True
    )

    # --- Totales ---
    total_graves = df_filtrado[df_filtrado['condicion'] == 'grave'].shape[0]
    total_leves = df_filtrado[df_filtrado['condicion'] == 'leve'].shape[0]
    total_noindica = df_filtrado[df_filtrado['condicion'] == 'noindica'].shape[0]
    total_general = len(df_filtrado)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("🔴 Graves", total_graves)
    with col2:
        st.metric("🟡 Leves", total_leves)
    with col3:
        st.metric("⚪ No Indica", total_noindica)
    with col4:
        st.metric("📌 Total General", total_general)
    with col5:
        st.metric("📦 Registros BD", len(df_calidad))

    st.markdown("---")
    st.caption(f"Datos obtenidos de la tabla pública 'calidad_externa'. Última actualización: al recargar la página.")
