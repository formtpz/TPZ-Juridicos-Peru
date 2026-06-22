# modulos/carga_masiva.py

import streamlit as st
import pandas as pd
from sqlalchemy import text
from db import get_engine, execute   # importamos desde db.py

def cargar_csv(tabla_name, archivo_csv, truncar=False):
    """
    Lee un archivo CSV (delimitado por ;) y lo carga en la tabla especificada.
    - tabla_name: nombre de la tabla en PostgreSQL (ej. 'rentas_vs_contribuyente')
    - archivo_csv: objeto UploadedFile de Streamlit
    - truncar: si True, elimina todos los registros existentes antes de insertar
    Retorna (exitoso, mensaje, cantidad_filas)
    """
    try:
        # 1. Leer CSV
        df = pd.read_csv(archivo_csv, delimiter=';', encoding='utf-8', dtype=str)
        if df.empty:
            archivo_csv.seek(0)
            df = pd.read_csv(archivo_csv, delimiter=';', encoding='latin-1', dtype=str)

        # Limpiar nombres de columnas: eliminar espacios, convertir a snake_case, reemplazar % por porciento
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('%', 'porciento')

        # 2. Truncar si se solicita
        if truncar:
            execute(f"TRUNCATE TABLE {tabla_name} RESTART IDENTITY CASCADE;")
            st.info(f"🗑️ Tabla {tabla_name} truncada.")

        # 3. Insertar usando pandas to_sql (append)
        # Convertir NaN a None para que se inserten como NULL
        df = df.where(pd.notnull(df), None)

        filas = len(df)
        engine = get_engine()
        with engine.connect() as conn:
            df.to_sql(tabla_name, con=conn, if_exists='append', index=False, method='multi')
            conn.commit()  # no es estrictamente necesario porque to_sql ya commit, pero por si acaso

        return True, f"✅ {filas} registros insertados en {tabla_name}.", filas

    except Exception as e:
        return False, f"❌ Error: {str(e)}", 0

def render():
    # Si usas autenticación, descomenta:
    # from permisos import validar_acceso
    # validar_acceso("Carga Masiva de Catastro")

    st.title("📤 Carga Masiva de Archivos CSV a PostgreSQL")
    st.markdown("Sube los tres archivos correspondientes a las tablas del sistema.")

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
                    with st.spinner(f"Cargando {tabla}..."):
                        ok, mensaje, filas = cargar_csv(tabla, archivo, truncar=truncar_global)
                        if ok:
                            st.success(mensaje)
                            st.balloons()
                        else:
                            st.error(mensaje)
            else:
                st.info("📂 Sube un archivo CSV para cargar.")

            st.divider()

    st.subheader("⚡ Carga simultánea")
    archivos_subidos = [st.session_state.get(f"upload_{tabla}") for tabla in tablas.keys()]
    if all(archivos_subidos):
        if st.button("🚀 Cargar todos los archivos", type="primary"):
            progreso = st.progress(0)
            exito_total = True
            for i, (tabla, archivo) in enumerate(zip(tablas.keys(), archivos_subidos)):
                progreso.progress((i + 1) / len(tablas), text=f"Cargando {tabla}...")
                ok, mensaje, _ = cargar_csv(tabla, archivo, truncar=truncar_global)
                if ok:
                    st.success(f"✅ {tabla}: {mensaje}")
                else:
                    st.error(f"❌ {tabla}: {mensaje}")
                    exito_total = False
            progreso.empty()
            if exito_total:
                st.balloons()
    else:
        st.info("Sube los tres archivos para usar la carga simultánea.")

    if st.button("🔍 Ver cantidad de registros en cada tabla"):
        engine = get_engine()
        with engine.connect() as conn:
            for tabla in tablas.keys():
                result = conn.execute(text(f"SELECT COUNT(*) FROM {tabla}"))
                count = result.scalar()
                st.write(f"**{tabla}**: {count} registros")
