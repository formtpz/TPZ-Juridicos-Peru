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
    nombre_regla = "UA-1007"
    
    col_rentas = 'Código Contribuyente de Rentas'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [col_rentas, col_crc]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    df_temp = df.copy()
    
    # 2. Preparar los datos
    # Quitamos todos los espacios en blanco (incluso entre números, por ej: "123, 456" -> "123,456")
    df_temp['Rentas_Clean'] = df_temp[col_rentas].fillna('').astype(str).str.replace(' ', '')

    # 3. Lógica de la regla
    # A) Validar caracteres inválidos (todo lo que NO sea un número de 0-9 o una coma)
    mascara_caracteres = (df_temp['Rentas_Clean'] != '') & df_temp['Rentas_Clean'].str.contains(r'[^0-9,]', regex=True)
    
    # B) Validar duplicados (ignorando los vacíos)
    # keep=False marca TODAS las apariciones del dato duplicado como True
    mascara_duplicados = (df_temp['Rentas_Clean'] != '') & df_temp.duplicated(subset=['Rentas_Clean'], keep=False)
    
    # Unimos ambas máscaras
    filas_con_error = df_temp[mascara_caracteres | mascara_duplicados]
    
    # 4. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        valor_original = fila[col_rentas]
        
        # Identificar los errores específicos para dar un mensaje claro
        es_invalido = mascara_caracteres.loc[index]
        es_duplicado = mascara_duplicados.loc[index]
        
        mensajes = []
        if es_invalido:
            mensajes.append("Contiene caracteres alfanuméricos o inválidos, solo se admiten números.")
        if es_duplicado:
            mensajes.append("Es un código duplicado (ya está asignado a otro predio).")
            
        desc_error = f"Inconsistencia en el Código de Rentas ('{valor_original}'): " + " ".join(mensajes)
        
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