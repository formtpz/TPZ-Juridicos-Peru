# modulos/procesar_detalle_muestra.py
import streamlit as st
import pandas as pd
import re
from io import BytesIO
from permisos import validar_acceso


# ============================================================
# Funciones de procesamiento (adaptadas del script original)
# ============================================================

def renombrar_leves_graves(df):
    leves_cols = [c for c in df.columns if isinstance(c, str) and c.startswith('Leves')]
    graves_cols = [c for c in df.columns if isinstance(c, str) and c.startswith('Graves')]

    destino_leves = ['Leves_UA', 'Leves_DE', 'Leves_BG']
    destino_graves = ['Graves_UA', 'Graves_DE', 'Graves_BG']
    mapping = {}

    for idx, col in enumerate(leves_cols[:3]):
        mapping[col] = destino_leves[idx]
    for idx, col in enumerate(graves_cols[:3]):
        mapping[col] = destino_graves[idx]

    return df.rename(columns=mapping)


def depurar_dataframe_exportado(df):
    columnas_a_eliminar = [
        'Con observaciones',
        'Resultado',
        'Extra',
        'Extra_2',
        'Observaciones_2',
        'Resultado (L<4, G<1)',
        'Extra_3',
        'Observaciones_3',
        'Resultado (L<4, G<1)_2',
        'Extra_4',
        'Resultado V1. Fichas',
        'Resultado V4. Base Gráfica',
        'Resultado FINAL',
        'Observaciones_4',
    ]

    df = df.drop(columns=[c for c in columnas_a_eliminar if c in df.columns], errors='ignore')
    df = renombrar_leves_graves(df)
    return df


def procesar_excel_detalle_muestra(file_bytes, file_name):
    """
    Procesa un archivo Excel a partir de sus bytes (Streamlit UploadedFile).
    Devuelve un DataFrame con los datos extraídos, o DataFrame vacío si falla.
    """
    try:
        # Leer hoja 'Resumen Muestra'
        df_resumen = pd.read_excel(file_bytes, sheet_name='Resumen Muestra', header=None)
    except ValueError:
        st.warning(f"El archivo {file_name} no tiene la hoja 'Resumen Muestra'. Se omite.")
        return pd.DataFrame()

    # Metadatos
    distrito = df_resumen.iloc[5, 14]          # O6
    entregable = df_resumen.iloc[6, 14]        # O7
    poligono = df_resumen.iloc[4, 30]          # AE5
    pol_sicun = df_resumen.iloc[5, 30]         # AE6

    # Fechas (búsqueda en zona AR:AW)
    fecha_recepcion = None
    fecha_resultado = None
    for i in range(df_resumen.shape[0]):
        for j in range(43, 49):
            cell_value = str(df_resumen.iloc[i, j]).strip() if pd.notna(df_resumen.iloc[i, j]) else ''
            label = cell_value.replace(' ', '').upper()
            if label in {'FECHARECEPCION:', 'FECHARECEPCION'}:
                for k in range(49, 53):
                    val = df_resumen.iloc[i, k]
                    if pd.notna(val) and str(val).strip() != '':
                        fecha_recepcion = val
                        break
            elif label in {'FECHA.RESULTADO:', 'FECHA.RESULTADO'}:
                for k in range(49, 53):
                    val = df_resumen.iloc[i, k]
                    if pd.notna(val) and str(val).strip() != '':
                        fecha_resultado = val
                        break
        if fecha_recepcion is not None and fecha_resultado is not None:
            break

    # Leer hoja 'Detalle Muestra'
    xls = pd.ExcelFile(file_bytes)
    sheet_detalle = next((s for s in xls.sheet_names if s.lower().strip() == 'detalle muestra'), None)
    if sheet_detalle is None:
        st.warning(f"El archivo {file_name} no contiene 'Detalle Muestra'. Se omite.")
        return pd.DataFrame()

    df_detalle = pd.read_excel(file_bytes, sheet_name=sheet_detalle, header=None)
    df_data = df_detalle.iloc[7:, :].reset_index(drop=True)

    # Columnas de Unidad Administrativa y CRC
    header_row = df_detalle.iloc[6]
    unidad_col = next(
        (col for col, val in header_row.items()
         if isinstance(val, str) and 'unidad administrativ' in val.lower()),
        2
    )
    crc_col = next(
        (col for col, val in header_row.items()
         if isinstance(val, str) and ('codigo de referencia' in val.lower() or 'crc' in val.lower())),
        3
    )

    unidad_administrativa = df_data.iloc[:, unidad_col].apply(lambda x: str(x).strip() if pd.notna(x) else '')
    crc = df_data.iloc[:, crc_col].apply(lambda x: str(x).strip() if pd.notna(x) else '')

    # Columnas de errores (a partir del primer código tipo XX.XX.XX)
    first_error_col = next(
        (col for col, val in header_row.items()
         if isinstance(val, str) and re.match(r'^[A-Z]{2}\.\d{2}\.\d{2}$', val.strip())),
        6
    )
    header_names = df_detalle.iloc[6, first_error_col:]
    error_columns = []
    column_names = []
    seen = {}

    for idx, name in enumerate(header_names, start=first_error_col):
        name = str(name).strip() if pd.notna(name) else ''
        if not name:
            continue

        if re.match(r'^[A-Z]{2}\.\d{2}\.\d{2}$', name):
            col_name = name
        else:
            col_name = re.sub(r'(?<=\b)([A-Za-z0-9]+)\.([0-9]+)\b', r'\1-\2', name)
            if not col_name:
                col_name = f'Extra_{idx}'

        if col_name in seen:
            seen[col_name] += 1
            col_name = f"{col_name}_{seen[col_name]}"
        else:
            seen[col_name] = 1

        error_columns.append(idx)
        column_names.append(col_name)

    df_errors = df_data.iloc[:, error_columns].copy()
    df_errors.columns = column_names

    # Construir DataFrame final
    df_final = pd.concat(
        [
            pd.Series([distrito] * len(df_errors), name='DISTRITO'),
            pd.Series([entregable] * len(df_errors), name='ENTREGABLE'),
            pd.Series([poligono] * len(df_errors), name='POLIGONO'),
            pd.Series([pol_sicun] * len(df_errors), name='POL_SICUN'),
            pd.Series([fecha_recepcion] * len(df_errors), name='FECHA RECEPCION:'),
            pd.Series([fecha_resultado] * len(df_errors), name='FECHA. RESULTADO:'),
            pd.Series(unidad_administrativa.values, name='Unidad Administrativa'),
            pd.Series(crc.values, name='CRC'),
            df_errors.reset_index(drop=True),
        ],
        axis=1,
    )

    # Filtrar filas válidas
    valid_rows = (
        df_final['Unidad Administrativa'].astype(str).str.strip() != ''
    ) | (df_final['CRC'].astype(str).str.strip() != '')
    valid_rows &= ~df_final['Unidad Administrativa'].astype(str).str.match(r'^Recuento$', na=False)
    df_final = df_final.loc[valid_rows].reset_index(drop=True)

    df_final['Unidad Administrativa'] = df_final['Unidad Administrativa'].astype(str)
    df_final['CRC'] = df_final['CRC'].astype(str)

    df_final = depurar_dataframe_exportado(df_final)
    return df_final


# ============================================================
# Interfaz de Streamlit
# ============================================================

def render():
    validar_acceso("Compilar Detalle Errores")   # <-- Nombre que pondremos en permisos

    st.title("📋 Compilador de Detalle de Errores")
    st.markdown("""
    Sube los archivos Excel que contengan las hojas **'Resumen Muestra'** y **'Detalle Muestra'**.  
    Se extraerán los metadatos y los errores individuales por CRC, generando un único archivo consolidado.
    """)

    archivos = st.file_uploader(
        "📂 Cargar archivos Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="compilar_detalle_errores"
    )

    if archivos:
        st.info(f"📌 {len(archivos)} archivo(s) cargado(s)")

        if st.button("🚀 Procesar archivos", type="primary"):
            with st.spinner("Procesando, por favor espera..."):
                frames = []
                progress_bar = st.progress(0)
                for idx, uploaded_file in enumerate(archivos):
                    # Leer bytes del archivo subido
                    file_bytes = BytesIO(uploaded_file.read())
                    df = procesar_excel_detalle_muestra(file_bytes, uploaded_file.name)
                    if not df.empty:
                        frames.append(df)
                    # Actualizar barra
                    progress_bar.progress((idx + 1) / len(archivos))

                if frames:
                    df_consolidado = pd.concat(frames, ignore_index=True)

                    st.success(f"✅ Procesamiento completado. Se consolidaron {len(df_consolidado)} registros.")

                    # Mostrar vista previa
                    with st.expander("🔍 Vista previa del resultado"):
                        st.dataframe(df_consolidado.head(50), use_container_width=True)

                    # Convertir a Excel para descarga
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_consolidado.to_excel(writer, index=False, sheet_name='Detalle Errores')
                    output.seek(0)

                    st.download_button(
                        label="⬇️ Descargar Excel consolidado",
                        data=output,
                        file_name="Compilado_Detalle_errores.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error("❌ Ninguno de los archivos contenía datos válidos.")
    else:
        st.info("📂 Arrastra o selecciona los archivos Excel para comenzar.")
