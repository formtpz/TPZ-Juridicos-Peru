# modulos/carga_masiva.py

import streamlit as st
import pandas as pd
from io import StringIO
from db import get_connection

def cargar_csv_con_copy(tabla_name, archivo_csv, truncar=False, chunksize=10000):
    try:
        # Leer header para columnas
        try:
            df_sample = pd.read_csv(archivo_csv, delimiter=';', encoding='utf-8', nrows=0, dtype=str)
        except UnicodeDecodeError:
            archivo_csv.seek(0)
            df_sample = pd.read_csv(archivo_csv, delimiter=';', encoding='latin-1', nrows=0, dtype=str)
        
        columnas = df_sample.columns.tolist()
        columnas_clean = [col.strip().lower().replace(' ', '_').replace('%', 'porciento') for col in columnas]
        
        conn = get_connection()
        cur = conn.cursor()
        
        if truncar:
            cur.execute(f"TRUNCATE TABLE {tabla_name} RESTART IDENTITY CASCADE;")
            conn.commit()
            st.info(f"🗑️ Tabla {tabla_name} truncada.")
        
        archivo_csv.seek(0)
        try:
            chunk_iter = pd.read_csv(archivo_csv, delimiter=';', encoding='utf-8', chunksize=chunksize, dtype=str)
        except UnicodeDecodeError:
            archivo_csv.seek(0)
            chunk_iter = pd.read_csv(archivo_csv, delimiter=';', encoding='latin-1', chunksize=chunksize, dtype=str)
        
        total_filas = 0
        chunk_count = 0
        progress_bar = st.progress(0, text="Iniciando carga...")
        status_text = st.empty()
        
        for chunk in chunk_iter:
            chunk.columns = columnas_clean
            chunk = chunk.where(pd.notnull(chunk), None)
            
            buffer = StringIO()
            chunk.to_csv(buffer, sep=';', index=False, header=False, quoting=1, quotechar='"', escapechar='\\', na_rep='')
            buffer.seek(0)
            
            columnas_str = ', '.join(columnas_clean)
            copy_sql = f"COPY {tabla_name} ({columnas_str}) FROM STDIN WITH (FORMAT CSV, DELIMITER ';', QUOTE '\"', ESCAPE '\\', NULL '')"
            cur.copy_expert(sql=copy_sql, file=buffer)
            conn.commit()
            
            filas_chunk = len(chunk)
            total_filas += filas_chunk
            chunk_count += 1
            
            progress = min(0.99, chunk_count / 100)
            progress_bar.progress(progress, text=f"Procesando chunk {chunk_count}... {total_filas} filas")
            status_text.text(f"✅ Cargadas {total_filas} filas hasta ahora...")
        
        progress_bar.progress(1.0, text="¡Carga completada!")
        status_text.text(f"✅ Total de {total_filas} filas insertadas en {tabla_name}.")
        
        cur.close()
        conn.close()
        return True, f"✅ {total_filas} registros insertados en {tabla_name}.", total_filas
    
    except Exception as e:
        return False, f"❌ Error: {str(e)}", 0

def render():
    # ... (código de la interfaz igual, pero llamando a cargar_csv_con_copy)
    # ...
