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
    errores = []
    nombre_regla = "IN-1002"
    
    # Verificamos que AMBOS archivos estén cargados
    if 'unidades' not in dfs or 'ingresos' not in dfs:
        return []
        
    df_ua = dfs['unidades'].copy()
    df_in = dfs['ingresos'].copy()
    
    col_crc = 'Código de Referencia Catastral'
    col_predial = 'Código Predial de Rentas'
    col_partida = 'Número de Partida Registral'
    col_cond_num = 'Condición Numérica'
    
    # 1. Verificar columnas estructurales en Unidades Administrativas
    if col_crc not in df_ua.columns or col_predial not in df_ua.columns or col_partida not in df_ua.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Código del Predio (CRC)': f"Error estructural: Faltan columnas en Unidades Administrativas."
        })
        return errores

    # 2. Verificar columnas estructurales en Ingresos
    if col_crc not in df_in.columns or col_cond_num not in df_in.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Código del Predio (CRC)': f"Error estructural: Faltan columnas en Ingresos."
        })
        return errores

    # 3. Preparar los datos
    df_ua['Predial_Clean'] = df_ua[col_predial].fillna('').astype(str).str.strip().str.upper()
    df_ua['Partida_Clean'] = df_ua[col_partida].fillna('').astype(str).str.strip().str.upper()
    
    df_in['Cond_Clean'] = df_in[col_cond_num].fillna('').astype(str).str.strip().str.upper()
    
    df_ua['CRC_Clean'] = df_ua[col_crc].fillna('').astype(str).str.strip()
    df_in['CRC_Clean'] = df_in[col_crc].fillna('').astype(str).str.strip()

    # --- NUEVA LÓGICA DE CEROS ---
    # Detecta si la celda contiene exclusivamente uno o más ceros
    es_predial_puro_cero = df_ua['Predial_Clean'].str.match(r'^0+$')
    es_partida_puro_cero = df_ua['Partida_Clean'].str.match(r'^0+$')

    # 4. Filtrar Unidades Administrativas
    # Condición UA: Predial tiene dato y NO es todo ceros
    cond_ua_predial = (df_ua['Predial_Clean'] != '') & (~es_predial_puro_cero)
    
    # Condición UA: Partida está vacía O es todo ceros
    cond_ua_partida = (df_ua['Partida_Clean'] == '') | (es_partida_puro_cero)
    
    df_ua_filtrado = df_ua[cond_ua_predial & cond_ua_partida]
    
    if df_ua_filtrado.empty:
        return []

    # 5. Cruce relacional (Merge)
    df_cruce = pd.merge(
        df_ua_filtrado, 
        df_in[['CRC_Clean', col_cond_num, 'Cond_Clean']], 
        on='CRC_Clean', 
        how='left'
    )

    # 6. Lógica de error en el cruce
    valores_permitidos = ['AUTO. GEN POR EL TIT. CAT.', 'SIN NÚMERO', 'SIN NUMERO']
    
    mascara_error = ~df_cruce['Cond_Clean'].isin(valores_permitidos)
    filas_con_error = df_cruce[mascara_error]

    # 7. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        valor_predial = fila[col_predial]
        valor_cond_num = fila[col_cond_num] if pd.notna(fila[col_cond_num]) else "No encontrado/Vacío"
        
        desc_error = (
            f"Inconsistencia Relacional: En UA tiene Predial ('{valor_predial}') y Partida vacía/0, "
            f"pero en Ingresos la Condición Numérica es '{valor_cond_num}' "
            f"(Debería ser 'AUTO. GEN POR EL TIT. CAT.' o 'SIN NÚMERO')."
        )
        
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
                'Código del Predio (CRC)': f"Sin CRC válido",
                'Descripción del Error': desc_error
            }
            
        errores.append(error_reporte)
        
    return errores