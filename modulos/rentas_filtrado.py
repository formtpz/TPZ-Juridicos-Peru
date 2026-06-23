# modulos/rentas_filtrado.py

import streamlit as st
import pandas as pd
import re
from db import get_engine

# ============ FUNCIONES DE CARGA CON CACHÉ ============
@st.cache_data(ttl=3600)
def load_filter_data():
    """
    Carga los campos necesarios para los filtros jerárquicos desde predios urbanos.
    """
    engine = get_engine()
    query = """
        SELECT codigo_predio, codigo_contribuyente, manzana, lote, cod_hu
        FROM public.rentas_vs_predio_urbano
    """
    df = pd.read_sql(query, engine)
    # Convertir a string por si hay valores numéricos
    df = df.astype(str)
    return df

@st.cache_data(ttl=3600)
def load_full_tables():
    """
    Carga las tres tablas completas.
    """
    engine = get_engine()
    contrib = pd.read_sql("SELECT * FROM public.rentas_vs_contribuyente", engine)
    construc = pd.read_sql("SELECT * FROM public.rentas_vs_construcciones", engine)
    predios = pd.read_sql("SELECT * FROM public.rentas_vs_predio_urbano", engine)
    return contrib, construc, predios

# ============ FUNCIÓN DE NORMALIZACIÓN ============
def normalize_manzana(s):
    """
    Elimina todo excepto letras (a-zA-Z) y convierte a minúsculas.
    """
    if pd.isna(s):
        return ''
    s = str(s)
    s = re.sub(r'[^a-zA-Z]', '', s)
    return s.lower()

# ============ FUNCIÓN PRINCIPAL DE RENDER ============
def render():
    st.title("🔍 Filtro Dinámico de Catastro por Predios")
    st.markdown("Selecciona `Código HU`, `Manzana` y `Lote` para filtrar los predios.")

    # --- Cargar datos con caché ---
    with st.spinner("Cargando datos..."):
        df_filtros = load_filter_data()          # contiene codigo_predio, codigo_contribuyente, manzana, lote, cod_hu
        df_contrib, df_construc, df_predios = load_full_tables()

    # --- Filtros jerárquicos sobre df_filtros ---
    cod_hu_opciones = sorted(df_filtros['cod_hu'].dropna().unique())
    manzana_opciones = sorted(df_filtros['manzana'].dropna().unique())
    lote_opciones = sorted(df_filtros['lote'].dropna().unique())

    selected_cod_hu = st.multiselect(
        "Código de Habilitación Urbana (cod_hu)",
        options=cod_hu_opciones,
        default=[],
        help="Selecciona uno o varios códigos HU"
    )

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

    # --- Aplicar filtros para obtener predios candidatos ---
    mask_filtros = pd.Series(True, index=df_filtros.index)
    if selected_cod_hu:
        mask_filtros &= df_filtros['cod_hu'].isin(selected_cod_hu)
    if selected_manzana:
        mask_filtros &= df_filtros['manzana'].isin(selected_manzana)
    if selected_lote:
        mask_filtros &= df_filtros['lote'].isin(selected_lote)

    df_filtrado_ubicacion = df_filtros[mask_filtros]
    # Lista de codigo_predio candidatos
    predios_candidatos = sorted(df_filtrado_ubicacion['codigo_predio'].dropna().unique())

    # --- Nota informativa de otras manzanas con la misma letra ---
    if selected_cod_hu and selected_manzana:
        todas_manzanas_codhu = df_filtros[df_filtros['cod_hu'].isin(selected_cod_hu)]['manzana'].dropna().unique()
        selected_normalized = {normalize_manzana(m) for m in selected_manzana}
        otras_manzanas = []
        for mz in todas_manzanas_codhu:
            if mz not in selected_manzana:
                if normalize_manzana(mz) in selected_normalized:
                    otras_manzanas.append(mz)
        if otras_manzanas:
            st.info(f"📌 El código HU **{', '.join(selected_cod_hu)}** también existe para las manzanas con la misma letra: **{', '.join(sorted(otras_manzanas))}**.")
        else:
            st.success("✅ Las manzanas seleccionadas cubren todas las existentes con esa letra para ese código HU.")

    # --- Tabla resumen de predios ---
    st.subheader("📋 Predios encontrados")
    if not df_filtrado_ubicacion.empty:
        # Mostrar tabla con codigo_predio, codigo_contribuyente, manzana, lote, cod_hu
        tabla_resumen = df_filtrado_ubicacion[['codigo_predio', 'codigo_contribuyente', 'manzana', 'lote', 'cod_hu']].drop_duplicates()
        st.dataframe(tabla_resumen, use_container_width=True)

        # Selección de predios
        st.markdown("### Selecciona los predios (por código) para visualizar sus datos completos")

        # Multiselect con búsqueda
        selected_predios_multiselect = st.multiselect(
            "Selecciona predios (puedes buscar por código)",
            options=predios_candidatos,
            default=[],
            help="Escribe el código de predio para buscar"
        )

        # Ingreso manual de códigos de predio
        st.markdown("o ingresa códigos de predio manualmente (separados por comas o espacios):")
        manual_input = st.text_area(
            "Códigos manuales",
            placeholder="Ej: 116707, 116706, 116705",
            help="Escribe los códigos de predio separados por comas o espacios."
        )

        # Unir ambas selecciones
        predios_seleccionados = set(selected_predios_multiselect)
        if manual_input.strip():
            codigos_manual = re.split(r'[,\s]+', manual_input.strip())
            codigos_manual = [c for c in codigos_manual if c.isdigit()]
            predios_seleccionados.update(codigos_manual)

        predios_seleccionados = list(predios_seleccionados)

        if st.button("🔎 Mostrar datos completos", type="primary"):
            if not predios_seleccionados:
                st.warning("No has seleccionado ningún predio.")
            else:
                # Obtener los codigos_contribuyente asociados a esos predios
                mask_predios_sel = df_filtros['codigo_predio'].isin(predios_seleccionados)
                contribuyentes_asociados = df_filtros.loc[mask_predios_sel, 'codigo_contribuyente'].dropna().unique().tolist()

                # Filtrar tabla de contribuyentes por codigo_contribuyente
                mask_contrib = df_contrib['codigo_contribuyente'].isin(contribuyentes_asociados)
                df_contrib_filt = df_contrib[mask_contrib]

                # Filtrar construcciones y predios por codigo_predio
                mask_construc = df_construc['codigo_predio'].isin(predios_seleccionados)
                df_construc_filt = df_construc[mask_construc]

                mask_predios_full = df_predios['codigo_predio'].isin(predios_seleccionados)
                df_predios_filt = df_predios[mask_predios_full]

                st.success(f"Mostrando datos para {len(predios_seleccionados)} predio(s) que involucran {len(contribuyentes_asociados)} contribuyente(s).")

                with st.expander("📄 Contribuyentes", expanded=True):
                    st.dataframe(df_contrib_filt, use_container_width=True)

                with st.expander("🏗️ Construcciones", expanded=True):
                    st.dataframe(df_construc_filt, use_container_width=True)

                with st.expander("🏠 Predios Urbanos", expanded=True):
                    st.dataframe(df_predios_filt, use_container_width=True)

    else:
        st.warning("No se encontraron predios con los filtros seleccionados.")

    st.divider()
    st.caption(f"Total de contribuyentes: {len(df_contrib)} | Total de predios: {len(df_predios)} | Total de construcciones: {len(df_construc)}")
