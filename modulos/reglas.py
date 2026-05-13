import streamlit as st
import pandas as pd
import os
import requests
import importlib.util
from io import BytesIO
from datetime import datetime
from permisos import validar_acceso

# ======================================================
# Configuración del repositorio GitHub (PARA ARCHIVOS EN NUBE)
# ======================================================
GITHUB_OWNER = "formtpz"          
GITHUB_REPO = "TPZ-Juridicos-Peru"              
GITHUB_BRANCH = "main"               
RENTAS_FOLDER = "Rentas_resumidos"   

# Directorio local para las reglas de validación
REGLAS_DIR = "Reglas" 

# ======================================================
# LISTA GLOBAL DE MUNICIPIOS
# ======================================================
MUNICIPIOS = [
    "Chorrillos",
    "San Juan de Miraflores",
    "Villa El Salvador"
]

# ======================================================
# Funciones de descarga desde GitHub
# ======================================================
def obtener_rentas(municipio):
    """
    Descarga el archivo de rentas correspondiente. 
    El mapeo de qué archivo le toca a cada municipio se maneja internamente aquí.
    """
    # Mapeo interno: El usuario no interactúa con estos nombres, solo el código.
    archivos_por_municipio = {
        "Chorrillos": "RENTAS_CHORRILLOS_2025_RESUMEN.xlsx",
        "San Juan de Miraflores": "RENTAS_SJM_2025_RESUMEN.xlsx",
        "Villa El Salvador": "RENTAS_VES_2025_RESUMEN.xlsx"
    }
    
    nombre_archivo = archivos_por_municipio.get(municipio)
    
    if not nombre_archivo:
        return None
        
    url_raw = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{RENTAS_FOLDER}/{nombre_archivo}"
    
    try:
        return pd.read_excel(url_raw)
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo de rentas para {municipio}: {e}")
        return None

# ======================================================
# Ejecución de reglas (Lectura LOCAL)
# ======================================================
def cargar_y_ejecutar_reglas(dataframes):
    todos_los_errores = []
    
    if not os.path.exists(REGLAS_DIR):
        st.error(f"Error: No se encuentra la carpeta local '{REGLAS_DIR}'.")
        return []
        
    archivos_reglas = sorted([f for f in os.listdir(REGLAS_DIR) if f.endswith(".py") and f != "__init__.py"])

    if not archivos_reglas:
        st.warning(f"⚠️ No se encontraron reglas de validación en la carpeta '{REGLAS_DIR}'.")
        return []

    for archivo in archivos_reglas:
        nombre_modulo = archivo[:-3]
        ruta_archivo = os.path.join(REGLAS_DIR, archivo)
        st.text(f"▶ Ejecutando regla: {nombre_modulo}")
        
        try:
            spec = importlib.util.spec_from_file_location(nombre_modulo, ruta_archivo)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
            
            if hasattr(modulo, 'validar'):
                errores_encontrados = modulo.validar(dataframes)
                if errores_encontrados:
                    todos_los_errores.extend(errores_encontrados)
                    st.text(f"  ❌ {len(errores_encontrados)} inconsistencias.")
                else:
                    st.text(f"  ✅ Sin errores.")
            else:
                st.text(f"  ⚠️ El archivo '{archivo}' no tiene una función 'validar'.")
        except Exception as e:
            st.text(f"  ❌ Error al ejecutar '{nombre_modulo}': {e}")

    return todos_los_errores

# ======================================================
# Interfaz principal de Streamlit
# ======================================================
def render():
    validar_acceso("Reglas")   # Control de acceso Streamlit

    st.title("🔍 Validación Relacional de Insumos Catastrales")
    st.markdown("""
    Selecciona el municipio a evaluar y sube los insumos requeridos. 
    Las bases de datos externas (como Rentas) se conectarán automáticamente según tu selección.
    """)

    # 1. Selección de Municipio (Variable Global para todo el proceso)
    municipio_seleccionado = st.selectbox(
        "🏛️ Selecciona el Municipio",
        options=MUNICIPIOS,
        help="El municipio define los parámetros geográficos, normativos y las bases de datos externas a utilizar."
    )

    st.markdown("---")
    st.subheader("📂 Carga de Insumos Locales")

    # 2. Carga de archivos locales (Organizados en cuadrícula)
    col1, col2 = st.columns(2)
    with col1:
        archivo_unidades = st.file_uploader("1. Unidades Administrativas", type=["xlsx", "xls"], key="ua")
        archivo_ingresos = st.file_uploader("3. Ingresos", type=["xlsx", "xls"], key="in")
    with col2:
        archivo_construcciones = st.file_uploader("2. Construcciones", type=["xlsx", "xls"], key="co")
        archivo_ingresos_lote = st.file_uploader("4. Ingresos por Lote", type=["xlsx", "xls"], key="inlote")

    st.markdown("---")

    # Botón de ejecución
    if st.button("🚀 Ejecutar todas las validaciones", type="primary", use_container_width=True):
        
        if not archivo_unidades or not archivo_ingresos:
            st.warning("⚠️ Recuerda que algunas reglas se omitirán si no subes todos los archivos que requieren.")
            
        dataframes = {}
        
        # Guardamos el municipio en el diccionario de datos para que las reglas puedan leerlo
        dataframes['municipio'] = municipio_seleccionado
        
        # Lectura de DataFrames locales
        with st.spinner("Procesando insumos locales en memoria..."):
            try:
                if archivo_unidades: dataframes['unidades'] = pd.read_excel(archivo_unidades)
                if archivo_ingresos: dataframes['ingresos'] = pd.read_excel(archivo_ingresos)
                if archivo_construcciones: dataframes['construcciones'] = pd.read_excel(archivo_construcciones)
                if archivo_ingresos_lote: dataframes['ingresos_lote'] = pd.read_excel(archivo_ingresos_lote)
            except Exception as e:
                st.error(f"Error al leer archivos locales: {e}")
                return

        # Descarga automática de archivos de la nube
        with st.spinner(f"📥 Conectando con bases de datos de {municipio_seleccionado}..."):
            df_rentas = obtener_rentas(municipio_seleccionado)
            if df_rentas is not None:
                dataframes['rentas'] = df_rentas
            else:
                st.error("No se pudo establecer conexión con la base de rentas del municipio. Las reglas relacionales podrían fallar.")
                return

        # Ejecutar reglas
        st.markdown("---")
        st.subheader(f"⚙️ Analizando datos para {municipio_seleccionado}...")
        with st.spinner("Ejecutando motor de reglas catastrales..."):
            lista_errores = cargar_y_ejecutar_reglas(dataframes)

        # Generar Reporte
        st.markdown("---")
        if lista_errores:
            df_resumen = pd.DataFrame(lista_errores)

            columnas_finales = [
                'Nombre de la Regla', 'Sector', 'Manzana', 'Lote', 'Edifica',
                'Entrada', 'Piso', 'Unidad', 'Descripción del Error'
            ]
            cols_presentes = list(df_resumen.columns)
            cols_extras = sorted([c for c in cols_presentes if c not in columnas_finales])
            orden_definitivo = [c for c in columnas_finales if c in cols_presentes] + cols_extras
            df_resumen_ordenado = df_resumen[orden_definitivo]

            columnas_para_ordenar = [
                'Nombre de la Regla', 'Sector', 'Manzana', 'Lote',
                'Edifica', 'Entrada', 'Piso', 'Unidad'
            ]
            cols_orden_validas = [col for col in columnas_para_ordenar if col in df_resumen_ordenado.columns]
            df_resumen_ordenado = df_resumen_ordenado.sort_values(by=cols_orden_validas, ascending=True)

            st.subheader("📊 Resultado de la validación")
            st.error(f"⚠️ Se encontraron **{len(df_resumen_ordenado)} inconsistencias**.")
            st.dataframe(df_resumen_ordenado, use_container_width=True)

            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resumen_ordenado.to_excel(writer, index=False, sheet_name="Errores")
            output.seek(0)

            # El nombre del archivo ahora incluye el municipio de forma dinámica
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            nombre_descarga = f"resumen_errores_{municipio_seleccionado.replace(' ', '_')}_{timestamp}.xlsx"
            
            st.download_button(
                label="⬇️ Descargar reporte de errores",
                data=output,
                file_name=nombre_descarga,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("✅ ¡Felicidades! No se encontraron errores en las validaciones ejecutadas.")
