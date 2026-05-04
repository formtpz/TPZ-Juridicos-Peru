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
    nombre_regla = "UA-R-1001"
    
    # 1. Verificar que AMBOS archivos estén cargados
    if 'unidades' not in dfs or 'rentas' not in dfs:
        return []
        
    df_ua = dfs['unidades'].copy()
    df_r = dfs['rentas'].copy()
    
    # Definición de columnas
    col_crc = 'Código de Referencia Catastral'
    col_predial_ua = 'Código Predial de Rentas'
    col_interior_ua = 'Número de Interior'
    
    col_predio_r = 'CODIGO_PREDIO'
    col_interior_r = 'INTERIOR'
    
    # 2. Verificar columnas estructurales en Unidades Administrativas
    req_ua = [col_crc, col_predial_ua, col_interior_ua]
    for col in req_ua:
        if col not in df_ua.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: Falta la columna '{col}' en UA."
            })
            return errores

    # 3. Verificar columnas estructurales en Rentas
    req_r = [col_predio_r, col_interior_r]
    for col in req_r:
        if col not in df_r.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': f"Error estructural: Falta la columna '{col}' en Rentas."
            })
            return errores

    # 4. Preparar y limpiar los datos
    # Llaves de cruce
    df_ua['Llave_UA'] = df_ua[col_predial_ua].fillna('').astype(str).str.strip().str.upper()
    df_r['Llave_Rentas'] = df_r[col_predio_r].fillna('').astype(str).str.strip().str.upper()
    
    # Columnas a comparar (quitando ".0" si excel lo interpretó como decimal)
    df_ua['Interior_UA_Clean'] = df_ua[col_interior_ua].fillna('').astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True)
    df_r['Interior_R_Clean'] = df_r[col_interior_r].fillna('').astype(str).str.strip().str.upper().str.replace(r'\.0$', '', regex=True)

    # 5. Filtrar Unidades Administrativas válidas para el cruce
    es_llave_puro_cero = df_ua['Llave_UA'].str.match(r'^0+$')
    df_ua_filtrado = df_ua[(df_ua['Llave_UA'] != '') & (~es_llave_puro_cero)]
    
    if df_ua_filtrado.empty:
        return []

    # 6. Cruce relacional (INNER JOIN)
    # Solo cruzamos si el código predial existe en ambos Excels
    # Eliminamos duplicados en Rentas por si un mismo código viene 2 veces (para no duplicar errores)
    df_r_subset = df_r[['Llave_Rentas', 'Interior_R_Clean', col_interior_r]].drop_duplicates(subset=['Llave_Rentas'])
    
    df_cruce = pd.merge(
        df_ua_filtrado, 
        df_r_subset, 
        left_on='Llave_UA', 
        right_on='Llave_Rentas', 
        how='inner' 
    )

    # 7. Lógica de la regla
    # Condición 1: En el excel de rentas VIENE un dato (no está vacío)
    tiene_dato_rentas = (df_cruce['Interior_R_Clean'] != '')
    
    # Condición 2: El dato NO ES IGUAL al de unidades administrativas
    no_coincide = (df_cruce['Interior_R_Clean'] != df_cruce['Interior_UA_Clean'])
    
    # Aplicamos ambas condiciones
    filas_con_error = df_cruce[tiene_dato_rentas & no_coincide]

    # 8. Construir el reporte
    for index, fila in filas_con_error.iterrows():
        crc = fila[col_crc]
        llave = fila['Llave_UA']
        
        # Recuperar valores originales para el mensaje
        val_orig_ua = fila[col_interior_ua] if pd.notna(fila[col_interior_ua]) and str(fila[col_interior_ua]).strip() != '' else "Vacío"
        val_orig_r = fila[col_interior_r]
        
        desc_error = (
            f"Inconsistencia de Cruce (Código Predial '{llave}'): "
            f"Rentas indica Interior '{val_orig_r}', pero Catastro tiene '{val_orig_ua}'."
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