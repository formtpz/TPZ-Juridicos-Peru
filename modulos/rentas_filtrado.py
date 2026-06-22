# modulos/carga_masiva.py

import streamlit as st
import pandas as pd
from io import StringIO
from db import get_connection
import unicodedata

# ========= FUNCIÓN PARA LIMPIAR NOMBRES DE COLUMNAS =========
def clean_column_name(col: str) -> str:
    """
    Convierte un nombre de columna a snake_case válido en SQL.
    Ejemplos:
        "Código Contribuyente" -> "codigo_contribuyente"
        "Nro. Documento"       -> "nro_documento"
        "Género"               -> "genero"
    """
    # 1. Convertir a minúsculas
    col = col.lower().strip()
    # 2. Reemplazar tildes (normalizar a ASCII)
    col = unicodedata.normalize('NFKD', col).encode('ascii', 'ignore').decode('ascii')
    # 3. Reemplazar espacios, puntos y otros caracteres especiales por '_'
    col = col.replace(' ', '_').replace('.', '_').replace('-', '_')
    # 4. Eliminar cualquier carácter que no sea alfanumérico o '_'
    col = ''.join(c for c in col if c.isalnum() or c == '_')
    # 5. Evitar guiones bajos múltiples
    while '__' in col:
        col = col.replace('__', '_')
    return col

# ========= FUNCIÓN PRINCIPAL DE CARGA CON COPY =========
def cargar_csv_con_copy(tabla_name, archivo_csv, truncar=False, chunksize=10000):
    """
    Carga un archivo CSV usando COPY de PostgreSQL con chunks y barra de progreso.
    """
    try:
        # 1. Leer el header para obtener los nombres originales
        try:
            df_sample = pd.read_csv(archivo_csv, delimiter=';', encoding='utf-8', nrows=0, dtype=str)
        except UnicodeDecodeError:
            archivo_csv.seek(0)
            df_sample = pd.read_csv(archivo_csv, delimiter=';', encoding='latin-1', nrows=0, dtype=str)

        # Limpiar nombres de columnas
        columnas_originales = df_sample.columns.tolist()
        columnas_limpias = [clean_column_name(col) for col in columnas_originales]
        
        # 2. Conectar a la BD
        conn = get_connection()
        cur = conn.cursor()
        
        # 3. Truncar si se solicita
        if truncar:
            cur.execute(f"TRUNCATE TABLE {tabla_name} RESTART IDENTITY CASCADE;")
            conn.commit()
            st.info(f"🗑️ Tabla {tabla_name} truncada.")
        
        # 4. Leer el CSV en chunks
        archivo_csv.seek(0)
        try:
            chunk_iter = pd.read_csv(
                archivo_csv, 
                delimiter=';', 
                encoding='utf-8', 
                chunksize=chunksize, 
                dtype=str,
                quotechar='"'
            )
        except UnicodeDecodeError:
            archivo_csv.seek(0)
            chunk_iter = pd.read_csv(
                archivo_csv, 
                delimiter=';', 
                encoding='latin-1', 
                chunksize=chunksize, 
                dtype=str,
                quotechar='"'
            )
        
        # 5. Procesar cada chunk
        total_filas = 0
        chunk_count = 0
        
        progress_bar = st.progress(0, text="Iniciando carga...")
        status_text = st.empty()
        
        for chunk in chunk_iter:
            # Asignar nombres limpios a las columnas
            chunk.columns = columnas_limpias
            
            # Reemplazar NaN por None (NULL en BD)
            chunk = chunk.where(pd.notnull(chunk), None)
            
            # Escribir chunk a un buffer CSV en memoria (formato COPY)
            buffer = StringIO()
            chunk.to_csv(
                buffer, 
                sep=';', 
                index=False, 
                header=False, 
                quoting=1,          # QUOTE_ALL para manejar comillas internas
                quotechar='"',
                escapechar='\\',
                na_rep=''           # valores nulos se escriben como cadena vacía
            )
            buffer.seek(0)
            
            # Construir comando COPY
            columnas_str = ', '.join(columnas_limpias)
            copy_sql = f"""
                COPY {tabla_name} ({columnas_str}) 
                FROM STDIN WITH (FORMAT CSV, DELIMITER ';', QUOTE '"', ESCAPE '\\', NULL '')
            """
            
            # Ejecutar COPY
            cur.copy_expert(sql=copy_sql, file=buffer)
            conn.commit()
            
            # Actualizar estadísticas
            filas_chunk = len(chunk)
            total_filas += filas_chunk
            chunk_count += 1
            
            # Actualizar barra de progreso (estimada basada en 100 chunks máx)
            progress = min(0.99, chunk_count / 100)
            progress_bar.progress(progress, text=f"Chunk {chunk_count} - {total_filas} filas cargadas")
            status_text.text(f"✅ Cargadas {total_filas} filas hasta ahora...")
        
        # Finalizar
        progress_bar.progress(1.0, text="¡Carga completada!")
        status_text.text(f"✅ Total de {total_filas} filas insertadas en {tabla_name}.")
        
        cur.close()
        conn.close()
        
        return True, f"✅ {total_filas} registros insertados en {tabla_name} usando COPY.", total_filas
    
    except Exception as e:
        return False, f"❌ Error: {str(e)}", 0

# ========= RENDER DE LA INTERFAZ STREAMLIT =========
def render():
    # Si usas autenticación, descomenta:
    # from permisos import validar_acceso
    # validar_acceso("Carga Masiva de Catastro")

    st.title("📤 Carga Masiva de Archivos CSV a PostgreSQL")
    st.markdown("Sube los tres archivos correspondientes a las tablas del sistema.")
    st.caption("Los nombres de columna se limpiarán automáticamente (tildes, puntos, espacios).")

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

    truncar_global = st.checkbox("🗑️ Truncar (eliminar datos existentes) antes de cargar", value=False)
    st.divider()

    # Uploaders individuales
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
                    st.caption(f"Tamaño: {archivo.size / 1024:.1f} KB")

            if archivo is not None:
                if st.button(f"⬆️ Cargar {tabla}", key=f"btn_{tabla}"):
                    with st.spinner(f"Cargando {tabla}... Esto puede tomar unos segundos."):
                        ok, mensaje, filas = cargar_csv_con_copy(tabla, archivo, truncar=truncar_global)
                        if ok:
                            st.success(mensaje)
                            st.balloons()
                        else:
                            st.error(mensaje)
            else:
                st.info("📂 Sube un archivo CSV para cargar.")

            st.divider()

    # Carga simultánea
    st.subheader("⚡ Carga simultánea")
    archivos_subidos = [st.session_state.get(f"upload_{tabla}") for tabla in tablas.keys()]
    if all(archivos_subidos):
        if st.button("🚀 Cargar todos los archivos", type="primary"):
            progreso = st.progress(0, text="Iniciando...")
            exito_total = True
            resultados = []
            for i, (tabla, archivo) in enumerate(zip(tablas.keys(), archivos_subidos)):
                progreso.progress((i + 1) / len(tablas), text=f"Cargando {tabla}...")
                ok, mensaje, _ = cargar_csv_con_copy(tabla, archivo, truncar=truncar_global)
                resultados.append(f"{tabla}: {'✅' if ok else '❌'} {mensaje}")
                if not ok:
                    exito_total = False
            progreso.empty()
            for res in resultados:
                if "✅" in res:
                    st.success(res)
                else:
                    st.error(res)
            if exito_total:
                st.balloons()
    else:
        st.info("Sube los tres archivos para usar la carga simultánea.")

    # Consultar conteo de registros
    if st.button("🔍 Ver cantidad de registros en cada tabla"):
        conn = get_connection()
        cur = conn.cursor()
        for tabla in tablas.keys():
            cur.execute(f"SELECT COUNT(*) FROM {tabla}")
            count = cur.fetchone()[0]
            st.write(f"**{tabla}**: {count} registros")
        cur.close()
        conn.close()
