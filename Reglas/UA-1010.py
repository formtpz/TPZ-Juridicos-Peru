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
    # Extraemos solo el Excel de unidades que es el que necesita esta regla
    if 'unidades' not in dfs: 
        return [] # Si por alguna razón no se cargó, la regla se omite
    df = dfs['unidades'] 
    
    errores = []
    nombre_regla = "UA-1010"
    
    col_cond_titular = 'Condición del Titular'
    col_forma_adq = 'Forma de Adquisición'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [col_cond_titular, col_forma_adq, col_crc]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    df_temp = df.copy()
    
    # 2. Preparar los datos (limpiar nulos y espacios en blanco)
    df_temp['Cond_Clean'] = df_temp[col_cond_titular].fillna('').astype(str).str.strip()
    df_temp['Forma_Clean'] = df_temp[col_forma_adq].fillna('').astype(str).str.strip()

    # 3. Lógica de la regla
    # El error ocurre si la Condición del Titular está vacía O la Forma de Adquisición está vacía
    mascara_error = (df_temp['Cond_Clean'] == '') | (df_temp['Forma_Clean'] == '')
    
    filas_con_error = df_temp[mascara_error]
    
    # 4. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        
        # Generar un mensaje dinámico dependiendo de qué columna esté vacía
        faltantes = []
        if fila['Cond_Clean'] == '':
            faltantes.append(f"'{col_cond_titular}'")
        if fila['Forma_Clean'] == '':
            faltantes.append(f"'{col_forma_adq}'")
            
        # Si faltan las dos dirá "Las columnas ...", si falta una dirá "La columna ..."
        articulo = "Las columnas" if len(faltantes) > 1 else "La columna"
        verbo = "están vacías" if len(faltantes) > 1 else "está vacía"
        
        desc_error = f"Inconsistencia: {articulo} {' y '.join(faltantes)} {verbo}. Son datos obligatorios."
        
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