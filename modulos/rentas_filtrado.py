# modulos/rentas_filtrado.py

import streamlit as st
import pandas as pd
import re
from db import fetch_df   # <--- importamos fetch_df en lugar de get_engine

# ============ FUNCIONES DE CARGA CON CACHÉ (usando fetch_df) ============

@st.cache_data(ttl=3600)
def load_filter_data():
    """
    Carga los campos necesarios para los filtros jerárquicos.
    """
    query = """
        SELECT codigo_contribuyente, codigo_predio, manzana, lote, cod_hu 
        FROM public.rentas_vs_predio_urbano
    """
    df = fetch_df(query)
    return df

@st.cache_data(ttl=3600)
def load_full_tables():
    """
    Carga las tres tablas completas y reordena las columnas de predios.
    """
    contrib = fetch_df("SELECT * FROM public.rentas_vs_contribuyente")
    construc = fetch_df("SELECT * FROM public.rentas_vs_construcciones")
    predios = fetch_df("SELECT * FROM public.rentas_vs_predio_urbano")

    # ===== REORDENAR COLUMNAS DE PREDIOS =====
    orden_deseado = [
        'codigo_contribuyente',
        'codigo_predio',
        'manzana',
        'lote',
        'codigo_habilitacion_urbana',
        'zona_habilitacion',
        'fecha_adquisicion',
        'descripcion_del_uso',
        'tipo_predio',
        'condicion_propiedad',
        'porcentaje_condominio',
        'area_terreno',
        'area_terreno_comun',
        'area_construida',
        'area_construida_comun',
    ]
    columnas_existentes = predios.columns.tolist()
    orden_final = [col for col in orden_deseado if col in columnas_existentes]
    orden_final += [col for col in columnas_existentes if col not in orden_final]
    predios = predios[orden_final]

    return contrib, construc, predios

# ============ FUNCIÓN DE NORMALIZACIÓN ============
def normalize_manzana(s):
    """
    Normaliza una manzana: elimina todo excepto letras (a-zA-Z) y convierte a minúsculas.
    """
    if pd.isna(s):
        return ''
    s = str(s)
    s = re.sub(r'[^a-zA-Z]', '', s)
    return s.lower()

# ============ FUNCIÓN PRINCIPAL DE RENDER ============
def render():
    st.title("🔍 Filtro Dinámico de Catastro")
    st.markdown("Selecciona `Código HU`, `Manzana` y `Lote` para filtrar los predios.")

    # --- Cargar datos con caché ---
    with st.spinner("Cargando datos..."):
        df_filtros = load_filter_data()
        df_contrib, df_construc, df_predios = load_full_tables()

    # --- Filtros jerárquicos (usando cod_hu) ---
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

    # --- Aplicar filtros jerárquicos para obtener los predios candidatos ---
    mask_filtros = pd.Series(True, index=df_filtros.index)
    if selected_cod_hu:
        mask_filtros &= df_filtros['cod_hu'].isin(selected_cod_hu)
    if selected_manzana:
        mask_filtros &= df_filtros['manzana'].isin(selected_manzana)
    if selected_lote:
        mask_filtros &= df_filtros['lote'].isin(selected_lote)

    df_filtrado_ubicacion = df_filtros[mask_filtros]
    # Obtener lista de codigo_predio y codigo_contribuyente de los predios filtrados
    predios_candidatos = df_filtrado_ubicacion[['codigo_predio', 'codigo_contribuyente']].drop_duplicates()

    # --- Mostrar nota informativa sobre otras manzanas con la misma letra ---
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

    # --- Tabla resumen de predios encontrados ---
    st.subheader("📋 Predios encontrados")
    if not df_filtrado_ubicacion.empty:
        # Mostrar tabla resumen con codigo_predio, codigo_contribuyente, manzana, lote, cod_hu
        tabla_resumen = df_filtrado_ubicacion[['codigo_predio', 'codigo_contribuyente', 'manzana', 'lote', 'cod_hu']].drop_duplicates()
        st.dataframe(tabla_resumen, use_container_width=True)

        # --- Selección de predios por código_predio ---
        st.markdown("### Selecciona los predios para visualizar sus datos completos")

        # Opción 1: Multiselect con búsqueda (usando codigo_predio)
        opciones_predios = sorted(predios_candidatos['codigo_predio'].dropna().unique())
        selected_predios_multiselect = st.multiselect(
            "Selecciona predios (puedes buscar por código)",
            options=opciones_predios,
            default=[],
            help="Escribe el código de predio para buscar"
        )

        # Opción 2: Ingreso manual de códigos de predio
        st.markdown("o ingresa códigos de predio manualmente (separados por comas o espacios):")
        manual_input = st.text_area(
            "Códigos de predio manuales",
            placeholder="Ej: 116707, 116706, 116705",
            help="Escribe los códigos separados por comas o espacios."
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
                # Obtener los códigos de contribuyente asociados a los predios seleccionados
                contribuyentes_asociados = df_filtrado_ubicacion[
                    df_filtrado_ubicacion['codigo_predio'].isin(predios_seleccionados)
                ]['codigo_contribuyente'].dropna().unique().tolist()

                # --- Filtrar las tres tablas ---
                mask_contrib = df_contrib['codigo_contribuyente'].isin(contribuyentes_asociados)
                df_contrib_filt = df_contrib[mask_contrib]

                mask_construc = df_construc['codigo_predio'].isin(predios_seleccionados)
                df_construc_filt = df_construc[mask_construc]

                mask_predios = df_predios['codigo_predio'].isin(predios_seleccionados)
                df_predios_filt = df_predios[mask_predios]

                st.success(f"Mostrando datos para {len(predios_seleccionados)} predio(s) y {len(contribuyentes_asociados)} contribuyente(s).")

                with st.expander("📄 Contribuyentes", expanded=True):
                    st.dataframe(df_contrib_filt, use_container_width=True)

                with st.expander("🏗️ Construcciones", expanded=True):
                    st.dataframe(df_construc_filt, use_container_width=True)

                with st.expander("🏠 Predios Urbanos", expanded=True):
                    st.dataframe(df_predios_filt, use_container_width=True)

    else:
        st.warning("No se encontraron predios con los filtros seleccionados.")

    st.divider()
    st.caption(f"Total de contribuyentes: {len(df_contrib)} | Predios: {len(df_predios)} | Construcciones: {len(df_construc)}")
