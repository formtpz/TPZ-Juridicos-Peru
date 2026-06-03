# modulos/filtro_errores.py
import streamlit as st
import pandas as pd
import os
from io import BytesIO
from permisos import validar_acceso
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# CONSTANTES
# ============================================================
MUNICIPIOS = {
    "VES": "🏛️ Vestigios",
    "SJM": "🏠 San Juan de Miraflores",
    "CH": "🌊 Chorrillos"
}

RENTAS_PATH = "Rentas_resumidos"


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def get_available_municipalities():
    """Obtiene municipios disponibles en la carpeta Rentas_resumidos"""
    if not os.path.exists(RENTAS_PATH):
        return []
    
    available = []
    for mun_code in MUNICIPIOS.keys():
        # Buscar tanto .xlsx como .xlsb
        file_xlsx = os.path.join(RENTAS_PATH, f"{mun_code}.xlsx")
        file_xlsb = os.path.join(RENTAS_PATH, f"{mun_code}.xlsb")
        
        if os.path.exists(file_xlsx) or os.path.exists(file_xlsb):
            available.append(mun_code)
    return available


def load_all_error_sheets(mun_code):
    """
    Carga todas las hojas del archivo de municipio.
    Soporta tanto .xlsx como .xlsb
    Cada hoja es un tipo de error diferente.
    Retorna un diccionario: {nombre_hoja: dataframe}
    """
    file_xlsx = os.path.join(RENTAS_PATH, f"{mun_code}.xlsx")
    file_xlsb = os.path.join(RENTAS_PATH, f"{mun_code}.xlsb")
    
    # Determinar qué archivo existe
    file_path = None
    if os.path.exists(file_xlsx):
        file_path = file_xlsx
        engine = "openpyxl"
    elif os.path.exists(file_xlsb):
        file_path = file_xlsb
        engine = "pyxlsb"
    else:
        return {}
    
    try:
        if engine == "pyxlsb":
            # Para archivos .xlsb usamos pyxlsb
            from pyxlsb import open_workbook
            sheets = {}
            with open_workbook(file_path) as wb:
                for sheet in wb.sheets:
                    try:
                        df = pd.read_excel(file_path, sheet_name=sheet.name, engine="pyxlsb")
                        if not df.empty:
                            sheets[sheet.name] = df
                    except Exception as e:
                        continue
            return sheets
        else:
            # Para archivos .xlsx usamos openpyxl
            xls = pd.ExcelFile(file_path, engine="openpyxl")
            sheets = {}
            for sheet_name in xls.sheet_names:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
                    if not df.empty:
                        sheets[sheet_name] = df
                except Exception as e:
                    continue
            return sheets
    except Exception as e:
        st.error(f"Error al cargar {mun_code}: {e}")
        return {}


def load_entregas_data():
    """Carga datos de Entregas_a_cofopri.xlsx"""
    file_path = os.path.join(RENTAS_PATH, "Entregas_a_cofopri.xlsx")
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        return df
    except Exception as e:
        st.error(f"Error al cargar Entregas_a_cofopri.xlsx: {e}")
        return None


def find_coordinate_columns(df):
    """
    Busca automáticamente las columnas de sector, manzana y lote en un DataFrame específico.
    Retorna un diccionario con los nombres de columnas encontrados.
    """
    cols_found = {}
    col_lower = [c.lower() for c in df.columns]
    
    # Buscar sector
    for col, col_l in zip(df.columns, col_lower):
        if "sector" in col_l or "sect" in col_l:
            cols_found["sector"] = col
            break
    
    # Buscar manzana
    for col, col_l in zip(df.columns, col_lower):
        if "manzana" in col_l or "manz" in col_l:
            cols_found["manzana"] = col
            break
    
    # Buscar lote
    for col, col_l in zip(df.columns, col_lower):
        if "lote" in col_l:
            cols_found["lote"] = col
            break
    
    return cols_found


def filter_data(df, sector=None, manzana=None, lote=None):
    """Filtra un dataframe por sector, manzana y lote"""
    filtered = df.copy()
    
    # Detectar columnas EN ESTE DATAFRAME ESPECÍFICO
    coords_cols = find_coordinate_columns(df)
    
    if not coords_cols:
        # Si no hay coordenadas, devolver todo
        return filtered
    
    if sector is not None and sector != "" and "sector" in coords_cols:
        sector_col = coords_cols["sector"]
        if sector_col in filtered.columns:
            sector_str = str(sector).zfill(2)
            filtered = filtered[
                filtered[sector_col].astype(str).str.zfill(2) == sector_str
            ]
    
    if manzana is not None and manzana != "" and "manzana" in coords_cols:
        manzana_col = coords_cols["manzana"]
        if manzana_col in filtered.columns:
            manzana_str = str(manzana).zfill(3)
            filtered = filtered[
                filtered[manzana_col].astype(str).str.zfill(3) == manzana_str
            ]
    
    if lote is not None and lote != "" and "lote" in coords_cols:
        lote_col = coords_cols["lote"]
        if lote_col in filtered.columns:
            lote_str = str(lote).zfill(3)
            filtered = filtered[
                filtered[lote_col].astype(str).str.zfill(3) == lote_str
            ]
    
    return filtered


def filter_by_polygon(entregas_df, polygon_code):
    """
    Filtra datos por código de polígono (ej: "VES-02").
    Busca las columnas cod_sector y cod_mzna automáticamente.
    """
    if entregas_df is None or entregas_df.empty:
        return pd.DataFrame()
    
    filtered = entregas_df.copy()
    coords_cols = find_coordinate_columns(filtered)
    
    try:
        mun_code, polygon_part = polygon_code.split("-")
    except:
        return pd.DataFrame()
    
    # Buscar columnas de sector y manzana
    sector_col = None
    manzana_col = None
    
    for col in filtered.columns:
        if "cod_sector" in col.lower() or "sector" in col.lower():
            sector_col = col
        if "cod_mzna" in col.lower() or "manzana" in col.lower():
            manzana_col = col
    
    if sector_col and manzana_col:
        sector_str = mun_code.zfill(2)
        manzana_str = polygon_part.zfill(3)
        
        filtered = filtered[
            (filtered[sector_col].astype(str).str.zfill(2) == sector_str) &
            (filtered[manzana_col].astype(str).str.zfill(3) == manzana_str)
        ]
    
    return filtered


def export_to_excel(dfs_dict):
    """Exporta múltiples DataFrames a un archivo Excel con múltiples hojas"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dfs_dict.items():
            # Limitar nombre de hoja a 31 caracteres
            safe_sheet_name = sheet_name[:31]
            df.to_excel(writer, index=False, sheet_name=safe_sheet_name)
    output.seek(0)
    return output


# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================

def render():
    validar_acceso("Filtro de Errores")
    
    st.title("🔍 Filtro de Errores - Consulta por Ubicación")
    st.markdown("""
    Filtra y visualiza errores por ubicación catastral.
    Selecciona un municipio, sector, manzana y/o lote para ver todos los errores asociados.
    """)
    
    # ============================================================
    # INICIALIZAR ESTADO DE SESIÓN
    # ============================================================
    if "current_municipio" not in st.session_state:
        st.session_state.current_municipio = None
    if "error_sheets_cache" not in st.session_state:
        st.session_state.error_sheets_cache = {}
    if "filtro_tipo_session" not in st.session_state:
        st.session_state.filtro_tipo_session = "sector_manzana"
    
    # ============================================================
    # SELECTOR DE MUNICIPIO
    # ============================================================
    available_mun = get_available_municipalities()
    
    if not available_mun:
        st.error("❌ No hay archivos de municipios disponibles en Rentas_resumidos/")
        st.info("📌 Se esperan archivos: VES.xlsx, SJM.xlsx, CH.xlsx o VES.xlsb, SJM.xlsb, CH.xlsb")
        return
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        municipio = st.selectbox(
            "🏘️ Selecciona un Municipio",
            options=available_mun,
            format_func=lambda x: MUNICIPIOS.get(x, x)
        )
    
    # Cargar datos si el municipio cambió
    if municipio != st.session_state.current_municipio:
        st.session_state.current_municipio = municipio
        st.session_state.error_sheets_cache = load_all_error_sheets(municipio)
        st.rerun()
    
    error_sheets = st.session_state.error_sheets_cache
    
    if not error_sheets:
        st.error(f"❌ No se encontraron hojas o datos en {municipio}")
        st.info("💡 Verifica que el archivo tenga al menos una hoja con datos")
        return
    
    total_registros = sum(len(df) for df in error_sheets.values())
    st.info(f"✅ Cargadas {len(error_sheets)} tipo(s) de error con {total_registros} registros en total")
    
    # ============================================================
    # MOSTRAR TABLA RESUMEN DE ERRORES
    # ============================================================
    st.subheader("📊 Resumen de Errores por Tipo")
    resumen_data = {
        "Tipo de Error": list(error_sheets.keys()),
        "Cantidad de Predios": [len(df) for df in error_sheets.values()]
    }
    resumen_df = pd.DataFrame(resumen_data)
    st.dataframe(resumen_df, use_container_width=True, hide_index=True)
    
    # ============================================================
    # SELECTOR DE TIPO DE FILTRADO
    # ============================================================
    st.markdown("---")
    st.subheader("🔎 Elige cómo deseas filtrar los datos")
    
    filtro_tipo = st.radio(
        "Opción de filtrado:",
        options=["sector_manzana", "poligono"],
        format_func=lambda x: {
            "sector_manzana": "📍 Filtrar por Sector, Manzana y Lote",
            "poligono": "🗺️ Filtrar por Polígono",
        }[x],
        horizontal=True
    )
    
    st.markdown("---")
    
    # ============================================================
    # OPCIÓN 1: FILTRAR POR SECTOR, MANZANA Y LOTE
    # ============================================================
    if filtro_tipo == "sector_manzana":
        st.subheader("📍 Filtro por Sector, Manzana y Lote")
        st.markdown("Selecciona la ubicación del predio para ver todos los errores asociados")
        
        # Consolidar todos los datos de todas las hojas para buscar coordenadas
        df_consolidated = pd.concat(error_sheets.values(), ignore_index=True)
        coords_cols = find_coordinate_columns(df_consolidated)
        
        if not coords_cols:
            st.warning("⚠️ No se encontraron columnas de sector, manzana o lote")
            st.write("Columnas disponibles:", list(df_consolidated.columns))
            return
        
        # Crear filtros cascada
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Selector de Sector
            sector_col = coords_cols.get("sector")
            if sector_col:
                sectors = sorted(df_consolidated[sector_col].dropna().unique())
                sector = st.selectbox(
                    f"Sector ({sector_col})",
                    options=[None] + list(sectors),
                    format_func=lambda x: f"Sector {str(x).zfill(2)}" if x is not None else "Todos"
                )
            else:
                sector = None
                st.warning("⚠️ Columna de sector no encontrada")
        
        # Filtrar manzanas según sector
        temp_df = df_consolidated.copy()
        if sector is not None and sector_col:
            temp_df = temp_df[temp_df[sector_col] == sector]
        
        with col2:
            # Selector de Manzana
            manzana_col = coords_cols.get("manzana")
            if manzana_col:
                manzanas = sorted(temp_df[manzana_col].dropna().unique())
                manzana = st.selectbox(
                    f"Manzana ({manzana_col})",
                    options=[None] + list(manzanas),
                    format_func=lambda x: f"Manzana {str(x).zfill(3)}" if x is not None else "Todas"
                )
            else:
                manzana = None
                st.warning("⚠️ Columna de manzana no encontrada")
        
        # Filtrar lotes según sector y manzana
        temp_df2 = df_consolidated.copy()
        if sector is not None and sector_col:
            temp_df2 = temp_df2[temp_df2[sector_col] == sector]
        if manzana is not None and manzana_col:
            temp_df2 = temp_df2[temp_df2[manzana_col] == manzana]
        
        with col3:
            # Selector de Lote
            lote_col = coords_cols.get("lote")
            if lote_col:
                lotes = sorted(temp_df2[lote_col].dropna().unique())
                lote = st.selectbox(
                    f"Lote ({lote_col})",
                    options=[None] + list(lotes),
                    format_func=lambda x: f"Lote {str(x).zfill(3)}" if x is not None else "Todos"
                )
            else:
                lote = None
        
        # ============================================================
        # FILTRAR POR CADA TIPO DE ERROR Y MOSTRAR EN TABS
        # ============================================================
        
        # Filtrar datos de cada tipo de error según los criterios
        filtered_errors = {}
        for error_name, df_error in error_sheets.items():
            df_filtered = filter_data(df_error, sector, manzana, lote)
            if not df_filtered.empty:
                filtered_errors[error_name] = df_filtered
        
        if not filtered_errors:
            st.warning("⚠️ No hay registros con los criterios seleccionados")
        else:
            total_filtered = sum(len(df) for df in filtered_errors.values())
            st.success(f"✅ Se encontraron {total_filtered} predio(s) con error(es)")
            
            # Mostrar info de ubicación
            location_info = []
            if sector is not None:
                location_info.append(f"Sector {str(sector).zfill(2)}")
            if manzana is not None:
                location_info.append(f"Manzana {str(manzana).zfill(3)}")
            if lote is not None:
                location_info.append(f"Lote {str(lote).zfill(3)}")
            
            location_text = " - ".join(location_info) if location_info else "General"
            st.info(f"📍 Ubicación: {location_text}")
            
            # Crear tabs dinámicamente para cada tipo de error encontrado
            tabs = st.tabs([f"🔴 {error_name} ({len(filtered_errors[error_name])})" for error_name in filtered_errors.keys()])
            
            # Dataframe consolidado para descargar
            all_filtered_data = {}
            
            for tab, (error_name, df_filtered) in zip(tabs, filtered_errors.items()):
                with tab:
                    st.markdown(f"### {error_name}")
                    st.write(f"**Predios con {error_name}:** {len(df_filtered)}")
                    
                    # Mostrar tabla
                    st.dataframe(df_filtered, use_container_width=True)
                    
                    # Guardar para descargar consolidado
                    all_filtered_data[error_name] = df_filtered
                    
                    # Botón descargar individual
                    excel_data = export_to_excel({error_name: df_filtered})
                    st.download_button(
                        label=f"⬇️ Descargar {error_name}",
                        data=excel_data,
                        file_name=f"{municipio}_{error_name}_filtrado.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"download_{error_name}"
                    )
            
            # Descargar todos los errores filtrados en un archivo
            st.markdown("---")
            st.subheader("📥 Descargar Consolidado")
            excel_all = export_to_excel(all_filtered_data)
            st.download_button(
                label="⬇️ Descargar Todos los Errores de esta Ubicación",
                data=excel_all,
                file_name=f"{municipio}_Errores_Consolidados_{location_text.replace(' ', '_')}.xlsx",
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
        
        # Obtener polígonos únicos (filtrados por municipio si es posible)
        polygon_col = None
        for col in df_entregas.columns:
            if "poligono" in col.lower():
                polygon_col = col
                break
        
        if polygon_col:
            poligonos = sorted(df_entregas[polygon_col].dropna().unique())
            # Filtrar por municipio actual si es posible
            poligonos = [p for p in poligonos if str(p).startswith(municipio)]
        else:
            st.error("❌ La columna 'poligono' no existe en Entregas_a_cofopri.xlsx")
            return
        
        if not poligonos:
            st.warning(f"⚠️ No hay polígonos para {municipio} en Entregas_a_cofopri.xlsx")
            return
        
        poligono_seleccionado = st.selectbox(
            "Selecciona un polígono",
            options=poligonos,
            format_func=lambda x: f"Polígono: {x}"
        )
        
        if st.button("✅ Aplicar Filtro de Polígono", type="primary", use_container_width=True):
            # Filtrar entregas por polígono
            entregas_filtradas = df_entregas[df_entregas[polygon_col] == poligono_seleccionado]
            
            if entregas_filtradas.empty:
                st.warning("⚠️ No hay registros de entregas para este polígono")
            else:
                st.success(f"✅ Se encontraron {len(entregas_filtradas)} registro(s) de entrega")
                
                with st.expander("📊 Ver datos de Entregas a COFOPRI", expanded=True):
                    st.dataframe(entregas_filtradas, use_container_width=True)
                
                # Descargar entregas filtradas
                excel_entregas = export_to_excel(
                    {"Entregas": entregas_filtradas}
                )
                st.download_button(
                    label="⬇️ Descargar Entregas de este Polígono",
                    data=excel_entregas,
                    file_name=f"Entregas_{poligono_seleccionado}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    # ============================================================
    # FOOTER CON INFORMACIÓN
    # ============================================================
    st.markdown("---")
    with st.expander("ℹ️ Información técnica"):
        st.write(f"**Municipio:** {MUNICIPIOS.get(municipio, municipio)}")
        st.write(f"**Total de tipos de error:** {len(error_sheets)}")
        st.write(f"**Total de predios con errores:** {total_registros}")
        
        df_consolidated = pd.concat(error_sheets.values(), ignore_index=True)
        coords_cols = find_coordinate_columns(df_consolidated)
        
        st.write(f"\n**Hojas/Errores cargadas:**")
        for error_name, df_error in error_sheets.items():
            sheet_coords = find_coordinate_columns(df_error)
            st.write(f"  - **{error_name}:** {len(df_error)} predios (Coords: {sheet_coords})")
