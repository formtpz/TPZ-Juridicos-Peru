# modulos/filtro_dinamico.py

import streamlit as st
import pandas as pd
import re
from db import get_connection

# ============ FUNCIONES DE CARGA CON CACHÉ ============
@st.cache_data(ttl=3600)  # cache por 1 hora (datos fijos)
def load_filter_data():
    """
    Carga solo los campos necesarios para los filtros jerárquicos.
    """
    conn = get_connection()
    query = """
        SELECT codigo_contribuyente, manzana, lote, cod_hu 
        FROM public.rentas_vs_predio_urbano
    """
    df = pd.read_sql(query, conn)
    conn.close()
    return df

@st.cache_data(ttl=3600)
def load_full_tables():
    """
    Carga las tres tablas completas.
    """
    conn = get_connection()
    contrib = pd.read_sql("SELECT * FROM public.rentas_vs_contribuyente", conn)
    construc = pd.read_sql("SELECT * FROM public.rentas_vs_construcciones", conn)
    predios = pd.read_sql("SELECT * FROM public.rentas_vs_predio_urbano", conn)
    conn.close()
    return contrib, construc, predios

# ============ FUNCIONES DE NORMALIZACIÓN ============
def normalize_string(s):
    """
    Normaliza una cadena: minúsculas, elimina espacios, signos de puntuación y apóstrofes.
    """
    if pd.isna(s):
        return ''
    s = str(s)
    # Eliminar todo excepto letras y números (elimina espacios, puntos, comas, apóstrofes, etc.)
    s = re.sub(r'[^a-zA-Z0-9]', '', s)
    return s.lower()

def get_normalized_manzanas(df, cod_hu_selected):
    """
    Dado un cod_hu (o lista), devuelve un diccionario {normalizado: valor_original}
    de todas las manzanas que existen para ese cod_hu.
    """
    if not cod_hu_selected:
        return {}
    mask = df['cod_hu'].isin(cod_hu_selected)
    manzanas = df.loc[mask, 'manzana'].dropna().unique()
    result = {}
    for mz in manzanas:
        norm = normalize_string(mz)
        # Si hay duplicados normalizados, conservamos el primero (o podríamos mostrar todos)
        if norm not in result:
            result[norm] = mz
    return result

# ============ FUNCIÓN PRINCIPAL DE RENDER ============
def render():
    st.title("🔍 Filtro Dinámico de Catastro")
    st.markdown("Selecciona `Código HU`, `Manzana` y `Lote` para filtrar los contribuyentes.")

    # --- Cargar datos con caché ---
    with st.spinner("Cargando datos..."):
        df_filtros = load_filter_data()
        df_contrib, df_construc, df_predios = load_full_tables()

    # --- Filtros jerárquicos ---
    # 1. Obtener listas únicas (ordenadas)
    cod_hu_opciones = sorted(df_filtros['cod_hu'].dropna().unique())
    manzana_opciones = sorted(df_filtros['manzana'].dropna().unique())
    lote_opciones = sorted(df_filtros['lote'].dropna().unique())

    # Estado de selecciones
    selected_cod_hu = st.multiselect(
        "Código de Habilitación Urbana (cod_hu)",
        options=cod_hu_opciones,
        default=[],
        help="Selecciona uno o varios códigos HU"
    )

    # Filtrar manzanas según cod_hu seleccionado
    if selected_cod_hu:
        manzanas_filtradas = sorted(
            df_filtros[df_filtros['cod_hu'].isin(selected_cod_hu)]['manzana'].dropna().unique()
        )
    else:
        manzanas_filtradas = manzana_opciones

    selected_manzana = st.multiselect(
        "Manzana",
        options=manzanas_filtradas,
        default=[],
        help="Selecciona una o varias manzanas"
    )

    # Filtrar lotes según cod_hu y manzana seleccionados
    mask_lotes = pd.Series(True, index=df_filtros.index)
    if selected_cod_hu:
        mask_lotes &= df_filtros['cod_hu'].isin(selected_cod_hu)
    if selected_manzana:
        mask_lotes &= df_filtros['manzana'].isin(selected_manzana)
    lotes_filtrados = sorted(df_filtros[mask_lotes]['lote'].dropna().unique()) if mask_lotes.any() else []

    selected_lote = st.multiselect(
        "Lote",
        options=lotes_filtrados,
        default=[],
        help="Selecciona uno o varios lotes"
    )

    # --- Aplicar filtros jerárquicos para obtener los contribuyentes candidatos ---
    mask_filtros = pd.Series(True, index=df_filtros.index)
    if selected_cod_hu:
        mask_filtros &= df_filtros['cod_hu'].isin(selected_cod_hu)
    if selected_manzana:
        mask_filtros &= df_filtros['manzana'].isin(selected_manzana)
    if selected_lote:
        mask_filtros &= df_filtros['lote'].isin(selected_lote)

    df_filtrado_ubicacion = df_filtros[mask_filtros]
    contribuyentes_candidatos = sorted(df_filtrado_ubicacion['codigo_contribuyente'].dropna().unique())

    # --- Mostrar nota informativa sobre otras manzanas (si hay cod_hu y manzana seleccionados) ---
    if selected_cod_hu and selected_manzana:
        # Obtener todas las manzanas para ese cod_hu
        manzanas_dict = get_normalized_manzanas(df_filtros, selected_cod_hu)
        # Normalizar las manzanas seleccionadas
        selected_norm = [normalize_string(m) for m in selected_manzana]
        # Otras manzanas (normalizadas) que no están en las seleccionadas
        otras_norm = [n for n in manzanas_dict.keys() if n not in selected_norm]
        if otras_norm:
            # Mostrar los valores originales
            otras_originales = [manzanas_dict[n] for n in otras_norm]
            st.info(f"📌 El código HU **{', '.join(selected_cod_hu)}** también existe para las manzanas: **{', '.join(otras_originales)}**.")
        else:
            st.success("✅ Las manzanas seleccionadas cubren todas las existentes para ese código HU.")

    # --- Tabla resumen de contribuyentes ---
    st.subheader("📋 Contribuyentes encontrados")
    if not df_filtrado_ubicacion.empty:
        # Mostrar tabla resumen
        tabla_resumen = df_filtrado_ubicacion[['codigo_contribuyente', 'manzana', 'lote', 'cod_hu']].drop_duplicates()
        st.dataframe(tabla_resumen, use_container_width=True)

        # Selección de contribuyentes
        st.markdown("### Selecciona los contribuyentes para visualizar sus datos completos")

        # Opción 1: Multiselect (con búsqueda)
        selected_contrib_multiselect = st.multiselect(
            "Selecciona contribuyentes (puedes buscar por código)",
            options=contribuyentes_candidatos,
            default=[],
            help="Escribe el código para buscar"
        )

        # Opción 2: Ingreso manual
        st.markdown("o ingresa códigos manualmente (separados por comas o espacios):")
        manual_input = st.text_area(
            "Códigos manuales",
            placeholder="Ej: 10016367, 10016366, 10016365",
            help="Escribe los códigos separados por comas o espacios."
        )

        # Unir ambas selecciones
        contribuyentes_seleccionados = set(selected_contrib_multiselect)
        if manual_input.strip():
            # Parsear: separar por comas o espacios y limpiar
            import re
            codigos_manual = re.split(r'[,\s]+', manual_input.strip())
            codigos_manual = [c for c in codigos_manual if c.isdigit()]  # solo números
            contribuyentes_seleccionados.update(codigos_manual)

        contribuyentes_seleccionados = list(contribuyentes_seleccionados)

        if st.button("🔎 Mostrar datos completos", type="primary"):
            if not contribuyentes_seleccionados:
                st.warning("No has seleccionado ningún contribuyente.")
            else:
                # Filtrar las tres tablas
                mask_contrib = df_contrib['codigo_contribuyente'].isin(contribuyentes_seleccionados)
                df_contrib_filt = df_contrib[mask_contrib]

                mask_construc = df_construc['codigo_contribuyente'].isin(contribuyentes_seleccionados)
                df_construc_filt = df_construc[mask_construc]

                mask_predios = df_predios['codigo_contribuyente'].isin(contribuyentes_seleccionados)
                df_predios_filt = df_predios[mask_predios]

                # Mostrar resultados
                st.success(f"Mostrando datos para {len(contribuyentes_seleccionados)} contribuyente(s).")

                with st.expander("📄 Contribuyentes", expanded=True):
                    st.dataframe(df_contrib_filt, use_container_width=True)

                with st.expander("🏗️ Construcciones", expanded=True):
                    st.dataframe(df_construc_filt, use_container_width=True)

                with st.expander("🏠 Predios Urbanos", expanded=True):
                    st.dataframe(df_predios_filt, use_container_width=True)

                # Opción de descarga (opcional)
                # st.download_button(...)
    else:
        st.warning("No se encontraron contribuyentes con los filtros seleccionados.")

    # --- Pie de página: estadísticas ---
    st.divider()
    st.caption(f"Total de contribuyentes en la base: {len(df_contrib)} | Predios: {len(df_predios)} | Construcciones: {len(df_construc)}")
