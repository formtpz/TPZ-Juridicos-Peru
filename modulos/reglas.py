import streamlit as st
import pandas as pd
import os
import requests
import importlib.util
import types
from io import BytesIO
from datetime import datetime
from permisos import validar_acceso

# ======================================================
# Configuración del repositorio GitHub (archivos estáticos)
# ======================================================
GITHUB_OWNER = "formtpz"          # Dueño del repositorio
GITHUB_REPO = "TPZ-Juridicos-Peru"              # Nombre del repositorio
GITHUB_BRANCH = "main"               # Rama de donde leer
REGLA_FOLDER = "Reglas"              # Carpeta dentro del repo con las reglas .py
RENTAS_FOLDER = "Rentas_resumidos"   # Carpeta dentro del repo con los archivos de rentas

# ======================================================
# Funciones auxiliares para obtener datos desde GitHub
# ======================================================
@st.cache_data(ttl=300) # Guarda en caché por 5 minutos para no saturar la API de GitHub
def obtener_lista_reglas():
    """
    Obtiene la lista de archivos .py del directorio de reglas en GitHub.
    Retorna una lista de diccionarios con 'name' y 'download_url'.
    """
    url_api = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{REGLA_FOLDER}?ref={GITHUB_BRANCH}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    try:
        respuesta = requests.get(url_api, headers=headers)
        if respuesta.status_code == 200:
            archivos = respuesta.json()
            return [
                {"name": f["name"], "download_url": f["download_url"]}
                for f in archivos
                if f["name"].endswith(".py") and f["name"] != "__init__.py"
            ]
        else:
            st.error(f"Error al acceder a la carpeta de reglas en GitHub (código {respuesta.status_code}).")
            return []
    except Exception as e:
        st.error(f"Error de conexión con GitHub: {e}")
        return []

@st.cache_data(ttl=300)
def obtener_lista_rentas():
    """
    Obtiene la lista de archivos Excel del directorio de rentas en GitHub.
    Retorna una lista de diccionarios con 'name' y 'download_url'.
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
                # Filtramos solo archivos Excel
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
    Descarga el archivo de rentas específico desde GitHub y lo carga en un DataFrame.
    """
    try:
        return pd.read_excel(url_raw)
    except Exception as e:
        st.warning(f"No se pudo cargar el archivo de rentas desde GitHub: {e}")
        return None

# ======================================================
# Ejecución de reglas (adaptada a Streamlit)
# ======================================================
def cargar_y_ejecutar_reglas(dataframes):
    """
    Recibe el diccionario de dataframes y ejecuta las reglas obtenidas desde GitHub.
    Devuelve la lista de todos los errores encontrados.
    """
    todos_los_errores = []
    reglas = obtener_lista_reglas()

    if not reglas:
        st.warning(f"⚠️ No se encontraron reglas de validación en '{REGLA_FOLDER}' del repositorio.")
        return []

    for regla in reglas:
        nombre = regla["name"]
        url = regla["download_url"]
        st.text(f"▶ Ejecutando regla: {nombre[:-3]}")  # Quitamos extensión .py
        try:
            # Descargar código fuente de la regla
            codigo = requests.get(url).text

            # Crear un módulo en memoria y ejecutarlo
            modulo = types.ModuleType(nombre)
            exec(codigo, modulo.__dict__)

            if hasattr(modulo, 'validar'):
                errores_encontrados = modulo.validar(dataframes)
                if errores_encontrados:
                    todos_los_errores.extend(errores_encontrados)
                    st.text(f"  ❌ {len(errores_encontrados)} inconsistencias encontradas.")
                else:
                    st.text(f"  ✅ Sin errores.")
            else:
                st.text(f"  ⚠️ La regla '{nombre}' no contiene una función 'validar'.")
        except Exception as e:
            st.text(f"  ❌ Error al ejecutar '{nombre[:-3]}': {e}")

    return todos_los_errores

# ======================================================
# Interfaz principal de Streamlit
# ======================================================
def render():
    validar_acceso("Reglas")   # Control de acceso Streamlit similar a depuracion.py

    st.title("🔍 Validación Relacional de Insumos Catastrales")
    st.markdown("""
    Sube los archivos de **Unidades Administrativas** e **Ingresos**.
    
    El archivo de **Rentas** se selecciona desde el repositorio y las **reglas de validación** se obtienen automáticamente.
    """)

    # 1. Obtener archivos de Rentas disponibles para el desplegable
    lista_rentas = obtener_lista_rentas()
    nombres_rentas = [r["name"] for r in lista_rentas]

    # Desplegable para seleccionar el archivo de Rentas
    archivo_rentas_seleccionado = st.selectbox(
        "📂 Selecciona el archivo de Rentas (Desde GitHub)",
        options=nombres_rentas,
        index=0 if nombres_rentas else None,
        help="Elige el archivo de rentas contra el cual quieres cruzar la información."
    )

    st.markdown("---")

    # Carga de archivos (inputs del usuario)
    archivo_unidades = st.file_uploader("📂 Reporte de Unidades Administrativas (Local)", type=["xlsx", "xls"],
                                        key="main_unidades")
    archivo_ingresos = st.file_uploader("📂 Reporte de Ingresos (Local)", type=["xlsx", "xls"],
                                        key="main_ingresos")

    # Botón para ejecutar la validación
    if st.button("🚀 Ejecutar validación", type="primary"):
        if not archivo_unidades or not archivo_ingresos:
            st.error("Es necesario cargar ambos archivos locales (Unidades e Ingresos).")
            return
            
        if not archivo_rentas_seleccionado:
            st.error("No se ha seleccionado un archivo de Rentas válido del repositorio.")
            return

        # Buscar la URL de descarga correspondiente al archivo seleccionado
        url_rentas_seleccionado = next(r["download_url"] for r in lista_rentas if r["name"] == archivo_rentas_seleccionado)

        # 1. Cargar los DataFrames desde los uploaders
        dataframes = {}
        try:
            dataframes['unidades'] = pd.read_excel(archivo_unidades)
            st.success("✅ Archivo de Unidades cargado")
        except Exception as e:
            st.error(f"Error al leer Unidades: {e}")
            return

        try:
            dataframes['ingresos'] = pd.read_excel(archivo_ingresos)
            st.success("✅ Archivo de Ingresos cargado")
        except Exception as e:
            st.error(f"Error al leer Ingresos: {e}")
            return

        # 2. Cargar Rentas seleccionadas desde GitHub
        with st.spinner(f"📥 Descargando '{archivo_rentas_seleccionado}' desde GitHub..."):
            df_rentas = obtener_rentas(url_rentas_seleccionado)
            if df_rentas is not None:
                dataframes['rentas'] = df_rentas
                st.success(f"✅ Archivo de Rentas cargado exitosamente")
            else:
                st.warning("⚠️ No se pudo cargar Rentas. La validación continuará sin ese archivo (si las reglas lo requieren, pueden fallar).")

        # 3. Ejecutar reglas
        st.markdown("---")
        st.subheader("⚙️ Procesando reglas de validación...")
        with st.spinner("Ejecutando reglas..."):
            lista_errores = cargar_y_ejecutar_reglas(dataframes)

        # 4. Mostrar resultado y permitir descarga
        st.markdown("---")
        if lista_errores:
            df_resumen = pd.DataFrame(lista_errores)

            # Ordenar columnas (mismo criterio que el original)
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
            st.write(f"Se encontraron **{len(df_resumen_ordenado)} errores**.")
            st.dataframe(df_resumen_ordenado.head(20), use_container_width=True)

            # Preparar descarga en Excel (en memoria)
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_resumen_ordenado.to_excel(writer, index=False, sheet_name="Errores")
            output.seek(0)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button(
                label="⬇️ Descargar reporte de errores",
                data=output,
                file_name=f"resumen_errores_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.success("✅ No se encontraron errores en las validaciones ejecutadas.")
            st.info("No hay reporte para descargar.")

# Fin del módulo
