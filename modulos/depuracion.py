# modulos/depuracion.py
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from io import BytesIO
from permisos import validar_acceso

# --- Credenciales fijas ---
USER = "gct_1"
PASSWORD = "5UWJpWHxsBv091t"
HOST = "192.168.4.9"
PORT = "5432"
DB_NAME = "COFOPRI"

def conectar_bd():
    url = f"postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}"
    return create_engine(url)

def parse_manzanas_input(texto: str):
    if not texto or not texto.strip():
        return set()
    texto = texto.replace(" ", "")
    partes = texto.split(",")
    numeros = set()
    for parte in partes:
        if "-" in parte:
            try:
                inicio, fin = parte.split("-")
                numeros.update(range(int(inicio), int(fin) + 1))
            except:
                continue
        else:
            try:
                numeros.add(int(parte))
            except:
                continue
    return numeros

def render():
    validar_acceso("Depuración de Datos")

    st.title("🧹 Depuración de Datos - Catastro")

    # --- Selector de modo ---
    modo = st.radio("Selecciona el modo de filtrado:", ["Sector/Manzana", "Polígono (BD)"])

    # --- Subida múltiple de archivos ---
    archivo_list = st.file_uploader(
        "📂 Cargar uno o varios archivos Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="depuracion_catastro"
    )

    if not archivo_list:
        st.info("📌 Sube al menos un archivo Excel con la columna catastral para comenzar.")
        return

    # --- Configuración extra para modo Polígono ---
    poligono = None
    if modo == "Polígono (BD)":
        poligono = st.text_input("Ingrese el código de polígono (ej: SJM-04)")

    # --- Procesar cada archivo en lote ---
    for archivo in archivo_list:
        st.markdown(f"### 📑 Procesando archivo: **{archivo.name}**")

        try:
            df = pd.read_excel(archivo, engine="openpyxl")

            # Buscar columna catastral
            col_cat = None
            for col in df.columns:
                if "código de referencia catastral" in col.lower():
                    col_cat = col
                    break
            if not col_cat:
                st.error("❌ No se encontró la columna 'Código de Referencia Catastral'.")
                continue

            df[col_cat] = df[col_cat].astype(str).str.strip()

            # Extracción sector/manzana/lote
            df["Sector"] = df[col_cat].apply(lambda c: c[6:8] if len(c) >= 8 else None)
            df["Manzana"] = df[col_cat].apply(lambda c: c[8:11] if len(c) >= 11 else None)
            df["Lote"] = df[col_cat].apply(lambda c: c[11:14] if len(c) >= 14 else None)

            df["Sector_int"] = pd.to_numeric(df["Sector"], errors="coerce")
            df["Manzana_int"] = pd.to_numeric(df["Manzana"], errors="coerce")

            # --- Modo 1: Sector/Manzana ---
            if modo == "Sector/Manzana":
                sectores_unicos = sorted(df["Sector_int"].dropna().unique())
                sectores_unicos_str = [str(s).zfill(2) for s in sectores_unicos]

                sectores_seleccionados = st.multiselect(
                    f"🏘️ Sectores para {archivo.name}",
                    options=sectores_unicos_str,
                    format_func=lambda x: f"Sector {x}"
                )

                if sectores_seleccionados and st.button(f"✅ Aplicar filtro ({archivo.name})"):
                    mask = pd.Series([False] * len(df), index=df.index)
                    for sector in sectores_seleccionados:
                        sector_int = int(sector)
                        manzanas_permitidas = parse_manzanas_input("")  # aquí podrías extender con inputs
                        mask_sector = (df["Sector_int"] == sector_int)
                        mask = mask | mask_sector

                    df_filtrado = df[mask].copy()

                    st.write(f"**Filas encontradas:** {len(df_filtrado)}")
                    st.dataframe(df_filtrado.head(20), use_container_width=True)

                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_filtrado.to_excel(writer, index=False, sheet_name="Filtrado")
                    output.seek(0)

                    st.download_button(
                        label=f"⬇️ Descargar resultado ({archivo.name})",
                        data=output,
                        file_name=f"Filtrado_{archivo.name}",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

            # --- Modo 2: Polígono (BD) ---
            else:
                if not poligono:
                    st.warning("⚠️ Ingrese un polígono para aplicar el filtro.")
                    continue

                engine = conectar_bd()
                query = text("""
                    SELECT concat_sec
                    FROM public.entregas_a_cofopri
                    WHERE poligono = :poligono
                """)
                with engine.connect() as conn:
                    df_bd = pd.read_sql(query, conn, params={"poligono": poligono})

                if df_bd.empty:
                    st.warning(f"⚠️ No se encontraron registros en la BD para el polígono {poligono}.")
                    continue

                df["SecManz"] = df[col_cat].apply(lambda c: c[6:11] if len(c) >= 11 else None)
                df_filtrado = df[df["SecManz"].isin(df_bd["concat_sec"])].copy()

                st.write(f"**Filas encontradas:** {len(df_filtrado)}")
                st.dataframe(df_filtrado.head(20), use_container_width=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Filtrado")
                output.seek(0)

                st.download_button(
                    label=f"⬇️ Descargar resultado ({archivo.name})",
                    data=output,
                    file_name=f"Filtrado_{poligono}_{archivo.name}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"Error al procesar {archivo.name}: {e}")
