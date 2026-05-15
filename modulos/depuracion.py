# modulos/depuracion.py
import streamlit as st
import pandas as pd
from io import BytesIO
from permisos import validar_acceso

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
    modo = st.radio("Selecciona el modo de filtrado:", ["Sector/Manzana", "Polígono (Excel)"])

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
    if modo == "Polígono (Excel)":
        poligono = st.text_input("Ingrese el código de polígono (ej: SJM-04)")

        # Cargar entregas desde Excel del repositorio
        try:
            df_entregas = pd.read_excel("Rentas_resumidos/Entregas_a_cofopri.xlsx", engine="openpyxl")
        except Exception as e:
            st.error(f"Error al cargar Entregas_a_cofopri.xlsx: {e}")
            return

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

            # --- Modo 2: Polígono (Excel) ---
            else:
                if not poligono:
                    st.warning("⚠️ Ingrese un polígono para aplicar el filtro.")
                    continue

                df_entregas_pol = df_entregas[df_entregas['poligono'] == poligono]

                if df_entregas_pol.empty:
                    st.warning(f"⚠️ No se encontraron registros en Entregas_a_cofopri.xlsx para el polígono {poligono}.")
                    continue

                df["SecManz"] = df[col_cat].apply(lambda c: c[6:11] if len(c) >= 11 else None)
                df_filtrado = df[df["SecManz"].isin(df_entregas_pol["concat_sec"])].copy()

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
