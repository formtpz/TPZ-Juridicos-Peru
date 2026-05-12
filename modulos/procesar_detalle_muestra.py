# modulos/procesar_detalle_muestra.py
import streamlit as st
import pandas as pd
import re
from io import BytesIO
from permisos import validar_acceso
from db import execute
import traceback


# ============================================================
# Funciones de procesamiento
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


def normalizar_nombres_columnas(df):
    """
    Convierte nombres de columnas a minúsculas,
    reemplaza espacios, puntos y dos puntos por guiones bajos,
    y elimina guiones bajos múltiples.
    """
    import re  # ← Agregar al inicio del archivo si no está
    
    df = df.copy()
    df.columns = [
        str(col).lower()
        .replace(' ', '_')
        .replace('.', '_')
        .replace('-', '_')
        .replace(':', '')
        .strip('_')
        for col in df.columns
    ]
    
    # Limpiar guiones bajos múltiples (ej: fecha__resultado → fecha_resultado)
    df.columns = [
        re.sub(r'_+', '_', col)  # Reemplaza 1 o más '_' por uno solo
        for col in df.columns
    ]
    
    return df

def procesar_excel_detalle_muestra(file_bytes, file_name):
    try:
        df_resumen = pd.read_excel(file_bytes, sheet_name='Resumen Muestra', header=None)
    except ValueError:
        st.warning(f"El archivo {file_name} no tiene la hoja 'Resumen Muestra'. Se omite.")
        return pd.DataFrame()

    distrito = df_resumen.iloc[5, 14]
    entregable = df_resumen.iloc[6, 14]
    poligono = df_resumen.iloc[4, 30]
    pol_sicun = df_resumen.iloc[5, 30]

    fecha_recepcion = None
    fecha_resultado = None
    
    for i in range(df_resumen.shape[0]):
        for j in range(df_resumen.shape[1]):
            cell_value = str(df_resumen.iloc[i, j]).strip() if pd.notna(df_resumen.iloc[i, j]) else ''
            label = cell_value.replace(' ', '').upper()
    
            if label in {'FECHARECEPCION:', 'FECHARECEPCION'}:
                for k in range(j + 1, min(j + 10, df_resumen.shape[1])):
                    val = df_resumen.iloc[i, k]
                    if pd.notna(val) and str(val).strip() != '':
                        fecha_recepcion = val
                        break
    
            elif label in {'FECHA.RESULTADO:', 'FECHA.RESULTADO'}:
                for k in range(j + 1, min(j + 10, df_resumen.shape[1])):
                    val = df_resumen.iloc[i, k]
                    if pd.notna(val) and str(val).strip() != '':
                        fecha_resultado = val
                        break
    
            if fecha_recepcion is not None and fecha_resultado is not None:
                break
        if fecha_recepcion is not None and fecha_resultado is not None:
            break

    xls = pd.ExcelFile(file_bytes)
    sheet_detalle = next((s for s in xls.sheet_names if s.lower().strip() == 'detalle muestra'), None)
    if sheet_detalle is None:
        st.warning(f"El archivo {file_name} no contiene 'Detalle Muestra'. Se omite.")
        return pd.DataFrame()

    df_detalle = pd.read_excel(file_bytes, sheet_name=sheet_detalle, header=None)
    df_data = df_detalle.iloc[7:, :].reset_index(drop=True)

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

    valid_rows = (
        df_final['Unidad Administrativa'].astype(str).str.strip() != ''
    ) | (df_final['CRC'].astype(str).str.strip() != '')
    valid_rows &= ~df_final['Unidad Administrativa'].astype(str).str.match(r'^Recuento$', na=False)
    df_final = df_final.loc[valid_rows].reset_index(drop=True)

    df_final['Unidad Administrativa'] = df_final['Unidad Administrativa'].astype(str)
    df_final['CRC'] = df_final['CRC'].astype(str)

    df_final = depurar_dataframe_exportado(df_final)
    df_final = normalizar_nombres_columnas(df_final)
    
    return df_final


# ============================================================
# Función para guardar en PostgreSQL
# ============================================================

def guardar_en_bd(df_consolidado):
    columnas_bd = [
        # Metadatos
        'distrito', 'entregable', 'poligono', 'pol_sicun',
        'fecha_recepcion', 'fecha_resultado', 'unidad_administrativa', 'crc',
        
        # FI (02-39)
        'fi_02_01', 'fi_02_02', 'fi_02_03', 'fi_02_04',
        'fi_03_01', 'fi_04_01', 'fi_05_01', 'fi_05_02', 'fi_05_03',
        'fi_05_04', 'fi_05_05', 'fi_05_06', 'fi_06_01', 'fi_06_02',
        'fi_06_03', 'fi_06_04', 'fi_06_05', 'fi_06_06', 'fi_07_01',
        'fi_07_02', 'fi_08_01', 'fi_08_02', 'fi_08_03', 'fi_08_04',
        'fi_08_05', 'fi_08_06', 'fi_08_07', 'fi_08_08', 'fi_09_01',
        'fi_09_02', 'fi_10_01', 'fi_10_02', 'fi_10_03', 'fi_10_04',
        'fi_11_01', 'fi_11_02', 'fi_11_03', 'fi_12_01', 'fi_12_02',
        'fi_12_03', 'fi_12_04', 'fi_13_01', 'fi_13_02', 'fi_13_03',
        'fi_13_04', 'fi_14_01', 'fi_14_02', 'fi_14_03', 'fi_14_04',
        'fi_15_01', 'fi_15_02', 'fi_15_03', 'fi_16_01', 'fi_16_02',
        'fi_17_01', 'fi_17_02', 'fi_17_03', 'fi_18_01', 'fi_18_02',
        'fi_18_03', 'fi_19_01', 'fi_19_02', 'fi_20_01', 'fi_20_02',
        'fi_20_03', 'fi_21_01', 'fi_21_02', 'fi_21_03', 'fi_22_01',
        'fi_23_01', 'fi_23_02', 'fi_24_01', 'fi_24_02', 'fi_24_03',
        'fi_25_01', 'fi_25_02', 'fi_25_03', 'fi_25_04', 'fi_25_05',
        'fi_25_06', 'fi_26_01', 'fi_26_02', 'fi_27_01', 'fi_27_02',
        'fi_28_01', 'fi_28_02', 'fi_29_01', 'fi_29_02', 'fi_29_03',
        'fi_29_04', 'fi_29_05', 'fi_29_06', 'fi_29_07', 'fi_29_08',
        'fi_29_09', 'fi_30_01', 'fi_30_02', 'fi_30_03', 'fi_30_04',
        'fi_30_05', 'fi_30_06', 'fi_30_07', 'fi_30_08', 'fi_30_09',
        'fi_31_01', 'fi_31_02', 'fi_32_01', 'fi_32_02', 'fi_32_03',
        'fi_33_01', 'fi_33_02', 'fi_34_01', 'fi_34_02', 'fi_34_03',
        'fi_34_04', 'fi_35_01', 'fi_35_02', 'fi_35_03', 'fi_35_04',
        'fi_35_05', 'fi_35_06', 'fi_36_01', 'fi_36_02', 'fi_36_03',
        'fi_37_01', 'fi_37_02', 'fi_37_03', 'fi_37_04', 'fi_37_05',
        'fi_37_06', 'fi_38_01', 'fi_39_01',
        
        # FC (40-42)
        'fc_40_01', 'fc_40_02', 'fc_40_03', 'fc_40_04', 'fc_40_05', 'fc_40_06',
        'fc_41_01', 'fc_41_02', 'fc_42_01', 'fc_42_02',
        
        # FB (43-44)
        'fb_43_01', 'fb_43_02', 'fb_43_03', 'fb_43_04', 'fb_43_05',
        'fb_44_01', 'fb_44_02', 'fb_44_03', 'fb_44_04', 'fb_44_05', 'fb_44_06',
        
        # FF (45)
        'ff_45_01', 'ff_45_02', 'ff_45_03', 'ff_45_04', 'ff_45_05',
        
        # FI (46)
        'fi_46_01', 'fi_46_02', 'fi_46_03', 'fi_46_04', 'fi_46_05',
        'fi_46_06', 'fi_46_07', 'fi_46_08', 'fi_46_09', 'fi_46_10',
        'fi_46_11', 'fi_46_12', 'fi_46_13',
        
        # EE (01-08)
        'ee_01_01', 'ee_02_01', 'ee_02_02', 'ee_02_03', 'ee_03_01',
        'ee_04_01', 'ee_05_01', 'ee_06_01', 'ee_07_01', 'ee_08_01',
        
        # ED (01-11)
        'ed_01_01', 'ed_02_01', 'ed_02_02', 'ed_03_01', 'ed_03_02',
        'ed_04_01', 'ed_04_02', 'ed_05_01', 'ed_06_01', 'ed_06_02',
        'ed_07_01', 'ed_07_02', 'ed_09_01', 'ed_10_01', 'ed_10_02',
        'ed_10_03', 'ed_10_04', 'ed_10_05', 'ed_10_06', 'ed_10_07',
        'ed_11_01', 'ed_11_02', 'ed_11_03', 'ed_11_04', 'ed_11_05',
        'ed_11_06', 'ed_11_07', 'ed_11_08', 'ed_11_09', 'ed_11_10',
        'ed_11_11', 'ed_11_12',
        
        # BM (01-05)
        'bm_01_01', 'bm_01_02', 'bm_01_03', 'bm_01_04', 'bm_01_05',
        'bm_01_06', 'bm_01_07', 'bm_01_08', 'bm_01_09', 'bm_01_10',
        'bm_01_11', 'bm_02_01', 'bm_02_02', 'bm_02_03', 'bm_02_04',
        'bm_02_05', 'bm_02_06', 'bm_03_01', 'bm_04_01', 'bm_05_01',
        'bm_05_02', 'bm_05_03', 'bm_05_04',
        
        # Columnas adicionales
        'suma_de_errores_por_fila', 'otras', 'error'
    ]
    
    try:
        columnas_existentes = [col for col in columnas_bd if col in df_consolidado.columns]
        
        if not columnas_existentes:
            st.error("❌ No hay columnas coincidentes")
            st.write("Columnas en el DataFrame:", list(df_consolidado.columns[:10]))
            return
        
        # Usar execute del db.py
        registros_insertados = 0
        
        for _, row in df_consolidado.iterrows():
            valores = []
            for col in columnas_existentes:
                val = row[col]
                if pd.notna(val):
                    val_str = str(val)[:30]
                else:
                    val_str = None
                valores.append(val_str)
            
            columnas_str = ', '.join(columnas_existentes)
            placeholders = ', '.join(['%s'] * len(columnas_existentes))
            
            query = f"""
                INSERT INTO public.calidad_externa ({columnas_str})
                VALUES ({placeholders})
            """
            
            execute(query, params=valores)
            registros_insertados += 1
        
        st.success(f"✅ {registros_insertados} registros insertados exitosamente")
    
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.code(traceback.format_exc())


# ============================================================
# Interfaz de Streamlit (CORREGIDA)
# ============================================================

def render():
    validar_acceso("Depuración de Datos")

    st.title("📋 Compilador de Detalle de Errores")
    st.markdown("""
    Sube los archivos Excel con hojas **'Resumen Muestra'** y **'Detalle Muestra'**.  
    Se extraen metadatos y errores por CRC.
    """)

    # ============================================================
    # INICIALIZAR ESTADOS DE SESIÓN
    # ============================================================
    if 'df_consolidado' not in st.session_state:
        st.session_state['df_consolidado'] = None
    
    if 'procesado' not in st.session_state:
        st.session_state['procesado'] = False

    # ============================================================
    # FILE UPLOADER (siempre visible)
    # ============================================================
    archivos = st.file_uploader(
        "📂 Cargar archivos Excel",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="compilar_detalle_errores"
    )

    if archivos:
        st.info(f"📌 {len(archivos)} archivo(s) cargado(s)")

        # ============================================================
        # BOTÓN PROCESAR (siempre visible mientras haya archivos)
        # ============================================================
        if st.button("🚀 Procesar archivos", type="primary"):
            with st.spinner("Procesando..."):
                frames = []
                progress_bar = st.progress(0)
                for idx, uploaded_file in enumerate(archivos):
                    file_bytes = BytesIO(uploaded_file.read())
                    df = procesar_excel_detalle_muestra(file_bytes, uploaded_file.name)
                    if not df.empty:
                        frames.append(df)
                    progress_bar.progress((idx + 1) / len(archivos))

                if frames:
                    st.session_state['df_consolidado'] = pd.concat(frames, ignore_index=True)
                    st.session_state['procesado'] = True
                    st.rerun()  # Forzar rerun para mostrar los resultados
                else:
                    st.error("❌ Ningún archivo contenía datos válidos.")
                    st.session_state['procesado'] = False

    # ============================================================
    # MOSTRAR RESULTADOS SI YA SE PROCESÓ
    # ============================================================
    if st.session_state['procesado'] and st.session_state['df_consolidado'] is not None:
        df_consolidado = st.session_state['df_consolidado']
        
        st.success(f"✅ {len(df_consolidado)} registros consolidados.")

        with st.expander("🔍 Vista previa (50 filas)"):
            st.dataframe(df_consolidado.head(50), use_container_width=True)
        
        with st.expander("🔍 Columnas del DataFrame"):
            st.write(list(df_consolidado.columns))

        # Exportar a Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_consolidado.to_excel(writer, index=False, sheet_name='Detalle Errores')
        output.seek(0)

        # ============================================================
        # BOTONES SIEMPRE VISIBLES (DESPUÉS DE PROCESAR)
        # ============================================================
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="⬇️ Descargar Excel",
                data=output,
                file_name="Compilado_Detalle_errores.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col2:
            if st.button("💾 Guardar en Base de Datos", type="secondary", use_container_width=True):
                with st.spinner("Guardando en la base de datos..."):
                    guardar_en_bd(df_consolidado)

    elif not archivos:
        st.info("📂 Arrastra o selecciona archivos Excel para comenzar.")
