# modulos/depuracion.py
import streamlit as st
import pandas as pd
from io import BytesIO
from permisos import validar_acceso

def render():
    # Control de acceso según perfil
    validar_acceso("Depuración de Datos")

    st.title("🧹 Depuración de Datos")
    st.markdown("Sube un archivo Excel y filtra por **Manzana** y **Lote**.")

    # 1. Cargar archivo Excel
    archivo = st.file_uploader(
        "📂 Cargar archivo Excel",
        type=["xlsx", "xls"],
        key="depuracion_uploader"
    )

    if archivo is not None:
        try:
            # Leer el Excel (primera hoja)
            df = pd.read_excel(archivo, engine="openpyxl")
            st.success("✅ Archivo cargado correctamente")

            # Mostrar vista previa
            with st.expander("📋 Vista previa de los datos"):
                st.dataframe(df.head(10), use_container_width=True)
                st.caption(f"Total de filas: {len(df)} | Columnas: {list(df.columns)}")

            # Verificar que existan las columnas requeridas
            col_manzana = None
            col_lote = None
            for col in df.columns:
                if col.lower() == "manzana":
                    col_manzana = col
                elif col.lower() == "lote":
                    col_lote = col

            if col_manzana is None:
                st.error("❌ No se encontró una columna llamada 'manzana' (insensible a mayúsculas).")
                return
            if col_lote is None:
                st.error("❌ No se encontró una columna llamada 'lote' (insensible a mayúsculas).")
                return

            # Obtener valores únicos ordenados
            valores_manzana = sorted(df[col_manzana].dropna().unique())
            valores_lote = sorted(df[col_lote].dropna().unique())

            # 2. Inputs para seleccionar filtros
            st.markdown("### 🔍 Selecciona los valores para filtrar")

            col1, col2 = st.columns(2)
            with col1:
                manzana_seleccionada = st.selectbox(
                    "🍎 Elija el filtro de Manzana",
                    options=valores_manzana,
                    index=None,
                    placeholder="Selecciona una manzana..."
                )
            with col2:
                lote_seleccionado = st.selectbox(
                    "📦 Elija el filtro de Lote",
                    options=valores_lote,
                    index=None,
                    placeholder="Selecciona un lote..."
                )

            # 3. Aplicar filtro
            if manzana_seleccionada and lote_seleccionado:
                df_filtrado = df[
                    (df[col_manzana] == manzana_seleccionada) &
                    (df[col_lote] == lote_seleccionado)
                ].copy()

                st.subheader("📊 Resultado del filtro")
                st.write(f"**Manzana:** {manzana_seleccionada} | **Lote:** {lote_seleccionado}")
                st.write(f"**Filas encontradas:** {len(df_filtrado)}")

                if len(df_filtrado) > 0:
                    st.dataframe(df_filtrado, use_container_width=True)

                    # 4. Descargar Excel filtrado (mismo orden de columnas)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_filtrado.to_excel(writer, index=False, sheet_name="Filtrado")
                    output.seek(0)

                    st.download_button(
                        label="⬇️ Descargar Excel filtrado",
                        data=output,
                        file_name=f"depurado_manzana_{manzana_seleccionada}_lote_{lote_seleccionado}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados.")
            else:
                st.info("👉 Selecciona una manzana **y** un lote para filtrar y descargar.")

        except Exception as e:
            st.error(f"Error al procesar el archivo: {str(e)}")
    else:
        st.info("📌 Sube un archivo Excel para comenzar.")
