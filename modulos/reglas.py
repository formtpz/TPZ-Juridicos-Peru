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
        respuesta = requests.get(url_raw)
        if respuesta.status_code == 200:
            return pd.read_excel(BytesIO(respuesta.content))
        else:
            st.warning(f"No se pudo cargar el archivo de rentas (Error HTTP {respuesta.status_code}).")
            return None
    except Exception as e:
        st.warning(f"Excepción al descargar el archivo de rentas: {e}")
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
    Sube los archivos locales necesarios. El archivo de **Rentas** se selecciona y descarga 
    automáticamente desde el repositorio en la nube.
    """)

    # 1. Obtener archivos de Rentas para el menú desplegable (Conectando a GitHub)
    lista_rentas = obtener_lista_rentas()
    nombres_rentas = [r["name"] for r in lista_rentas]

    archivo_rentas_seleccionado = st.selectbox(
        "📂 Selecciona el archivo de Rentas (Nube)",
        options=nombres_rentas,
        index=0 if nombres_rentas else None,
        help="Elige la base de rentas contra la cual quieres cruzar la información."
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
            st.warning("⚠️ Recuerda que algunas reglas se omitirán si no subes todos los archivos correspondientes.")
            
        dataframes = {}
        
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

        # Descarga de Rentas si se seleccionó uno
        if archivo_rentas_seleccionado:
            url_rentas_seleccionado = next(r["download_url"] for r in lista_rentas if r["name"] == archivo_rentas_seleccionado)
            
            with st.spinner(f"📥 Descargando '{archivo_rentas_seleccionado}'..."):
                df_rentas = obtener_rentas(url_rentas_seleccionado)
                if df_rentas is not None:
                    dataframes['rentas'] = df_rentas
                    st.success(f"✅ Archivo de Rentas conectado exitosamente.")
                else:
                    st.warning("⚠️ No se pudo establecer conexión con la base de Rentas. La validación continuará, pero las reglas relacionales serán omitidas.")
        else:
            st.info("No se seleccionó archivo de Rentas. Se omitirán las validaciones relacionales.")

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

            # Nombre dinámico usando el archivo de rentas que se eligió o una etiqueta general
            nombre_etiqueta = archivo_rentas_seleccionado.replace('.xlsx', '') if archivo_rentas_seleccionado else "SinRentas"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            nombre_descarga = f"resumen_errores_{nombre_etiqueta}_{timestamp}.xlsx"
            
            st.download_button(
                label="⬇️ Descargar reporte de errores",
                data=output,
                file_name=nombre_descarga,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        else:
            st.success("✅ ¡Felicidades! No se encontraron errores en las validaciones ejecutadas.")
