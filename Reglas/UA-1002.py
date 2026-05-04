import pandas as pd

def descomponer_crc(crc):
    """
    Descompone el CRC aplicando los índices corregidos (23 caracteres).
    """
    if pd.isna(crc) or str(crc).strip() == '':
        return None
        
    crc_str = str(crc).strip()
    # Ajustado a 23 caracteres para que coincida con tus índices
    crc_pad = crc_str.zfill(23) 
    
    try:
        return {
            'Prefix':   crc_pad[0:6],
            'Sector':   crc_pad[6:8],   # 2 dígitos
            'Manzana':  crc_pad[8:11],  # 3 dígitos
            'Lote':     crc_pad[11:14], # 3 dígitos
            'Edifica':  crc_pad[14:16], # 2 dígitos
            'Entrada':  crc_pad[16:18], # 2 dígitos
            'Piso':     crc_pad[18:20], # 2 dígitos
            'Unidad':   crc_pad[20:23], # 3 dígitos
        }
    except Exception:
        return None

def validar(dfs):
    # Extraemos solo el Excel de unidades que es el que necesita esta regla
    if 'unidades' not in dfs: 
        return [] # Si por alguna razón no se cargó, la regla se omite
    df = dfs['unidades'] 
    
    errores = []
    nombre_regla = "UA-1002"
    
    col_clasificacion = 'Clasificación Del Predio'
    col_uso = 'Descripción Del Uso'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [col_clasificacion, col_uso, col_crc]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    # 2. Preparar los datos (limpieza de texto para una comparación segura)
    # Convertimos a mayúsculas y quitamos espacios para evitar falsos negativos por errores de tipeo
    clasif_limpia = df[col_clasificacion].fillna('').astype(str).str.strip().str.upper()
    uso_limpio = df[col_uso].fillna('').astype(str).str.strip().str.upper()

    # 3. Lógica de la regla
    # El error es: Clasificación es CASA HABITACIÓN y Uso es distinto de VIVIENDA
    condicion_error = (clasif_limpia == 'CASA HABITACIÓN') & (uso_limpio != 'VIVIENDA')
    
    filas_con_error = df[condicion_error]
    
    # 4. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        
        # Recuperamos los valores originales (sin mayúsculas forzadas) para mostrarlos en la descripción del error
        valor_original_clasif = fila[col_clasificacion]
        valor_original_uso = fila[col_uso]
        
        desc_error = f"Inconsistencia: Clasificación es '{valor_original_clasif}' pero el Uso registrado es '{valor_original_uso}'."
        
        componentes = descomponer_crc(crc)
        
        if componentes:
            # Omitimos los falsos positivos donde la Unidad es 999
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