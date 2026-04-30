# modulos/depuracion.py
import streamlit as st
import pandas as pd
import re
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
    st.markdown("""
    Sube un archivo Excel que contenga una columna **'Código de Referencia Catastral'**.
    A partir de ella se extraerán:
    - **Sector** (posiciones 7-8)
    - **Manzana** (posiciones 9-11)
    
    Luego puedes filtrar por sectores y, para cada uno, elegir manzanas específicas (rangos o lista) o todas.
    """)

    archivo = st.file_uploader("📂 Cargar archivo Excel", type=["xlsx", "xls"], key="depuracion_catastro")
    if archivo is not None:
        try:
            df = pd.read_excel(archivo, engine="openpyxl")
            st.success("✅ Archivo cargado correctamente")
            with st.expander("📋 Columnas detectadas"):
                st.write(list(df.columns))

            col_cat = None
            for col in df.columns:
                if "código de referencia catastral" in col.lower():
                    col_cat = col
                    break
            if not col_cat:
                st.error("❌ No se encontró una columna que contenga 'Código de Referencia Catastral'.")
                return

            df[col_cat] = df[col_cat].astype(str).str.strip()
            def extraer_sector(cod):
                return cod[6:8] if len(cod) >= 8 else None
            def extraer_manzana(cod):
                return cod[8:11] if len(cod) >= 11 else None

            df["Sector"] = df[col_cat].apply(extraer_sector)
            df["Manzana"] = df[col_cat].apply(extraer_manzana)
            df["Sector_int"] = pd.to_numeric(df["Sector"], errors="coerce")
            df["Manzana_int"] = pd.to_numeric(df["Manzana"], errors="coerce")

            original_len = len(df)
            df = df.dropna(subset=["Sector_int", "Manzana_int"]).copy()
            st.info(f"Se descartaron {original_len - len(df)} filas con códigos catastrales inválidos.")

            if df.empty:
                st.error("No hay datos válidos para procesar.")
                return

            sectores_unicos = sorted(df["Sector_int"].unique())
            sectores_unicos_str = [str(s).zfill(2) for s in sectores_unicos]

            st.markdown("### 🔍 Configuración de filtros")
            sectores_seleccionados = st.multiselect(
                "🏘️ Seleccione uno o más Sectores",
                options=sectores_unicos_str,
                format_func=lambda x: f"Sector {x}"
            )

            if "filtros_manzanas" not in st.session_state:
                st.session_state.filtros_manzanas = {}

            if sectores_seleccionados:
                st.markdown("---")
                st.subheader("📌 Definir manzanas por sector")
                for sector in sectores_seleccionados:
                    sector_int = int(sector)
                    manzanas_disponibles = sorted(df[df["Sector_int"] == sector_int]["Manzana_int"].unique())
                    st.markdown(f"**Sector {sector}** (manzanas disponibles: {len(manzanas_disponibles)})")
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        key_input = f"manzanas_input_{sector}"
                        default_val = st.session_state.filtros_manzanas.get(sector, {}).get("texto", "")
                        texto_manzanas = st.text_input(
                            "Manzanas (rangos ej: 1,2-6,30-90)",
                            value=default_val,
                            key=key_input,
                            placeholder="Ej: 1,5-8,12"
                        )
                    with col2:
                        key_check = f"todas_manzanas_{sector}"
                        todas = st.checkbox("Todas las manzanas", key=key_check,
                                            value=st.session_state.filtros_manzanas.get(sector, {}).get("todas", False))
                    st.session_state.filtros_manzanas[sector] = {"texto": texto_manzanas, "todas": todas}

                if st.button("✅ Aplicar filtro", type="primary"):
                    mask = pd.Series([False] * len(df), index=df.index)
                    for sector in sectores_seleccionados:
                        sector_int = int(sector)
                        config = st.session_state.filtros_manzanas.get(sector, {"todas": False, "texto": ""})
                        todas = config["todas"]
                        texto = config["texto"]
                        if todas:
                            mask_sector = (df["Sector_int"] == sector_int)
                        else:
                            manzanas_permitidas = parse_manzanas_input(texto)
                            if manzanas_permitidas:
                                mask_sector = (df["Sector_int"] == sector_int) & (df["Manzana_int"].isin(manzanas_permitidas))
                            else:
                                mask_sector = pd.Series([False] * len(df), index=df.index)
                        mask = mask | mask_sector

                    df_filtrado = df[mask].copy()
                    st.subheader("📊 Resultado del filtro")
                    st.write(f"**Sectores seleccionados:** {', '.join(sectores_seleccionados)}")
                    st.write(f"**Filas encontradas:** {len(df_filtrado)}")

                    if len(df_filtrado) > 0:
                        columnas_originales = [c for c in df.columns if c not in ["Sector_int", "Manzana_int", "Sector", "Manzana"]]
                        df_output = df_filtrado[columnas_originales].copy()
                        df_output["Sector"] = df_filtrado["Sector"]
                        df_output["Manzana"] = df_filtrado["Manzana"]
                        st.dataframe(df_output.head(20), use_container_width=True)
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine="openpyxl") as writer:
                            df_output.to_excel(writer, index=False, sheet_name="Filtrado")
                        output.seek(0)
                        st.download_button(
                            label="⬇️ Descargar Excel filtrado",
                            data=output,
                            file_name="Reporte_Unidades_Administrativas_Filtrado.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados.")
            else:
                st.info("👉 Selecciona al menos un sector para continuar.")
        except Exception as e:
            st.error(f"Error al procesar el archivo: {str(e)}")
            st.exception(e)
    else:
        st.info("📌 Sube un archivo Excel con la columna catastral para comenzar.")
