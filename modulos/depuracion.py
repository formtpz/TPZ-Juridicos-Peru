# modulos/depuracion.py
import streamlit as st
import pandas as pd
from io import BytesIO
from pathlib import Path
from permisos import validar_acceso

ENTREGAS_FILES = {
    "Entregas a COFOPRI": "Entregas_a_cofopri.xlsx",
    "Entregas a Campo": "Entregas_a_campo.xlsx",
}

def normalize_concat_sec(value, width=5):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    text = text.replace(" ", "")
    if text.isdigit():
        return text.zfill(width)
    return text


def normalize_segment(value, start, end, pad_length=None):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    text = text.replace(" ", "")
    if pad_length:
        text = text.zfill(pad_length)
    return text[start:end]

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
    poligonos_sel = None
    df_entregas = None
    fuente_entregas = None
    if modo == "Polígono (Excel)":
        fuente_entregas = st.selectbox(
            "Fuente de entregas:",
            ["Entregas a COFOPRI", "Entregas a Campo", "Ambas"]
        )

        archivos_entrega = []
        if fuente_entregas == "Ambas":
            archivos_entrega = list(ENTREGAS_FILES.values())
        else:
            archivos_entrega = [ENTREGAS_FILES[fuente_entregas]]

        try:
            frames = []
            for nombre_archivo in archivos_entrega:
                ruta_entrega = Path("Rentas_resumidos") / nombre_archivo
                df_tmp = pd.read_excel(ruta_entrega, engine="openpyxl")
                df_tmp["fuente_entrega"] = nombre_archivo
                frames.append(df_tmp)

            df_entregas = pd.concat(frames, ignore_index=True)

            columnas_requeridas = {"poligono", "concat_sec"}
            faltantes = columnas_requeridas.difference(df_entregas.columns)
            if faltantes:
                st.error(f"Faltan columnas requeridas en los archivos de entregas: {sorted(faltantes)}")
                return
        except Exception as e:
            st.error(f"Error al cargar los archivos de entregas ({', '.join(archivos_entrega)}): {e}")
            return

        # Selección múltiple de polígonos disponibles
        poligonos_disp = sorted(df_entregas['poligono'].dropna().unique())
        poligonos_sel = st.multiselect("Seleccione uno o varios polígonos:", poligonos_disp)

    # --- Procesar cada archivo en lote ---
    for archivo in archivo_list:
        st.markdown(f"### 📑 Procesando archivo: **{archivo.name}**")

        try:
            df = pd.read_excel(archivo, engine="openpyxl")

            # Buscar columna catastral o columna Código del Lote
            col_cat = None
            for col in df.columns:
                if "código de referencia catastral" in col.lower():
                    col_cat = col
                    break
                if "código del lote" in col.lower():
                    col_cat = col
                    break

            if not col_cat:
                st.error("❌ No se encontró la columna 'Código de Referencia Catastral' ni 'Código del Lote'.")
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
                if not poligonos_sel:
                    st.warning("⚠️ Seleccione al menos un polígono para aplicar el filtro.")
                    continue

                if df_entregas is None:
                    st.error("No se pudo inicializar la fuente de entregas para el filtrado por polígono.")
                    continue

                df_entregas_sel = df_entregas[df_entregas['poligono'].isin(poligonos_sel)]

                if df_entregas_sel.empty:
                    st.warning(f"⚠️ No se encontraron registros en la fuente seleccionada ({fuente_entregas}) para los polígonos seleccionados.")
                    continue

                # Extraer los 5 dígitos (posiciones 7–11) según la columna usada
                if "referencia catastral" in col_cat.lower():
                    df["SecManz"] = df[col_cat].apply(
                        lambda c: normalize_concat_sec(normalize_segment(c, 6, 11, pad_length=23)) if pd.notna(c) else None
                    )
                else:  # Código del Lote
                    df["SecManz"] = df[col_cat].apply(
                        lambda c: normalize_concat_sec(normalize_segment(c, 6, 11)) if pd.notna(c) else None
                    )

                # Normalizar ambas columnas como strings de 5 dígitos con ceros a la izquierda
                df["SecManz"] = df["SecManz"].apply(normalize_concat_sec)
                df_entregas_sel = df_entregas_sel.copy()
                df_entregas_sel["concat_sec"] = df_entregas_sel["concat_sec"].apply(normalize_concat_sec)

                # Join con entregas seleccionadas
                df_filtrado = df.merge(
                    df_entregas_sel[["concat_sec", "poligono", "fuente_entrega"]],
                    left_on="SecManz",
                    right_on="concat_sec",
                    how="inner"
                )

                # Agregar columna Poligono y fuente de entrega
                df_filtrado.rename(
                    columns={"poligono": "Poligono", "fuente_entrega": "Fuente_Entrega"},
                    inplace=True
                )

                st.write(f"**Filas encontradas:** {len(df_filtrado)}")
                st.dataframe(df_filtrado.head(20), use_container_width=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Filtrado")
                output.seek(0)

                st.download_button(
                    label=f"⬇️ Descargar resultado ({archivo.name})",
                    data=output,
                    file_name=f"Filtrado_{'_'.join(poligonos_sel)}_{archivo.name}",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        except Exception as e:
            st.error(f"Error al procesar {archivo.name}: {e}")
