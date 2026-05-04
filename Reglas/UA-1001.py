import pandas as pd

def descomponer_crc(crc):
    """
    Función de ayuda para segmentar un CRC y formatear sus componentes con ceros.
    Retorna un diccionario con los componentes o None si el CRC es inválido.
    """
    if pd.isna(crc) or str(crc).strip() == '':
        return None
        
    # Asegurarnos de trabajar con texto y quitar espacios
    crc_str = str(crc).strip()
    
    # Supongamos que tu CRC completo debe tener 24 dígitos.
    # Esta función robusta rellena con ceros a la izquierda si falta alguno.
    # Ejemplo: si el Excel le quitó un 0 inicial, esto lo recupera.
    crc_pad = crc_str.zfill(24)
    
    try:
        # Extraer substrings según los anchos fijos de cada componente.
        # Basado en la inferencia de un CRC de 24 dígitos.
        # Prefix(7), Sector(2), Manzana(3), Lote(3), Edifica(2), Entrada(2), Piso(2), Unidad(3)
        return {
            'Prefix':   crc_pad[0:6],
            'Sector':   crc_pad[6:8],   # 2 dígitos (ej: 04)
            'Manzana':  crc_pad[8:11],  # 3 dígitos (ej: 043)
            'Lote':     crc_pad[11:14], # 3 dígitos (ej: 028)
            'Edifica':  crc_pad[14:16], # 2 dígitos (ej: 01)
            'Entrada':  crc_pad[16:18], # 2 dígitos (ej: 01)
            'Piso':     crc_pad[18:20], # 2 dígitos (ej: 01)
            'Unidad':   crc_pad[20:23], # 3 dígitos (ej: 001)
        }
    except Exception as e:
        return None # Si algo sale mal en el split, devolvemos None

def validar(dfs):
    # Extraemos solo el Excel de unidades que es el que necesita esta regla
    if 'unidades' not in dfs: 
        return [] # Si por alguna razón no se cargó, la regla se omite
    df = dfs['unidades'] 
    
    errores = []
    nombre_regla = "UA-1001"
    
    col_tipo_doc = 'Tipo de Documento'
    col_tipo_partida = 'Tipo de Partida Registral'
    col_num_partida = 'Número de Partida Registral'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales (igual que antes)
    columnas_requeridas = [col_tipo_doc, col_tipo_partida, col_num_partida, col_crc]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    # 2. Preparar los datos
    tipo_doc = df[col_tipo_doc].fillna('').astype(str).str.strip()
    tipo_partida = df[col_tipo_partida].fillna('').astype(str).str.strip()
    num_partida = df[col_num_partida].fillna('').astype(str).str.strip()

    # 3. Lógica de la regla
    condicion_error = (tipo_doc != '') & (tipo_partida != '') & (num_partida == '')
    filas_con_error = df[condicion_error]
    
    # 4. Construir la lista de errores para el reporte con el NUEVO FORMATO VISUAL
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        desc_error = f"El '{col_num_partida}' no puede estar vacío porque '{col_tipo_doc}' y '{col_tipo_partida}' contienen información."
        
        # --- NUEVA LÓGICA DE SEGMENTACIÓN ---
        componentes = descomponer_crc(crc)
        
        if componentes:
            # INTEGRACIÓN DE LA REGLA DE OMISIÓN DE UNIDAD '999'
            if componentes['Unidad'] == '999':
                # Si la unidad es 999, consideramos esto un falso positivo y NO lo reportamos.
                continue
            
            # Construir el diccionario de error con todas las columnas segmentadas
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
            # Caso de respaldo: si el CRC es ilegible o nulo, reportamos la fila de excel
            error_reporte = {
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Sin CRC (Fila {index + 2})",
                'Descripción del Error': desc_error
            }
            
        errores.append(error_reporte)
        
    return errores