# modulos/filtro_errores.py
# Versión: 3.5 - Repositorio de errores con manejo mejorado de usuarios múltiples
import streamlit as st
import pandas as pd
import os
from io import BytesIO
from permisos import validar_acceso
import warnings
from datetime import datetime
import traceback
import time
import threading
warnings.filterwarnings('ignore')

# ============================================================
# CONSTANTES
# ============================================================
MUNICIPIOS = {
    "VES": "🏛️ Villa El Salvador",
    "SJM": "🏠 San Juan de Miraflores",
    "CH": "🌊 Chorrillos"
}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ERROR_REPOSITORY_PATH = os.path.join(BASE_DIR, "Repositorio_de_Errores")
RENTAS_PATH = os.path.join(BASE_DIR, "Rentas_resumidos")

ESTADOS_VALIDOS = ["No corregido", "Corregido", "Falso positivo"]

# Lock para evitar condiciones de carrera con archivos
_file_lock = threading.Lock()
LOCK_TIMEOUT = 30  # segundos

# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def ensure_error_repository_exists():
    """
    Verifica que la carpeta Repositorio_de_Errores exista.
    Si no existe, la crea.
    """
    if not os.path.exists(ERROR_REPOSITORY_PATH):
        os.makedirs(ERROR_REPOSITORY_PATH, exist_ok=True)
        st.info(f"📁 Se creó la carpeta '{ERROR_REPOSITORY_PATH}'")
    return os.path.exists(ERROR_REPOSITORY_PATH)


def get_available_error_files():
    """
    Obtiene lista de archivos Excel en Repositorio_de_Errores
    Soporta .xlsx y .xlsb
    """
    if not os.path.exists(ERROR_REPOSITORY_PATH):
        return []
    
    available_files = []
    for filename in os.listdir(ERROR_REPOSITORY_PATH):
        if filename.endswith(('.xlsx', '.xlsb')) and not filename.startswith('~'):
            available_files.append(filename)
    
    return sorted(available_files)


def sync_error_file_session_state(available_files):
    """
    Sincroniza el estado de Streamlit con los Excel que existen actualmente
    para evitar referencias obsoletas a archivos ya eliminados.
    """
    current_files = set(available_files)
    previous_files = set(st.session_state.get("error_repository_files", []))
    removed_files = previous_files - current_files

    current_error_file = st.session_state.get("current_error_file")
    if current_error_file and current_error_file not in current_files:
        removed_files.add(current_error_file)
        st.session_state.current_error_file = None
        st.session_state.error_sheets_cache = {}
        st.session_state.file_modified = False
        st.session_state.file_loaded = False

    selected_error_file = st.session_state.get("selected_error_file")
    if selected_error_file and selected_error_file not in current_files:
        st.session_state.selected_error_file = None

    if available_files:
        if st.session_state.get("selected_error_file") is None:
            st.session_state.selected_error_file = available_files[0]
    else:
        st.session_state.selected_error_file = None

    st.session_state.error_repository_files = list(available_files)
    return sorted(removed_files)


def load_error_file(filename):
    """
    Carga un archivo Excel desde Repositorio_de_Errores
    Retorna un diccionario {nombre_hoja: dataframe}
    Con mejor manejo de errores y debug
    """
    file_path = os.path.join(ERROR_REPOSITORY_PATH, filename)
    
    if not os.path.exists(file_path):
        st.error(f"❌ Archivo no encontrado: {file_path}")
        return {}
    
    try:
        if filename.endswith('.xlsb'):
            # ===== CARGAR .XLSB =====
            from pyxlsb import open_workbook
            sheets = {}
            try:
                with open_workbook(file_path) as wb:
                    sheet_names = [sheet.name for sheet in wb.sheets]
                    
                    if not sheet_names:
                        st.error(f"❌ El archivo {filename} no contiene hojas")
                        return {}
                    
                    st.info(f"📂 Hojas encontradas en {filename}: {', '.join(sheet_names)}")
                    
                    for sheet_name in sheet_names:
                        try:
                            df = pd.read_excel(file_path, sheet_name=sheet_name, engine="pyxlsb")
                            
                            if df.empty or len(df) == 0:
                                st.warning(f"⚠️ La hoja '{sheet_name}' está vacía")
                                continue
                            
                            st.info(f"✅ Hoja '{sheet_name}' cargada: {len(df)} filas")
                            
                            df = ensure_status_columns(df)
                            df = convert_data_types_safely(df)
                            sheets[sheet_name] = df
                            
                        except Exception as e:
                            st.error(f"❌ Error al leer hoja '{sheet_name}' en {filename}:")
                            st.error(f"   {str(e)}")
                            continue
                    
                    if sheets:
                        st.success(f"✅ {len(sheets)} hoja(s) cargada(s) exitosamente")
                    
                    return sheets
            except Exception as e:
                st.error(f"❌ Error general al abrir {filename}:")
                st.error(f"   {str(e)}")
                return {}
        
        else:
            # ===== CARGAR .XLSX =====
            try:
                # Primero obtener lista de hojas
                xls = pd.ExcelFile(file_path, engine="openpyxl")
                sheet_names = xls.sheet_names
                
                if not sheet_names:
                    st.error(f"❌ El archivo {filename} no contiene hojas")
                    return {}
                
                st.info(f"📂 Hojas encontradas en {filename}: {', '.join(sheet_names)}")
                
                sheets = {}
                for sheet_name in sheet_names:
                    try:
                        # Intentar cargar la hoja
                        df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
                        
                        # Verificar si está vacía
                        if df.empty or len(df) == 0:
                            st.warning(f"⚠️ La hoja '{sheet_name}' está vacía (0 filas)")
                            continue
                        
                        # Log de éxito
                        st.info(f"✅ Hoja '{sheet_name}' cargada: {len(df)} filas, {len(df.columns)} columnas")
                        st.write(f"   Columnas: {', '.join(df.columns[:5])}{'...' if len(df.columns) > 5 else ''}")
                        
                        # Aplicar transformaciones
                        df = ensure_status_columns(df)
                        df = convert_data_types_safely(df)
                        sheets[sheet_name] = df
                        
                    except Exception as e:
                        st.error(f"❌ Error al leer hoja '{sheet_name}' en {filename}:")
                        st.error(f"   Tipo: {type(e).__name__}")
                        st.error(f"   Mensaje: {str(e)}")
                        st.error(f"   Traceback: {traceback.format_exc()}")
                        continue
                
                if sheets:
                    st.success(f"✅ {len(sheets)} hoja(s) cargada(s) exitosamente")
                else:
                    st.warning(f"⚠️ No se pudo cargar ninguna hoja del archivo {filename}")
                
                return sheets
                
            except Exception as e:
                st.error(f"❌ Error general al procesar {filename}:")
                st.error(f"   Tipo: {type(e).__name__}")
                st.error(f"   Mensaje: {str(e)}")
                return {}
    
    except Exception as e:
        st.error(f"❌ Error crítico al cargar {filename}:")
        st.error(f"   {str(e)}")
        st.error(traceback.format_exc())
        return {}


def convert_data_types_safely(df):
    """
    Convierte tipos de datos de forma segura para evitar OverflowError con PyArrow
    Convierte tipos complejos a string para compatibilidad con st.data_editor
    """
    df = df.copy()
    
    for col in df.columns:
        try:
            # Si es una columna de fecha, convertir a string ISO
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
            # Si es una columna de timedelta, convertir a string
            elif pd.api.types.is_timedelta64_dtype(df[col]):
                df[col] = df[col].astype(str)
            # Convertir todo a string para evitar problemas con PyArrow
            elif not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].astype(str)
        except Exception:
            try:
                df[col] = df[col].astype(str)
            except Exception:
                pass
    
    return df


def ensure_status_columns(df):
    """
    Verifica que existan las columnas de estado.
    Si no existen, las crea con valores por defecto.
    """
    # Columna de Estado
    if "Estado" not in df.columns:
        df.insert(len(df.columns), "Estado", "No corregido")
    
    # Columna de Usuario
    if "Usuario_Corrigió" not in df.columns:
        df.insert(len(df.columns), "Usuario_Corrigió", "")
    
    # Columna de Fecha
    if "Fecha_Corrección" not in df.columns:
        df.insert(len(df.columns), "Fecha_Corrección", "")
    
    return df


def save_error_file(filename, sheets_dict):
    """
    Guarda los DataFrames actualizados en el archivo Excel
    Crea backup automático del archivo original
    Implementa lock para evitar condiciones de carrera
    """
    file_path = os.path.join(ERROR_REPOSITORY_PATH, filename)
    
    try:
        # Intentar adquirir el lock con timeout
        acquired = _file_lock.acquire(timeout=LOCK_TIMEOUT)
        if not acquired:
            st.error(f"❌ No se pudo guardar: otro usuario está modificando el archivo. Intenta en 30 segundos.")
            return False
        
        try:
            # Crear backup
            if os.path.exists(file_path):
                backup_name = f"{filename[:-5]}_backup_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                backup_path = os.path.join(ERROR_REPOSITORY_PATH, backup_name)
                import shutil
                shutil.copy(file_path, backup_path)
                st.info(f"💾 Backup creado: {backup_name}")
            
            # Guardar archivo actualizado
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                for sheet_name, df in sheets_dict.items():
                    safe_sheet_name = sheet_name[:31]
                    df.to_excel(writer, index=False, sheet_name=safe_sheet_name)
            
            return True
        finally:
            # Liberar el lock siempre
            _file_lock.release()
            
    except Exception as e:
        st.error(f"❌ Error al guardar {filename}: {e}")
        return False


def convert_coordinate_columns_to_string(df):
    """
    Convierte las columnas de coordenadas (sector, manzana, lote) a string
    para evitar que se conviertan a float
    """
    df = df.copy()
    col_lower = [c.lower() for c in df.columns]
    
    for col, col_l in zip(df.columns, col_lower):
        if "sector" in col_l or "sect" in col_l or "manzana" in col_l or "manz" in col_l or "lote" in col_l:
            # Normalizar nulos/vacíos y evitar literales "nan"/"none"
            cleaned = df[col].where(~pd.isna(df[col]), "")
            cleaned = cleaned.astype(str).str.strip()
            cleaned = cleaned.replace({"nan": "", "None": "", "none": "", "<NA>": ""})

            # Remover sufijo decimal típico de Excel (3.0 -> 3)
            cleaned = cleaned.str.replace(r'\.0$', '', regex=True)

            # Mantener solo valores no vacíos para padding
            if "lote" in col_l:
                cleaned = cleaned.apply(lambda x: x.zfill(3) if x != '' else x)
            elif "manzana" in col_l or "manz" in col_l:
                cleaned = cleaned.apply(lambda x: x.zfill(3) if x != '' else x)
            elif "sector" in col_l or "sect" in col_l:
                cleaned = cleaned.apply(lambda x: x.zfill(2) if x != '' else x)

            df[col] = cleaned
    
    return df


def sanitize_tab_label(name: str) -> str:
    """
    Sanitiza el nombre de un tab removiendo caracteres potencialmente problemáticos
    """
    if not isinstance(name, str):
        name = str(name)
    safe = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-', '(', ')'))
    safe = safe.strip()
    if not safe:
        return "tab"
    return safe[:50]


def find_coordinate_columns(df):
    """
    Busca automáticamente las columnas de sector, manzana y lote en un DataFrame.
    Retorna un diccionario con los nombres de columnas encontrados.
    """
    cols_found = {}
    col_lower = [c.lower() for c in df.columns]
    
    for col, col_l in zip(df.columns, col_lower):
        if "sector" in col_l or "sect" in col_l:
            cols_found["sector"] = col
            break
    
    for col, col_l in zip(df.columns, col_lower):
        if "manzana" in col_l or "manz" in col_l:
            cols_found["manzana"] = col
            break
    
    for col, col_l in zip(df.columns, col_lower):
        if "lote" in col_l:
            cols_found["lote"] = col
            break
    
    return cols_found


def filter_data(df, sector=None, manzana=None, lote=None):
    """Filtra un dataframe por sector, manzana y lote"""
    filtered = convert_coordinate_columns_to_string(df.copy())
    coords_cols = find_coordinate_columns(filtered)
    
    if not coords_cols:
        return filtered
    
    if sector is not None and sector != "" and "sector" in coords_cols:
        sector_col = coords_cols["sector"]
        if sector_col in filtered.columns:
            sector_str = str(sector).strip().replace('.0', '').zfill(2)
            filtered = filtered[filtered[sector_col].astype(str).str.strip() == sector_str]
    
    if manzana is not None and manzana != "" and "manzana" in coords_cols:
        manzana_col = coords_cols["manzana"]
        if manzana_col in filtered.columns:
            manzana_str = str(manzana).strip().replace('.0', '').zfill(3)
            filtered = filtered[filtered[manzana_col].astype(str).str.strip() == manzana_str]
    
    if lote is not None and lote != "" and "lote" in coords_cols:
        lote_col = coords_cols["lote"]
        if lote_col in filtered.columns:
            lote_str = str(lote).strip().replace('.0', '').zfill(3)
            filtered = filtered[filtered[lote_col].astype(str).str.strip() == lote_str]
    
    return filtered.reset_index(drop=True)


def export_to_excel(dfs_dict):
    """Exporta múltiples DataFrames a un archivo Excel con múltiples hojas"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet_name, df in dfs_dict.items():
            safe_sheet_name = sheet_name[:31]
            df.to_excel(writer, index=False, sheet_name=safe_sheet_name)
    output.seek(0)
    return output


def generate_error_statistics(error_sheets):
    """
    Genera estadísticas generales de los errores
    """
    total_errors = sum(len(df) for df in error_sheets.values())
    corrected_count = 0
    not_corrected_count = 0
    false_positive_count = 0
    
    for df in error_sheets.values():
        if "Estado" in df.columns:
            corrected_count += (df["Estado"] == "Corregido").sum()
            not_corrected_count += (df["Estado"] == "No corregido").sum()
            false_positive_count += (df["Estado"] == "Falso positivo").sum()
    
    return {
        "total_errors": total_errors,
        "corrected": corrected_count,
        "not_corrected": not_corrected_count,
        "false_positive": false_positive_count,
        "percentage_corrected": (corrected_count / total_errors * 100) if total_errors > 0 else 0
    }


def display_editable_dataframe(df, key_prefix):
    """
    Muestra un DataFrame editable con columnas de Estado como dropdown
    Coerciones de tipo para evitar StreamlitAPIException por incompatibilidad.
    """
    df_display = df.copy().reset_index(drop=True)

    # Coerciones seguras: Streamlit data_editor espera tipos compatibles con ColumnConfig
    if "Estado" in df_display.columns:
        df_display["Estado"] = df_display["Estado"].fillna("No corregido").astype(str)
        df_display["Estado"] = df_display["Estado"].replace({"nan": "No corregido", "None": "No corregido"})
        df_display["Estado"] = df_display["Estado"].apply(lambda x: x if x in ESTADOS_VALIDOS else "No corregido")

    if "Usuario_Corrigió" in df_display.columns:
        df_display["Usuario_Corrigió"] = df_display["Usuario_Corrigió"].fillna("").astype(str)
        df_display["Usuario_Corrigió"] = df_display["Usuario_Corrigió"].replace({"nan": "", "None": ""})

    if "Fecha_Corrección" in df_display.columns:
        df_display["Fecha_Corrección"] = df_display["Fecha_Corrección"].fillna("").astype(str)
        df_display["Fecha_Corrección"] = df_display["Fecha_Corrección"].replace({"nan": "", "None": ""})

    column_config = {}

    if "Estado" in df_display.columns:
        column_config["Estado"] = st.column_config.SelectboxColumn(
            "Estado",
            options=ESTADOS_VALIDOS,
            required=True
        )

    if "Usuario_Corrigió" in df_display.columns:
        column_config["Usuario_Corrigió"] = st.column_config.TextColumn(
            "Usuario_Corrigió",
            width="medium"
        )

    if "Fecha_Corrección" in df_display.columns:
        column_config["Fecha_Corrección"] = st.column_config.TextColumn(
            "Fecha_Corrección",
            width="medium"
        )

    # Mostrar el editor
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        height=500,
        column_config=column_config,
        key=key_prefix,
        disabled=[]
    )

    return edited_df


def update_user_and_date_on_change(edited_df, original_df, usuario_actual):
    """
    Actualiza usuario y fecha cuando hay cambios en el Estado.
    """
    edited_df = edited_df.reset_index(drop=True)
    original_df = original_df.reset_index(drop=True)
    
    min_length = min(len(edited_df), len(original_df))
    
    for idx in range(min_length):
        try:
            edited_estado = edited_df.iloc[idx].get("Estado")
            original_estado = original_df.iloc[idx].get("Estado")
            
            if edited_estado != original_estado:
                if pd.isna(edited_df.iloc[idx].get("Usuario_Corrigió")) or edited_df.iloc[idx].get("Usuario_Corrigió") == "":
                    edited_df.at[idx, "Usuario_Corrigió"] = usuario_actual
                
                edited_df.at[idx, "Fecha_Corrección"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            continue
    
    return edited_df


# ============================================================
# INTERFAZ PRINCIPAL
# ============================================================

def render():
    validar_acceso("Filtro de Errores")
    
    st.title("🔍 Filtro de Errores - Repositorio Dinámico")
    st.markdown("""
    Carga excels desde el Repositorio de Errores, visualiza y marca errores como corregidos.
    Los cambios se guardan en el archivo original.
    """)
    
    ensure_error_repository_exists()
    
    usuario_actual = st.session_state.get("usuario", {}).get("usuario", "Sistema")
    
    # Inicializar estados de sesión
    if "current_error_file" not in st.session_state:
        st.session_state.current_error_file = None
    if "error_sheets_cache" not in st.session_state:
        st.session_state.error_sheets_cache = {}
    if "file_modified" not in st.session_state:
        st.session_state.file_modified = False
    if "file_loaded" not in st.session_state:
        st.session_state.file_loaded = False
    if "selected_error_file" not in st.session_state:
        st.session_state.selected_error_file = None
    if "error_repository_files" not in st.session_state:
        st.session_state.error_repository_files = []
    
    st.subheader("📁 Selecciona un archivo de errores")
    
    available_files = get_available_error_files()
    removed_files = sync_error_file_session_state(available_files)

    if removed_files:
        st.info(
            "🧹 Se actualizaron los archivos disponibles y se quitaron del estado los Excel eliminados: "
            + ", ".join(removed_files)
        )
    
    if not available_files:
        st.warning("⚠️ No hay archivos Excel en la carpeta 'Repositorio_de_Errores'")
        st.info("💡 Por favor, carga un archivo Excel en la carpeta antes de continuar.")
        return
    
    # Selector sin rerun automático
    col1, col2 = st.columns([3, 1])
    
    with col1:
        error_file = st.selectbox(
            "🗂️ Archivo de errores disponibles",
            options=available_files,
            help="Selecciona el archivo Excel que deseas procesar",
            key="selected_error_file"
        )
    
    with col2:
        load_button = st.button(
            "📂 Cargar Archivo",
            type="primary",
            use_container_width=True,
            help="Click para cargar el archivo seleccionado"
        )
    
    # Cargar archivo SOLO cuando se presiona el botón
    if load_button:
        if (
            error_file != st.session_state.current_error_file
            or not st.session_state.file_loaded
            or not st.session_state.error_sheets_cache
        ):
            st.session_state.current_error_file = error_file
            
            with st.spinner(f"📂 Cargando {error_file}..."):
                loaded_sheets = load_error_file(error_file)
                st.session_state.error_sheets_cache = loaded_sheets
            
            st.session_state.file_modified = False
            st.session_state.file_loaded = bool(loaded_sheets)
        else:
            st.info("✅ El archivo ya estaba cargado")
    
    # Si no hay archivo cargado, mostrar aviso y no continuar
    if not st.session_state.file_loaded or not st.session_state.error_sheets_cache:
        st.warning("⚠️ Presiona 'Cargar Archivo' para comenzar")
        return
    
    error_sheets = st.session_state.error_sheets_cache
    
    if not error_sheets:
        st.error(f"❌ No se encontraron datos en {error_file}")
        st.error("Por favor, verifica los logs anteriores para más información")
        return
    
    # Mostrar info del archivo cargado
    st.info(f"✅ Archivo cargado: **{error_file}** | Usuario: **{usuario_actual}**")
    
    stats = generate_error_statistics(error_sheets)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📊 Total", stats["total_errors"])
    with col2:
        st.metric("✅ Corregidos", stats["corrected"])
    with col3:
        st.metric("❌ No Corregidos", stats["not_corrected"])
    with col4:
        st.metric("🔍 Falso Positivo", stats["false_positive"])
    with col5:
        st.metric("📈 Progreso", f"{stats['percentage_corrected']:.1f}%")
    
    st.markdown("---")
    
    st.subheader("🔎 Opciones de visualización")
    
    filtro_tipo = st.radio(
        "¿Cómo deseas visualizar los datos?",
        options=["hoja_especifica", "todas_las_hojas", "filtrar_por_ubicacion"],
        format_func=lambda x: {
            "hoja_especifica": "📄 Una hoja específica",
            "todas_las_hojas": "📋 Todas las hojas consolidadas",
            "filtrar_por_ubicacion": "📍 Filtrar por Sector/Manzana/Lote"
        }[x],
        horizontal=True
    )
    
    st.markdown("---")
    
    if filtro_tipo == "hoja_especifica":
        st.subheader("📄 Selecciona una Hoja para Editar")
        
        hoja_seleccionada = st.selectbox(
            "🗂️ Hoja",
            options=list(error_sheets.keys()),
            format_func=lambda x: f"{x} ({len(error_sheets[x])} registros)"
        )
        
        if hoja_seleccionada:
            df_hoja = error_sheets[hoja_seleccionada].copy().reset_index(drop=True)
            
            st.write(f"**Registros en esta hoja:** {len(df_hoja)}")
            
            if "Estado" in df_hoja.columns:
                corrected = (df_hoja["Estado"] == "Corregido").sum()
                not_corrected = (df_hoja["Estado"] == "No corregido").sum()
                false_positive = (df_hoja["Estado"] == "Falso positivo").sum()
                st.info(f"✅ Corregidos: {corrected} | ❌ No corregidos: {not_corrected} | 🔍 Falso positivo: {false_positive}")
            
            st.markdown("**Edita el estado de los errores:**")
            
            edited_df = display_editable_dataframe(df_hoja, f"editor_{hoja_seleccionada}")
            
            if not edited_df.equals(df_hoja):
                edited_df = update_user_and_date_on_change(edited_df, df_hoja, usuario_actual)
                st.session_state.file_modified = True
                error_sheets[hoja_seleccionada] = edited_df.reset_index(drop=True)
                st.success("✏️ Cambios detectados")
            
            if st.session_state.file_modified:
                if st.button("💾 Guardar Cambios", type="primary", use_container_width=True, key=f"save_{hoja_seleccionada}"):
                    if save_error_file(error_file, error_sheets):
                        st.success(f"✅ Archivo guardado correctamente: {error_file}")
                        st.session_state.file_modified = False
                    else:
                        st.error("❌ Error al guardar el archivo")
            
            st.markdown("---")
            excel_hoja = export_to_excel({hoja_seleccionada: edited_df})
            st.download_button(
                label=f"⬇️ Descargar {hoja_seleccionada}",
                data=excel_hoja,
                file_name=f"{error_file[:-5]}_{hoja_seleccionada}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    elif filtro_tipo == "todas_las_hojas":
        st.subheader("📋 Todos los Errores - Vista Consolidada")
        
        df_consolidated = pd.concat(error_sheets.values(), ignore_index=True).reset_index(drop=True)
        
        st.write(f"**Total de registros:** {len(df_consolidated)}")
        
        edited_df = display_editable_dataframe(df_consolidated, "editor_consolidado")
        
        if not edited_df.equals(df_consolidated):
            st.session_state.file_modified = True
            edited_df = update_user_and_date_on_change(edited_df, df_consolidated, usuario_actual)
        
        st.markdown("---")
        excel_all = export_to_excel({"Consolidado": edited_df})
        st.download_button(
            label="⬇️ Descargar Consolidado",
            data=excel_all,
            file_name=f"{error_file[:-5]}_consolidado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        if st.session_state.file_modified:
            if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                updated_sheets = {}
                current_idx = 0
                for sheet_name, df_original in error_sheets.items():
                    sheet_len = len(df_original)
                    updated_sheets[sheet_name] = edited_df.iloc[current_idx:current_idx + sheet_len].reset_index(drop=True)
                    current_idx += sheet_len
                
                if save_error_file(error_file, updated_sheets):
                    st.success(f"✅ Archivo guardado correctamente: {error_file}")
                    st.session_state.file_modified = False
                    st.session_state.error_sheets_cache = updated_sheets
                else:
                    st.error("❌ Error al guardar el archivo")
    
    elif filtro_tipo == "filtrar_por_ubicacion":
        st.subheader("📍 Filtro por Sector, Manzana y Lote")
        st.markdown("Selecciona la ubicación para ver solo esos errores")

        # Normalizar coordenadas en todas las hojas para evitar opciones como 3.0/4.0
        normalized_sheets = {
            name: convert_coordinate_columns_to_string(df.copy())
            for name, df in error_sheets.items()
        }

        df_consolidated = pd.concat(normalized_sheets.values(), ignore_index=True).reset_index(drop=True)
        coords_cols = find_coordinate_columns(df_consolidated)
        
        if not coords_cols:
            st.warning("⚠️ No se encontraron columnas de coordenadas (sector, manzana, lote)")
            return
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            sector_col = coords_cols.get("sector")
            if sector_col:
                sectors = sorted(
                    df_consolidated[sector_col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .replace({"": None})
                    .dropna()
                    .unique()
                )
                sector = st.selectbox(
                    "Sector",
                    options=[None] + list(sectors),
                    format_func=lambda x: f"Sector {x}" if x is not None else "Todos"
                )
            else:
                sector = None
        
        temp_df = df_consolidated.copy()
        if sector is not None and sector_col:
            temp_df = temp_df[temp_df[sector_col].astype(str) == str(sector)]
        
        with col2:
            manzana_col = coords_cols.get("manzana")
            if manzana_col:
                manzanas = sorted(
                    temp_df[manzana_col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .replace({"": None})
                    .dropna()
                    .unique()
                )
                manzana = st.selectbox(
                    "Manzana",
                    options=[None] + list(manzanas),
                    format_func=lambda x: f"Manzana {x}" if x is not None else "Todas"
                )
            else:
                manzana = None
        
        temp_df2 = df_consolidated.copy()
        if sector is not None and sector_col:
            temp_df2 = temp_df2[temp_df2[sector_col].astype(str) == str(sector)]
        if manzana is not None and manzana_col:
            temp_df2 = temp_df2[temp_df2[manzana_col].astype(str) == str(manzana)]
        
        with col3:
            lote_col = coords_cols.get("lote")
            if lote_col:
                lotes = sorted(
                    temp_df2[lote_col]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .replace({"": None})
                    .dropna()
                    .unique()
                )
                lote = st.selectbox(
                    "Lote",
                    options=[None] + list(lotes),
                    format_func=lambda x: f"Lote {x}" if x is not None else "Todos"
                )
            else:
                lote = None
        
        filtered_errors = {}
        for error_name, df_error in normalized_sheets.items():
            df_filtered = filter_data(df_error, sector, manzana, lote)
            if not df_filtered.empty:
                filtered_errors[error_name] = df_filtered
        
        if not filtered_errors:
            st.warning("⚠️ No hay registros con los criterios seleccionados")
        else:
            total_filtered = sum(len(df) for df in filtered_errors.values())
            st.success(f"✅ Se encontraron {total_filtered} predio(s) con error(es)")
            
            st.subheader("📊 Resumen de Errores")
            resumen_data = {
                "Tipo de Error": list(filtered_errors.keys()),
                "Cantidad": [len(df) for df in filtered_errors.values()]
            }
            resumen_df = pd.DataFrame(resumen_data)
            st.dataframe(resumen_df, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            tabs = st.tabs([f"🔴 {sanitize_tab_label(name)} ({len(filtered_errors[name])})" 
                           for name in filtered_errors.keys()])
            
            for tab, (error_name, df_filtered) in zip(tabs, filtered_errors.items()):
                with tab:
                    st.markdown(f"### {error_name}")
                    st.write(f"**Registros:** {len(df_filtered)}")
                    
                    df_filtered_reset = df_filtered.reset_index(drop=True)
                    edited_df = display_editable_dataframe(df_filtered_reset, f"editor_filtered_{error_name}")
                    
                    if not edited_df.equals(df_filtered_reset):
                        edited_df = update_user_and_date_on_change(edited_df, df_filtered_reset, usuario_actual)
                        st.session_state.file_modified = True
                        error_sheets[error_name] = edited_df.reset_index(drop=True)
                    
                    excel_data = export_to_excel({error_name: edited_df})
                    st.download_button(
                        label=f"⬇️ Descargar {error_name}",
                        data=excel_data,
                        file_name=f"{error_file[:-5]}_{error_name}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key=f"download_{error_name}"
                    )
            
            # Crear un archivo con los errores filtrados
            if filtered_errors:
                sheets_for_export = {}
                seen = {}
                for name, df in filtered_errors.items():
                    safe = sanitize_tab_label(name)[:31]
                    if safe in seen:
                        seen[safe] += 1
                        safe = f"{safe}_{seen[safe]}"
                    else:
                        seen[safe] = 0
                    sheets_for_export[safe] = df.reset_index(drop=True)
                
                if sheets_for_export:
                    st.markdown("---")
                    st.subheader("⬇️ Descargar todo lo filtrado")
                    excel_filtrados = export_to_excel(sheets_for_export)
                    st.download_button(
                        label=f"⬇️ Descargar Excel (Filtrados por ubicación)",
                        data=excel_filtrados,
                        file_name=f"{error_file[:-5]}_filtrados_{str(sector) if sector else 'todos'}_{str(manzana) if manzana else 'todos'}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="download_consolidado_filtrados"
                    )
            
            if st.session_state.file_modified:
                st.markdown("---")
                if st.button("💾 Guardar Todos los Cambios", type="primary", use_container_width=True, key="save_all_filtered"):
                    if save_error_file(error_file, error_sheets):
                        st.success(f"✅ Archivo guardado: {error_file}")
                        st.session_state.file_modified = False
                    else:
                        st.error("❌ Error al guardar el archivo")
    
    st.markdown("---")
    with st.expander("ℹ️ Información Técnica"):
        st.write(f"**Archivo actual:** {error_file}")
        st.write(f"**Ubicación:** {ERROR_REPOSITORY_PATH}/")
        st.write(f"**Usuario actual:** {usuario_actual}")
        st.write(f"**Hojas cargadas:** {len(error_sheets)}")
        st.write(f"**Estado de guardado:** {'⚠️ Cambios sin guardar' if st.session_state.file_modified else '✅ Todo guardado'}")
        
        for sheet_name, df in error_sheets.items():
            corrected = (df["Estado"] == "Corregido").sum() if "Estado" in df.columns else 0
            false_positive = (df["Estado"] == "Falso positivo").sum() if "Estado" in df.columns else 0
            total = len(df)
            st.write(f"  - **{sheet_name}:** {total} registros ({corrected} corregidos, {false_positive} falso positivo)")
