import pandas as pd

def descomponer_crc(crc):
    """
    Descompone el CRC aplicando los índices (23 caracteres).
    """
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
    if 'ingresos' not in dfs:
        return []
    
    df = dfs['ingresos']
    
    errores = []
    nombre_regla = "IN-1001"
    
    col_cond_num = 'Condición Numérica'
    col_num_muni = 'Número Municipal'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [col_cond_num, col_num_muni, col_crc]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}' en Ingresos."
            })
            return errores

    df_temp = df.copy()
    
    # 2. Preparar los datos
    df_temp['Cond_Clean'] = df_temp[col_cond_num].fillna('').astype(str).str.strip().str.upper()
    # Limpiamos también el Número Municipal para la excepción
    df_temp['Num_Muni_Clean'] = df_temp[col_num_muni].fillna('').astype(str).str.strip().str.upper()

    # 3. Lógica de la regla
    valores_prohibidos = ['GEN. POR EL TEC. CAT.', 'SIN CONDICIÓN', 'SIN CONDICION']
    
    # EXCEPCIÓN APLICADA: Es error si está vacía Y ADEMÁS el número municipal NO es 'S/N'
    mascara_vacia = (df_temp['Cond_Clean'] == '') & (df_temp['Num_Muni_Clean'] != 'S/N')
    
    # Los valores prohibidos siempre son error
    mascara_prohibida = df_temp['Cond_Clean'].isin(valores_prohibidos)
    
    filas_con_error = df_temp[mascara_vacia | mascara_prohibida]
    
    # 4. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        valor_original_cond = fila[col_cond_num]
        valor_original_num = fila[col_num_muni]
        
        # Mensaje dinámico según el tipo de error
        if mascara_vacia.loc[index]:
            desc_error = f"Inconsistencia: 'Condición Numérica' está vacía, pero el 'Número Municipal' es '{valor_original_num}' (no es S/N)."
        else:
            desc_error = f"Inconsistencia: La 'Condición Numérica' tiene un valor prohibido ('{valor_original_cond}')."
        
        componentes = descomponer_crc(crc)
        
        if componentes:
            if componentes['Unidad'] == '999':
                continue
            
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
                'Código del Predio (CRC)': f"Sin CRC (Fila {index + 2})",
                'Descripción del Error': desc_error
            }
            
        errores.append(error_reporte)
        
    return errores