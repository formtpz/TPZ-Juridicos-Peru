# modulos/rentas_filtrado.py

import streamlit as st
import pandas as pd
import re
from db import get_engine  # Importamos el engine SQLAlchemy

# ============ FUNCIONES DE CARGA CON CACHÉ ============
@st.cache_data(ttl=3600)
def load_filter_data():
    """
    Carga solo los campos necesarios para los filtros jerárquicos.
    """
    engine = get_engine()
    query = """
        SELECT codigo_contribuyente, manzana, lote, cod_hu 
        FROM public.rentas_vs_predio_urbano
    """
    df = pd.read_sql(query, engine)
    return df

@st.cache_data(ttl=3600)
def load_full_tables():
    """
    Carga las tres tablas completas usando SQLAlchemy engine.
    """
    engine = get_engine()
    contrib = pd.read_sql("SELECT * FROM public.rentas_vs_contribuyente", engine)
    construc = pd.read_sql("SELECT * FROM public.rentas_vs_construcciones", engine)
    predios = pd.read_sql("SELECT * FROM public.rentas_vs_predio_urbano", engine)
    return contrib, construc, predios

# ============ FUNCIÓN DE NORMALIZACIÓN ============
def normalize_manzana(s):
    """
    Normaliza una manzana: elimina todo excepto letras (a-zA-Z) y convierte a minúsculas.
    Ejemplo: "H-1" -> "h", "C'" -> "c", "A''" -> "a"
    """
    if pd.isna(s):
        return ''
    s = str(s)
    # Eliminar todo excepto letras
    s = re.sub(r'[^a-zA-Z]', '', s)
    return s.lower()

# ============ FUNCIÓN PRINCIPAL DE RENDER ============
def render():
    st.title("🔍 Filtro Dinámico de Catastro")
    st.markdown("Selecciona `Código HU`, `Manzana` y `Lote` para filtrar los contribuyentes.")

    # --- Cargar datos con caché ---
    with st.spinner("Cargando datos..."):
        df_filtros = load_filter_data()
        df_contrib, df_construc, df_predios = load_full_tables()

    # --- Filtros jerárquicos ---
    cod_hu_opciones = sorted(df_filtros['cod_hu'].dropna().unique())
    manzana_opciones = sorted(df_filtros['manzana'].dropna().unique())
    lote_opciones = sorted(df_filtros['lote'].dropna().unique())

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

    # --- Mostrar nota informativa sobre otras manzanas con la MISMA LETRA ---
    if selected_cod_hu and selected_manzana:
        # Obtener todas las manzanas para ese cod_hu (sin filtrar por las seleccionadas)
        todas_manzanas_codhu = df_filtros[df_filtros['cod_hu'].isin(selected_cod_hu)]['manzana'].dropna().unique()
        
        # Normalizar las manzanas seleccionadas
        selected_normalized = {normalize_manzana(m) for m in selected_manzana}
        
        # Filtrar otras manzanas (no seleccionadas) que tengan la misma normalización
        otras_manzanas = []
        for mz in todas_manzanas_codhu:
            if mz not in selected_manzana:  # excluir las ya seleccionadas
                if normalize_manzana(mz) in selected_normalized:
                    otras_manzanas.append(mz)
        
        if otras_manzanas:
            st.info(f"📌 El código HU **{', '.join(selected_cod_hu)}** también existe para las manzanas con la misma letra: **{', '.join(sorted(otras_manzanas))}**.")
        else:
            st.success("✅ Las manzanas seleccionadas cubren todas las existentes con esa letra para ese código HU.")

    # --- Tabla resumen de contribuyentes ---
    st.subheader("📋 Contribuyentes encontrados")
    if not df_filtrado_ubicacion.empty:
        tabla_resumen = df_filtrado_ubicacion[['codigo_contribuyente', 'manzana', 'lote', 'cod_hu']].drop_duplicates()
        st.dataframe(tabla_resumen, use_container_width=True)

        # Selección de contribuyentes
        st.markdown("### Selecciona los contribuyentes para visualizar sus datos completos")

        # Multiselect con búsqueda
        selected_contrib_multiselect = st.multiselect(
            "Selecciona contribuyentes (puedes buscar por código)",
            options=contribuyentes_candidatos,
            default=[],
            help="Escribe el código para buscar"
        )

        # Ingreso manual
        st.markdown("o ingresa códigos manualmente (separados por comas o espacios):")
        manual_input = st.text_area(
            "Códigos manuales",
            placeholder="Ej: 10016367, 10016366, 10016365",
            help="Escribe los códigos separados por comas o espacios."
        )

        # Unir ambas selecciones
        contribuyentes_seleccionados = set(selected_contrib_multiselect)
        if manual_input.strip():
            codigos_manual = re.split(r'[,\s]+', manual_input.strip())
            codigos_manual = [c for c in codigos_manual if c.isdigit()]
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

                st.success(f"Mostrando datos para {len(contribuyentes_seleccionados)} contribuyente(s).")

                with st.expander("📄 Contribuyentes", expanded=True):
                    st.dataframe(df_contrib_filt, use_container_width=True)

                with st.expander("🏗️ Construcciones", expanded=True):
                    st.dataframe(df_construc_filt, use_container_width=True)

                with st.expander("🏠 Predios Urbanos", expanded=True):
                    st.dataframe(df_predios_filt, use_container_width=True)

    else:
        st.warning("No se encontraron contribuyentes con los filtros seleccionados.")

    st.divider()
    st.caption(f"Total de contribuyentes en la base: {len(df_contrib)} | Predios: {len(df_predios)} | Construcciones: {len(df_construc)}")
