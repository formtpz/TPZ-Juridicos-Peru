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
    nombre_regla = "UA-1006"
    
    col_num_partida = 'Número de Partida Registral'
    col_tipo_partida = 'Tipo de Partida Registral'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [col_num_partida, col_tipo_partida, col_crc]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    df_temp = df.copy()
    
    # 2. Preparar los datos
    # Forzamos a mayúsculas para que 'p' y 'P' se evalúen igual
    df_temp['Num_Partida_Clean'] = df_temp[col_num_partida].fillna('').astype(str).str.strip().str.upper()
    df_temp['Tipo_Partida_Clean'] = df_temp[col_tipo_partida].fillna('').astype(str).str.strip().str.upper()

    # 3. Lógica de la regla
    # A) Detectar caracteres inválidos. 
    # El regex r'[^0-9P,\s]' significa: Encuentra cualquier carácter que NO sea un dígito(0-9), P, coma(,) o espacio(\s).
    mascara_caracteres_invalidos = (df_temp['Num_Partida_Clean'] != '') & df_temp['Num_Partida_Clean'].str.contains(r'[^0-9P,\s]', regex=True)
    
    # B) Detectar inconsistencia de la P y el Código de Predio
    tiene_p = df_temp['Num_Partida_Clean'].str.contains('P')
    # Validamos con y sin tilde por seguridad
    tipo_no_es_codigo = ~df_temp['Tipo_Partida_Clean'].isin(['CÓDIGO DE PREDIO', 'CODIGO DE PREDIO'])
    
    mascara_inconsistencia_p = tiene_p & tipo_no_es_codigo
    
    # Unimos ambas condiciones para encontrar todas las filas con algún error de esta regla
    filas_con_error = df_temp[mascara_caracteres_invalidos | mascara_inconsistencia_p]
    
    # 4. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        num_partida_orig = fila[col_num_partida]
        tipo_partida_orig = fila[col_tipo_partida]
        
        # Saber qué error específico cometió el digitador para darle un mensaje claro
        fallo_caracteres = mascara_caracteres_invalidos.loc[index]
        fallo_logica_p = mascara_inconsistencia_p.loc[index]
        
        mensajes = []
        if fallo_caracteres:
            mensajes.append(f"Contiene caracteres inválidos ('{num_partida_orig}'). Solo se permiten números, la letra 'P'.")
        if fallo_logica_p:
            mensajes.append(f"Contiene una 'P', por lo que el Tipo de Partida DEBE ser 'Código de Predio' (Registrado: '{tipo_partida_orig}').")
            
        desc_error = " Inconsistencia: " + " Además, ".join(mensajes)
        
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