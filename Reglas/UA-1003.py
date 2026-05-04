import pandas as pd

def descomponer_crc(crc):
    if pd.isna(crc) or str(crc).strip() == '':
        return None
        
    crc_str = str(crc).strip()
    crc_pad = crc_str.zfill(23) 
    
    try:
        return {
            'Prefix':   crc_pad[0:6],
            'Sector':   crc_pad[6:8],   
            'Manzana':  crc_pad[8:11],  
            'Lote':     crc_pad[11:14], 
            'Edifica':  crc_pad[14:16], 
            'Entrada':  crc_pad[16:18], 
            'Piso':     crc_pad[18:20], 
            'Unidad':   crc_pad[20:23], 
        }
    except Exception:
        return None

def validar(dfs):
    # Extraemos solo el Excel de unidades que es el que necesita esta regla
    if 'unidades' not in dfs: 
        return [] # Si por alguna razón no se cargó, la regla se omite
    df = dfs['unidades'] 
    
    errores = []
    nombre_regla = "UA-1003"
    
    col_crc = 'Código de Referencia Catastral'
    col_predio_en = 'Predio Catastral En'
    col_tipo_edifica = 'Tipo de Edificación'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [col_crc, col_predio_en, col_tipo_edifica]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    df_temp = df.copy()
    
    # Rellenamos y limpiamos el CRC para extraer los identificadores
    crcs_limpios = df_temp[col_crc].fillna('').astype(str).str.strip()
    crcs_padded = crcs_limpios.apply(lambda x: x.zfill(23) if x != '' else '')
    
    df_temp['Lote_ID'] = crcs_padded.str.slice(0, 14)
    df_temp['Unidad_ID'] = crcs_padded.str.slice(20, 23)
    
    # Limpiamos textos para comparaciones seguras
    df_temp['Predio_Clean'] = df_temp[col_predio_en].fillna('').astype(str).str.strip().str.upper()
    
    # Limpieza robusta del Tipo de Edificación (quitamos espacios extra para evitar errores de tipeo como "CASA/ CHALET" vs "CASA/CHALET")
    df_temp['Tipo_Edifica_Clean'] = df_temp[col_tipo_edifica].fillna('').astype(str).str.upper().str.replace(' ', '')

    # 3. Filtrar datos válidos para el conteo (excluimos sin CRC y falsos positivos 999)
    df_validos = df_temp[(df_temp['Lote_ID'] != '') & (df_temp['Unidad_ID'] != '999')].copy()
    
    # 4. Agrupar por Lote_ID y contar cuántas unidades tiene cada lote
    conteo_por_lote = df_validos.groupby('Lote_ID').size().reset_index(name='Total_Unidades')
    df_evaluar = pd.merge(df_validos, conteo_por_lote, on='Lote_ID', how='left')

    # 5. Lógica de la regla
    # Condición A: Tiene 1 unidad PERO NO dice PREDIO INDEPENDIENTE
    cond_a = (df_evaluar['Total_Unidades'] == 1) & (df_evaluar['Predio_Clean'] != 'PREDIO INDEPENDIENTE')
    
    # Condición B: Tiene más de 1 unidad PERO SÍ dice PREDIO INDEPENDIENTE
    cond_b = (df_evaluar['Total_Unidades'] > 1) & (df_evaluar['Predio_Clean'] == 'PREDIO INDEPENDIENTE')
    
    filas_con_error = df_evaluar[cond_a | cond_b]
    
    # 6. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        total_unds = fila['Total_Unidades']
        valor_original_predio = fila[col_predio_en]
        valor_original_edifica = fila[col_tipo_edifica]
        tipo_edifica_clean = fila['Tipo_Edifica_Clean']
        
        # Generar mensaje de error dinámico y explícito para el caso de CASA/CHALET
        es_casa = (tipo_edifica_clean == 'CASA/CHALET')
        
        if total_unds == 1:
            if es_casa:
                desc_error = f"Inconsistencia: Es '{valor_original_edifica}' con 1 sola unidad en el lote, DEBE ser 'PREDIO INDEPENDIENTE' (Registrado: '{valor_original_predio}')."
            else:
                desc_error = f"Inconsistencia: El lote tiene 1 sola unidad, debe ser 'PREDIO INDEPENDIENTE' (Registrado: '{valor_original_predio}')."
        else:
            if es_casa:
                desc_error = f"Inconsistencia: Es '{valor_original_edifica}', pero el lote tiene {total_unds} unidades físicas, NO puede ser 'PREDIO INDEPENDIENTE' (Registrado: '{valor_original_predio}')."
            else:
                desc_error = f"Inconsistencia: El lote tiene {total_unds} unidades, NO puede ser 'PREDIO INDEPENDIENTE' (Registrado: '{valor_original_predio}')."
        
        componentes = descomponer_crc(crc)
        
        if componentes:
            error_reporte = {
                'Nombre de la Regla': nombre_regla,
                'Sector':   componentes['Sector'],
                'Manzana':  componentes['Manzana'],
                'Lote':     componentes['Lote'],
                'Edifica':  componentes['Edifica'],
                'Entrada':  componentes['Entrada'],
                'Piso':     componentes['Piso'],
                'Unidad':   componentes['Unidad'],
                'Descripción del Error': desc_error
            }
        else:
            error_reporte = {
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Sin CRC o Inválido (Fila de lectura)",
                'Descripción del Error': desc_error
            }
            
        errores.append(error_reporte)
        
    return errores