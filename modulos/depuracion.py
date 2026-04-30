# modulos/depuracion.py
import streamlit as st
import pandas as pd
from io import BytesIO
from permisos import validar_acceso

def render():
    validar_acceso("Depuración de Datos")

    st.title("🧹 Depuración de Datos")
    st.markdown("Sube un archivo Excel y filtra por **Manzana** y uno o varios **Lotes** asociados.")

    archivo = st.file_uploader(
        "📂 Cargar archivo Excel",
        type=["xlsx", "xls"],
        key="depuracion_uploader"
    )

    if archivo is not None:
        try:
            df = pd.read_excel(archivo, engine="openpyxl")
            st.success("✅ Archivo cargado correctamente")

            with st.expander("📋 Vista previa de los datos"):
                st.dataframe(df.head(10), use_container_width=True)
                st.caption(f"Total de filas: {len(df)} | Columnas: {list(df.columns)}")

            # Detectar columnas 'manzana' y 'lote' (insensible a mayúsculas)
            col_manzana = None
            col_lote = None
            for col in df.columns:
                if col.lower() == "manzana":
                    col_manzana = col
                elif col.lower() == "lote":
                    col_lote = col

            if col_manzana is None:
                st.error("❌ No se encontró una columna llamada 'manzana'.")
                return
            if col_lote is None:
                st.error("❌ No se encontró una columna llamada 'lote'.")
                return

            # Valores únicos de manzana (ordenados)
            manzanas_unicas = sorted(df[col_manzana].dropna().unique())

            st.markdown("### 🔍 Selecciona los valores para filtrar")

            # Selector de manzana
            manzana_seleccionada = st.selectbox(
                "🍎 Elija la Manzana",
                options=manzanas_unicas,
                index=None,
                placeholder="Selecciona una manzana..."
            )

            # Inicializar variable lotes_seleccionados
            lotes_seleccionados = []

            if manzana_seleccionada:
                # Filtrar lotes únicos para esa manzana
                lotes_asociados = sorted(
                    df[df[col_manzana] == manzana_seleccionada][col_lote].dropna().unique()
                )

                if lotes_asociados:
                    # Multi-select para lotes
                    lotes_seleccionados = st.multiselect(
                        "📦 Elija uno o varios Lotes (asociados a la manzana seleccionada)",
                        options=lotes_asociados,
                        default=None,
                        placeholder="Selecciona lotes..."
                    )
                else:
                    st.warning("⚠️ La manzana seleccionada no tiene lotes asociados.")
            else:
                st.info("👉 Primero selecciona una manzana para ver sus lotes disponibles.")

            # Aplicar filtro solo si hay manzana y al menos un lote seleccionado
            if manzana_seleccionada and lotes_seleccionados:
                df_filtrado = df[
                    (df[col_manzana] == manzana_seleccionada) &
                    (df[col_lote].isin(lotes_seleccionados))
                ].copy()

                st.subheader("📊 Resultado del filtro")
                st.write(f"**Manzana:** {manzana_seleccionada}")
                st.write(f"**Lotes seleccionados:** {', '.join(map(str, lotes_seleccionados))}")
                st.write(f"**Filas encontradas:** {len(df_filtrado)}")

                if len(df_filtrado) > 0:
                    st.dataframe(df_filtrado, use_container_width=True)

                    # Preparar descarga (mismo orden de columnas)
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine="openpyxl") as writer:
                        df_filtrado.to_excel(writer, index=False, sheet_name="Filtrado")
                    output.seek(0)

                    nombre_archivo = f"depurado_manzana_{manzana_seleccionada}_lotes_{'_'.join(map(str, lotes_seleccionados))}.xlsx"
                    # Limitar longitud del nombre si es muy largo
                    if len(nombre_archivo) > 200:
                        nombre_archivo = f"depurado_manzana_{manzana_seleccionada}_{len(lotes_seleccionados)}_lotes.xlsx"

                    st.download_button(
                        label="⬇️ Descargar Excel filtrado",
                        data=output,
                        file_name=nombre_archivo,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados.")
            else:
                if manzana_seleccionada and not lotes_seleccionados:
                    st.info("👉 Selecciona al menos un lote para filtrar.")
                elif not manzana_seleccionada:
                    st.info("👉 Selecciona una manzana para comenzar.")

        except Exception as e:
            st.error(f"Error al procesar el archivo: {str(e)}")
    else:
        st.info("📌 Sube un archivo Excel para comenzar.")
