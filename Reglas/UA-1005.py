import pandas as pd

def descomponer_crc(crc):
    """
    Descompone el CRC aplicando los índices corregidos (23 caracteres).
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
    nombre_regla = "UA-1005"
    
    # Definición de columnas
    col_num_partida = 'Número de Partida Registral'
    col_cond_titular = 'Condición del Titular'
    col_forma_adq = 'Forma de Adquisición'
    col_tipo_doc = 'Tipo de Documento'
    col_tipo_partida = 'Tipo de Partida Registral'
    col_crc = 'Código de Referencia Catastral'
    
    # 1. Verificar columnas estructurales
    columnas_requeridas = [
        col_num_partida, col_cond_titular, col_forma_adq, 
        col_tipo_doc, col_tipo_partida, col_crc
    ]
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: No se encontró la columna '{col}'"
            })
            return errores

    # 2. Preparar los datos (limpieza y conversión a booleanos para saber si tienen datos)
    df_temp = pd.DataFrame()
    df_temp['tiene_num'] = df[col_num_partida].fillna('').astype(str).str.strip() != ''
    df_temp['tiene_cond'] = df[col_cond_titular].fillna('').astype(str).str.strip() != ''
    df_temp['tiene_forma'] = df[col_forma_adq].fillna('').astype(str).str.strip() != ''
    df_temp['tiene_doc'] = df[col_tipo_doc].fillna('').astype(str).str.strip() != ''
    df_temp['tiene_tipo_part'] = df[col_tipo_partida].fillna('').astype(str).str.strip() != ''
    
    # 3. Lógica de la regla
    # Condición 1: Num de partida está lleno, pero falta alguno de los otros 4
    todos_los_otros_llenos = df_temp['tiene_cond'] & df_temp['tiene_forma'] & df_temp['tiene_doc'] & df_temp['tiene_tipo_part']
    error_falta_dato = df_temp['tiene_num'] & ~todos_los_otros_llenos
    
    # Condición 2 (Viceversa): Num de partida está vacío, pero hay datos en alguno de los otros 4
    alguno_otro_lleno = df_temp['tiene_cond'] | df_temp['tiene_forma'] | df_temp['tiene_doc'] | df_temp['tiene_tipo_part']
    error_sobra_dato = ~df_temp['tiene_num'] & alguno_otro_lleno
    
    # Combinamos ambas condiciones de error
    filas_con_error = df[error_falta_dato | error_sobra_dato]
    
    # 4. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        
        # --- Generación de mensaje dinámico para ayudar al digitador ---
        datos_fila = {
            col_cond_titular: str(fila[col_cond_titular]).strip() if pd.notna(fila[col_cond_titular]) else '',
            col_forma_adq: str(fila[col_forma_adq]).strip() if pd.notna(fila[col_forma_adq]) else '',
            col_tipo_doc: str(fila[col_tipo_doc]).strip() if pd.notna(fila[col_tipo_doc]) else '',
            col_tipo_partida: str(fila[col_tipo_partida]).strip() if pd.notna(fila[col_tipo_partida]) else '',
        }
        
        num_partida_val = str(fila[col_num_partida]).strip() if pd.notna(fila[col_num_partida]) else ''
        
        if num_partida_val != '':
            # Caso 1: Tiene Número de partida, pero le faltan los otros
            faltantes = [col for col, val in datos_fila.items() if val == '']
            desc_error = f"Inconsistencia: '{col_num_partida}' está lleno ({num_partida_val}), pero están vacías las columnas: {', '.join(faltantes)}."
        else:
            # Caso 2: No tiene Número de partida, pero llenaron las otras
            sobrantes = [f"'{col}' ({val})" for col, val in datos_fila.items() if val != '']
            desc_error = f"Inconsistencia: '{col_num_partida}' está vacío, pero se registró información en: {', '.join(sobrantes)}."
        
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