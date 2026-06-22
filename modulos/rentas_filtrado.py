# modulos/carga_masiva.py

import streamlit as st
import pandas as pd
from io import StringIO
from db import get_connection   # Importamos tu función para obtener conexión psycopg2

def cargar_csv_con_copy(tabla_name, archivo_csv, truncar=False, chunksize=10000):
    """
    Carga un archivo CSV en una tabla PostgreSQL usando COPY (rápido) con chunks.
    Retorna (exito, mensaje, filas_insertadas)
    """
    try:
        # --- 1. Leer solo el header para obtener nombres de columnas ---
        try:
            df_sample = pd.read_csv(archivo_csv, delimiter=';', encoding='utf-8', nrows=0, dtype=str)
        except UnicodeDecodeError:
            archivo_csv.seek(0)
            df_sample = pd.read_csv(archivo_csv, delimiter=';', encoding='latin-1', nrows=0, dtype=str)
        
        columnas = df_sample.columns.tolist()
        # Limpiar nombres: minúsculas, espacios a guion bajo, % a 'porciento'
        columnas_clean = [
            col.strip().lower().replace(' ', '_').replace('%', 'porciento')
            for col in columnas
        ]
        
        # --- 2. Conectar y truncar si se pide ---
        conn = get_connection()
        cur = conn.cursor()
        
        if truncar:
            cur.execute(f"TRUNCATE TABLE {tabla_name} RESTART IDENTITY CASCADE;")
            conn.commit()
            st.info(f"🗑️ Tabla {tabla_name} truncada.")
        
        # --- 3. Leer el archivo en chunks y copiar cada uno ---
        archivo_csv.seek(0)
        try:
            chunk_iter = pd.read_csv(
                archivo_csv,
                delimiter=';',
                encoding='utf-8',
                chunksize=chunksize,
                dtype=str
            )
        except UnicodeDecodeError:
            archivo_csv.seek(0)
            chunk_iter = pd.read_csv(
                archivo_csv,
                delimiter=';',
                encoding='latin-1',
                chunksize=chunksize,
                dtype=str
            )
        
        total_filas = 0
        chunk_count = 0
        
        # Barra de progreso y texto de estado
        progress_bar = st.progress(0, text="⏳ Iniciando carga...")
        status_text = st.empty()
        
        for chunk in chunk_iter:
            # Asignar nombres limpios a las columnas del chunk
            chunk.columns = columnas_clean
            # Reemplazar NaN por None (para que se inserten como NULL)
            chunk = chunk.where(pd.notnull(chunk), None)
            
            # Convertir el chunk a CSV en memoria (StringIO) en formato COPY
            buffer = StringIO()
            chunk.to_csv(
                buffer,
                sep=';',
                index=False,
                header=False,
                quoting=1,          # QUOTE_ALL
                quotechar='"',
                escapechar='\\',
                na_rep=''           # los None se escriben como cadena vacía
            )
            buffer.seek(0)
            
            # Construir comando COPY
            columnas_str = ', '.join(columnas_clean)
            copy_sql = f"""
                COPY {tabla_name} ({columnas_str})
                FROM STDIN WITH (
                    FORMAT CSV,
                    DELIMITER ';',
                    QUOTE '"',
                    ESCAPE '\\',
                    NULL ''
                )
            """
            # Ejecutar COPY desde el buffer
            cur.copy_expert(sql=copy_sql, file=buffer)
            conn.commit()
            
            filas_chunk = len(chunk)
            total_filas += filas_chunk
            chunk_count += 1
            
            # Actualizar progreso (asumimos máximo 100 chunks para la barra)
            progress = min(0.99, chunk_count / 100)
            progress_bar.progress(
                progress,
                text=f"⏳ Procesando chunk {chunk_count}... {total_filas} filas"
            )
            status_text.text(f"✅ Cargadas {total_filas} filas hasta ahora...")
        
        # Finalizar barra
        progress_bar.progress(1.0, text="✅ ¡Carga completada!")
        status_text.text(f"✅ Total de {total_filas} filas insertadas en {tabla_name}.")
        
        cur.close()
        conn.close()
        
        return True, f"✅ {total_filas} registros insertados en {tabla_name} usando COPY.", total_filas
    
    except Exception as e:
        return False, f"❌ Error: {str(e)}", 0


def render():
    """
    Interfaz principal para cargar los 3 archivos CSV a las tablas.
    """
    # Si usas autenticación, descomenta la siguiente línea:
    # from permisos import validar_acceso
    # validar_acceso("Carga Masiva de Catastro")
    
    st.title("📤 Carga Masiva de Archivos CSV a PostgreSQL")
    st.markdown(
        """
        Sube los tres archivos CSV correspondientes a las tablas del sistema.
        La carga se realiza usando `COPY` de PostgreSQL para mayor velocidad.
        """
    )
    
    # Definición de las tablas
    tablas = {
        "rentas_vs_contribuyente": {
            "label": "📄 Tabla 1: Contribuyentes",
            "help": "Archivo CSV con distrito, código contribuyente, apellidos, etc."
        },
        "rentas_vs_construcciones": {
            "label": "🏗️ Tabla 2: Construcciones",
            "help": "Archivo CSV con datos de construcciones por nivel."
        },
        "rentas_vs_predio_urbano": {
            "label": "🏠 Tabla 3: Predios Urbanos",
            "help": "Archivo CSV con datos completos de predios urbanos."
        }
    }
    
    # Checkbox global para truncar
    truncar_global = st.checkbox(
        "🗑️ Truncar (eliminar datos existentes) antes de cargar",
        value=False
    )
    
    st.divider()
    
    # --- Para cada tabla, mostrar su uploader y botón de carga ---
    for tabla, config in tablas.items():
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                archivo = st.file_uploader(
                    config["label"],
                    type=["csv"],
                    accept_multiple_files=False,
                    key=f"upload_{tabla}",
                    help=config["help"]
                )
            with col2:
                if archivo is not None:
                    st.caption(f"📏 Tamaño: {archivo.size / 1024:.1f} KB")
            
            # Botón de carga individual
            if archivo is not None:
                if st.button(f"⬆️ Cargar {tabla}", key=f"btn_{tabla}"):
                    with st.spinner(f"Cargando {tabla}..."):
                        ok, mensaje, filas = cargar_csv_con_copy(
                            tabla,
                            archivo,
                            truncar=truncar_global
                        )
                        if ok:
                            st.success(mensaje)
                            st.balloons()
                        else:
                            st.error(mensaje)
            else:
                st.info("📂 Sube un archivo CSV para cargar.")
            
            st.divider()
    
    # --- Carga simultánea (si los 3 archivos están subidos) ---
    st.subheader("⚡ Carga simultánea")
    archivos_subidos = [st.session_state.get(f"upload_{tabla}") for tabla in tablas.keys()]
    if all(archivos_subidos):
        if st.button("🚀 Cargar todos los archivos", type="primary"):
            progreso = st.progress(0, text="Iniciando carga simultánea...")
            exito_total = True
            for i, (tabla, archivo) in enumerate(zip(tablas.keys(), archivos_subidos)):
                progreso.progress(
                    (i + 0.5) / len(tablas),
                    text=f"Cargando {tabla}..."
                )
                ok, mensaje, _ = cargar_csv_con_copy(
                    tabla,
                    archivo,
                    truncar=truncar_global
                )
                if ok:
                    st.success(f"✅ {tabla}: {mensaje}")
                else:
                    st.error(f"❌ {tabla}: {mensaje}")
                    exito_total = False
            progreso.progress(1.0, text="Carga finalizada")
            if exito_total:
                st.balloons()
    else:
        st.info("📌 Sube los tres archivos para usar la carga simultánea.")
    
    # --- Opcional: Ver cantidad de registros ---
    if st.button("🔍 Ver cantidad de registros en cada tabla"):
        try:
            conn = get_connection()
            cur = conn.cursor()
            for tabla in tablas.keys():
                cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                count = cur.fetchone()[0]
                st.write(f"**{tabla}**: {count} registros")
            cur.close()
            conn.close()
        except Exception as e:
            st.error(f"Error al consultar: {e}")
