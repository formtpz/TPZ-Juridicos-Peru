# modulos/filtro_errores.py
import streamlit as st
import pandas as pd
import os
from io import BytesIO
from permisos import validar_acceso

# ============================================================
# CONSTANTES
# ============================================================
MUNICIPIOS = {
    "VES": "Vestigios",
    "SJM": "San Juan de Miraflores",
    "CH": "Chorrillos"
}

RENTAS_PATH = "Rentas_resumidos"

# Diccionario de tipos de errores y sus columnas asociadas
ERROR_TYPES = {
    "Puertas": "puertas",
    "Sin Rentas": "sin_rentas",
    "Pisos": "pisos",
    "Techos": "techos",
    "Muros": "muros",
    "Observaciones": "observaciones"
}


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def get_available_municipalities():
    """Obtiene municipios disponibles en la carpeta Rentas_resumidos"""
    if not os.path.exists(RENTAS_PATH):
        return []
    
    available = []
    for mun_code in MUNICIPIOS.keys():
        file_path = os.path.join(RENTAS_PATH, f"{mun_code}.xlsx")
        if os.path.exists(file_path):
            available.append(mun_code)
    return available


def load_municipality_data(mun_code):
    """Carga datos de un municipio específico"""
    file_path = os.path.join(RENTAS_PATH, f"{mun_code}.xlsx")
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        return df
    except Exception as e:
        st.error(f"Error al cargar {mun_code}: {e}")
        return None


def load_entregas_data():
    """Carga datos de Entregas_a_cofopri.xlsx"""
    file_path = os.path.join(RENTAS_PATH, "Entregas_a_cofopri.xlsx")
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        return df
    except Exception as e:
        st.error(f"Error al cargar Entregas_a_cofopri.xlsx: {e}")
        return None


def normalize_value(value):
    """Normaliza valores para comparación"""
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def get_error_tabs(df, sector=None, manzana=None, lote=None):
    """
    Obtiene los tabs de errores que tienen datos según los filtros.
    Retorna un diccionario con nombres de tabs que tienen errores.
    """
    tabs_with_errors = {}
    
    # Aplicar filtros si existen
    filtered_df = df.copy()
    
    if sector is not None:
        sector_str = str(sector).zfill(2)
        if "crc_sect" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["crc_sect"].astype(str).str.zfill(2) == sector_str
            ]
    
    if manzana is not None:
        manzana_str = str(manzana).zfill(3)
        if "crc_manz" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["crc_manz"].astype(str).str.zfill(3) == manzana_str
            ]
    
    if lote is not None:
        lote_str = str(lote).zfill(3)
        if "crc_lote" in filtered_df.columns:
            filtered_df = filtered_df[
                filtered_df["crc_lote"].astype(str).str.zfill(3) == lote_str
            ]
    
    if filtered_df.empty:
        return {}
    
    # Verificar qué columnas de error tienen datos (no vacíos)
    for error_name, error_col in ERROR_TYPES.items():
        if error_col in filtered_df.columns:
            # Contar registros con error (valores no nulos/vacíos)
            error_count = filtered_df[error_col].notna().sum()
            if error_count > 0:
                tabs_with_errors[error_name] = filtered_df[
                    filtered_df[error_col].notna()
                ].copy()
    
    return tabs_with_errors


def filter_by_sector_manzana_lote(df, sector, manzana, lote):
    """Filtra dataframe por sector, manzana y lote"""
    filtered = df.copy()
    
    if sector is not None and sector != "":
        sector_str = str(sector).zfill(2)
        if "crc_sect" in filtered.columns:
            filtered = filtered[
                filtered["crc_sect"].astype(str).str.zfill(2) == sector_str
            ]
    
    if manzana is not None and manzana != "":
        manzana_str = str(manzana).zfill(3)
        if "crc_manz" in filtered.columns:
            filtered = filtered[
                filtered["crc_manz"].astype(str).str.zfill(3) == manzana_str
            ]
    
    if lote is not None and lote != "":
        lote_str = str(lote).zfill(3)
        if "crc_lote" in filtered.columns:
            filtered = filtered[
                filtered["crc_lote"].astype(str).str.zfill(3) == lote_str
            ]
    
    return filtered


def filter_by_polygon(entregas_df, polygon_code):
    """
    Filtra datos por código de polígono.
    polygon_code: ej. "VES-02"
    """
    if entregas_df is None or entregas_df.empty:
        return pd.DataFrame()
    
    filtered = entregas_df.copy()
    
    # Buscar registros que coincidan con el código de polígono
    if "cod_sector" in filtered.columns and "cod_mzna" in filtered.columns:
        sector, manzana = polygon_code.split("-")
        filtered = filtered[
            (filtered["cod_sector"].astype(str).str.zfill(2) == sector.zfill(2)) &
            (filtered["cod_mzna"].astype(str).str.zfill(3) == manzana.zfill(3))
        ]
    
    return filtered


def export_to_excel(dfs_dict, filename):
    """Exporta múltiples DataFrames a un archivo Excel con múltiples hojas"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dfs_dict.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])  # Max 31 chars
    output.seek(0)
    return output


# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================

def render():
    validar_acceso("Filtro de Errores")
    
    st.title("🔍 Filtro de Errores - Base de Datos por Municipio")
    st.markdown("""
    Visualiza y filtra errores compilados por municipio.
    Selecciona una opción de filtrado y consulta los errores organizados por tipo.
    """)
    
    # ============================================================
    # INICIALIZAR ESTADO DE SESIÓN
    # ============================================================
    if "filtro_municipio" not in st.session_state:
        st.session_state.filtro_municipio = None
    if "filtro_tipo" not in st.session_state:
        st.session_state.filtro_tipo = "sector_manzana"
    if "df_municipio_cache" not in st.session_state:
        st.session_state.df_municipio_cache = None
    if "current_municipio" not in st.session_state:
        st.session_state.current_municipio = None
    
    # ============================================================
    # SELECTOR DE MUNICIPIO (PARTE SUPERIOR)
    # ============================================================
    available_mun = get_available_municipalities()
    
    if not available_mun:
        st.error("❌ No hay archivos de municipios disponibles en Rentas_resumidos/")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        municipio = st.selectbox(
            "🏘️ Selecciona un Municipio",
            options=available_mun,
            format_func=lambda x: f"{x} - {MUNICIPIOS[x]}"
        )
    
    # Cargar datos si el municipio cambió
    if municipio != st.session_state.current_municipio:
        st.session_state.current_municipio = municipio
        st.session_state.df_municipio_cache = load_municipality_data(municipio)
    
    df_municipio = st.session_state.df_municipio_cache
    
    if df_municipio is None or df_municipio.empty:
        st.error(f"❌ No se pudo cargar datos para {municipio}")
        return
    
    st.info(f"✅ Cargados {len(df_municipio)} registros de {municipio}")
    
    # ============================================================
    # SELECTOR DE TIPO DE FILTRADO
    # ============================================================
    st.markdown("---")
    st.subheader("Elige cómo deseas filtrar los datos")
    
    filtro_tipo = st.radio(
        "Opción de filtrado:",
        options=["sector_manzana", "poligono"],
        format_func=lambda x: {
            "sector_manzana": "📍 Filtrar por Sector, Manzana y Lote",
            "poligono": "🗺️ Filtrar por Polígono"
        }[x],
        horizontal=True
    )
    
    st.markdown("---")
    
    # ============================================================
    # OPCIÓN 1: FILTRAR POR SECTOR, MANZANA Y LOTE
    # ============================================================
    if filtro_tipo == "sector_manzana":
        st.subheader("📍 Filtro por Sector, Manzana y Lote")
        
        # Obtener valores únicos
        sectors = sorted(df_municipio["crc_sect"].dropna().unique())
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            sector = st.selectbox(
                "Sector",
                options=[None] + list(sectors),
                format_func=lambda x: f"Sector {str(x).zfill(2)}" if x is not None else "Todos"
            )
        
        # Filtrar manzanas según sector
        if sector is not None:
            manzanas_filtered = sorted(
                df_municipio[df_municipio["crc_sect"] == sector]["crc_manz"].dropna().unique()
            )
        else:
            manzanas_filtered = sorted(df_municipio["crc_manz"].dropna().unique())
        
        with col2:
            manzana = st.selectbox(
                "Manzana",
                options=[None] + list(manzanas_filtered),
                format_func=lambda x: f"Manzana {str(x).zfill(3)}" if x is not None else "Todas"
            )
        
        # Filtrar lotes según sector y manzana
        temp_df = df_municipio.copy()
        if sector is not None:
            temp_df = temp_df[temp_df["crc_sect"] == sector]
        if manzana is not None:
            temp_df = temp_df[temp_df["crc_manz"] == manzana]
        
        lotes_filtered = sorted(temp_df["crc_lote"].dropna().unique())
        
        with col3:
            lote = st.selectbox(
                "Lote",
                options=[None] + list(lotes_filtered),
                format_func=lambda x: f"Lote {str(x).zfill(3)}" if x is not None else "Todos"
            )
        
        # Aplicar filtros
        df_filtered = filter_by_sector_manzana_lote(df_municipio, sector, manzana, lote)
        
        if df_filtered.empty:
            st.warning("⚠️ No hay registros con los criterios seleccionados")
        else:
            st.success(f"✅ Se encontraron {len(df_filtered)} registros")
            
            # Obtener tabs con errores
            error_tabs = get_error_tabs(df_filtered, sector, manzana, lote)
            
            if not error_tabs:
                st.info("ℹ️ No hay errores en los registros seleccionados")
            else:
                st.subheader(f"📋 Errores encontrados ({len(error_tabs)} tipo(s))")
                
                # Crear tabs dinámicamente
                tabs = st.tabs([f"🔴 {error_name} ({len(df)})" for error_name, df in error_tabs.items()])
                
                for tab, (error_name, error_df) in zip(tabs, error_tabs.items()):
                    with tab:
                        st.markdown(f"### {error_name}")
                        st.dataframe(error_df, use_container_width=True)
                        
                        # Botón descargar individual
                        excel_data = export_to_excel(
                            {error_name: error_df},
                            f"{municipio}_{error_name}.xlsx"
                        )
                        st.download_button(
                            label=f"⬇️ Descargar {error_name}",
                            data=excel_data,
                            file_name=f"{municipio}_{error_name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                
                # Descargar todos los errores en un archivo
                st.markdown("---")
                excel_all = export_to_excel(error_tabs, f"{municipio}_Errores_Compilados.xlsx")
                st.download_button(
                    label="⬇️ Descargar Todos los Errores",
                    data=excel_all,
                    file_name=f"{municipio}_Errores_Compilados.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    # ============================================================
    # OPCIÓN 2: FILTRAR POR POLÍGONO
    # ============================================================
    elif filtro_tipo == "poligono":
        st.subheader("🗺️ Filtro por Polígono")
        
        # Cargar datos de entregas
        df_entregas = load_entregas_data()
        
        if df_entregas is None or df_entregas.empty:
            st.error("❌ No se pudo cargar Entregas_a_cofopri.xlsx")
            return
        
        # Obtener polígonos únicos
        if "poligono" in df_entregas.columns:
            poligonos = sorted(df_entregas["poligono"].dropna().unique())
        else:
            st.error("❌ La columna 'poligono' no existe en Entregas_a_cofopri.xlsx")
            return
        
        poligono_seleccionado = st.selectbox(
            "Selecciona un polígono",
            options=poligonos,
            format_func=lambda x: f"Polígono: {x}"
        )
        
        if st.button("✅ Aplicar Filtro de Polígono", type="primary", use_container_width=True):
            # Filtrar entregas por polígono
            entregas_filtradas = df_entregas[df_entregas["poligono"] == poligono_seleccionado]
            
            if entregas_filtradas.empty:
                st.warning("⚠️ No hay registros para este polígono")
            else:
                st.success(f"✅ Se encontraron {len(entregas_filtradas)} registros de entregas")
                
                with st.expander("📊 Ver datos de Entregas a COFOPRI", expanded=False):
                    st.dataframe(entregas_filtradas, use_container_width=True)
                
                # Descargar entregas filtradas
                excel_entregas = export_to_excel(
                    {"Entregas": entregas_filtradas},
                    f"Entregas_{poligono_seleccionado}.xlsx"
                )
                st.download_button(
                    label="⬇️ Descargar Entregas de este Polígono",
                    data=excel_entregas,
                    file_name=f"Entregas_{poligono_seleccionado}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    # ============================================================
    # VISTA GENERAL (OPCIONAL)
    # ============================================================
    st.markdown("---")
    with st.expander("📂 Ver estructura de datos completa"):
        st.write(f"**Total de columnas:** {len(df_municipio.columns)}")
        st.write(f"**Total de filas:** {len(df_municipio)}")
        st.write("**Columnas disponibles:**")
        st.write(list(df_municipio.columns))
        
        with st.expander("Vista previa (primeras 10 filas)"):
            st.dataframe(df_municipio.head(10), use_container_width=True)
