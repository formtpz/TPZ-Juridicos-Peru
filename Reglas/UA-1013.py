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
    # Extraemos solo el Excel de unidades
    if 'unidades' not in dfs: 
        return [] 
    df = dfs['unidades'] 
    
    errores = []
    nombre_regla = "UA-1013"
    
    # Definición de columnas
    col_clasificacion = 'Clasificación Del Predio'
    col_uso = 'Descripción Del Uso'
    col_edifica = 'Nombre de Edifica'
    col_interior = 'Tipo de Interior'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [col_clasificacion, col_uso, col_edifica, col_interior, col_crc]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    df_temp = df.copy()
    
    # 2. Limpieza para búsqueda exacta (convertimos a mayúsculas y quitamos espacios extra)
    df_temp['Clasif_Clean'] = df_temp[col_clasificacion].fillna('').astype(str).str.strip().str.upper()
    
    # 3. Filtramos SOLO los predios clasificados como "TERRENO SIN CONSTRUIR"
    filas_evaluar = df_temp[df_temp['Clasif_Clean'] == 'TERRENO SIN CONSTRUIR']
    
    # 4. Lógica de validación
    for index, fila in filas_evaluar.iterrows():
        crc = fila[col_crc]
        
        # Limpiamos los datos a evaluar, previniendo valores nulos
        uso = str(fila[col_uso]).strip() if pd.notna(fila[col_uso]) else ''
        edifica = str(fila[col_edifica]).strip() if pd.notna(fila[col_edifica]) else ''
        interior = str(fila[col_interior]).strip() if pd.notna(fila[col_interior]) else ''
        
        detalles_error = []
        
        # Condición 1: Uso debe ser igual
        if uso.upper() != 'TERRENO SIN CONSTRUIR':
            # Si está vacío, se indica; si tiene otro valor, se muestra el valor erróneo
            valor_uso = uso if uso != '' else 'Vacío'
            detalles_error.append(f"El Uso reportado es '{valor_uso}'")
            
        # Condición 2: Nombre de Edifica debe estar vacío
        if edifica != '':
            detalles_error.append(f"Registra un Nombre de Edifica ('{edifica}')")
            
        # Condición 3: Tipo de Interior debe estar vacío
        if interior != '':
            detalles_error.append(f"Registra un Tipo de Interior ('{interior}')")
            
        # Si la lista tiene elementos, se incumplió al menos una condición
        if detalles_error:
            desc_error = "Inconsistencia en Terreno Sin Construir: " + ", ".join(detalles_error) + "."
            
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
