import streamlit as st
import pandas as pd
import os
import requests
import importlib.util
from io import BytesIO
from datetime import datetime
from permisos import validar_acceso

# ======================================================
# Configuración del repositorio GitHub (SOLO PARA RENTAS)
# ======================================================
GITHUB_OWNER = "formtpz"          
GITHUB_REPO = "TPZ-Juridicos-Peru"              
GITHUB_BRANCH = "main"               
RENTAS_FOLDER = "Rentas_resumidos"   

# Directorio local para las reglas de validación
REGLAS_DIR = "Reglas" # Asegúrate de que el nombre de la carpeta coincida (Reglas o reglas)

# ======================================================
# Funciones para obtener RENTAS desde GitHub
# ======================================================
@st.cache_data(ttl=300)
def obtener_lista_rentas():
    """
    Obtiene la lista de archivos Excel del directorio de rentas en GitHub.
    """
    url_api = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{RENTAS_FOLDER}?ref={GITHUB_BRANCH}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    try:
        respuesta = requests.get(url_api, headers=headers)
        if respuesta.status_code == 200:
            archivos = respuesta.json()
            return [
                {"name": f["name"], "download_url": f["download_url"]}
                for f in archivos
                if f["name"].endswith(".xlsx") or f["name"].endswith(".xls")
            ]
        else:
            st.error(f"Error al acceder a la carpeta de rentas en GitHub (código {respuesta.status_code}).")
            return []
    except Exception as e:
        st.error(f"Error de conexión con GitHub: {e}")
        return []

def obtener_rentas(url_raw):
    """
    Descarga el archivo de rentas seleccionado.
    """
    try:
        return pd.read_excel(url_raw)
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo de rentas: {e}")
        return None

# ======================================================
# Ejecución de reglas (Lectura LOCAL)
# ======================================================
def cargar_y_ejecutar_reglas(dataframes):
    """
    Lee todos los archivos .py locales en REGLAS_DIR y los ejecuta automáticamente.
    """
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
            # Carga dinámica local
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
    Sube los archivos locales de **Unidades Administrativas** e **Ingresos**.
    El archivo de **Rentas** se selecciona directamente desde el repositorio de la nube.
    Todas las reglas del sistema se ejecutarán automáticamente.
    """)

    # 1. Obtener archivos de Rentas para el menú desplegable
    lista_rentas = obtener_lista_rentas()
    nombres_rentas = [r["name"] for r in lista_rentas]

    archivo_rentas_seleccionado = st.selectbox(
        "📂 Selecciona el archivo de Rentas (Desde GitHub)",
        options=nombres_rentas,
        index=0 if nombres_rentas else None,
        help="Elige la base de rentas contra la cual quieres cruzar la información."
    )

    st.markdown("---")

    # 2. Carga de archivos locales
    col1, col2 = st.columns(2)
    with col1:
        archivo_unidades = st.file_uploader("📂 Reporte de Unidades Administrativas", type=["xlsx", "xls"], key="main_unidades")
    with col2:
        archivo_ingresos = st.file_uploader("📂 Reporte de Ingresos", type=["xlsx", "xls"], key="main_ingresos")

    # Botón de ejecución
    if st.button("🚀 Ejecutar todas las validaciones", type="primary", use_container_width=True):
        if not archivo_unidades or not archivo_ingresos:
            st.error("Es necesario cargar ambos archivos locales (Unidades e Ingresos).")
            return
            
        if not archivo_rentas_seleccionado:
            st.error("No se ha seleccionado un archivo de Rentas válido.")
            return

        url_rentas_seleccionado = next(r["download_url"] for r in lista_rentas if r["name"] == archivo_rentas_seleccionado)

        dataframes = {}
        
        # Lectura de DataFrames
        with st.spinner("Leyendo archivos locales..."):
            try:
                dataframes['unidades'] = pd.read_excel(archivo_unidades)
                dataframes['ingresos'] = pd.read_excel(archivo_ingresos)
            except Exception as e:
                st.error(f"Error al leer archivos locales: {e}")
                return

        with st.spinner(f"📥 Descargando '{archivo_rentas_seleccionado}' desde GitHub..."):
            df_rentas = obtener_rentas(url_rentas_seleccionado)
            if df_rentas is not None:
                dataframes['rentas'] = df_rentas
            else:
                st.warning("No se pudo cargar Rentas. Las reglas relacionales podrían fallar.")

        # Ejecutar reglas
        st.markdown("---")
        st.subheader("⚙️ Procesando motor de reglas...")
        with st.spinner("Ejecutando validaciones catastrales..."):
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

            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                label="⬇️ Descargar reporte de errores",
                data=output,
                file_name=f"resumen_errores_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("✅ ¡Felicidades! No se encontraron errores en las validaciones ejecutadas.")
