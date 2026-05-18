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
    # Verificamos que el Excel de Unidades Administrativas esté cargado
    if 'unidades' not in dfs:
        return []
    
    df = dfs['unidades'].copy()
    errores = []
    nombre_regla = "UA-1011" # Secuencia de Unidades Administrativas
    
    col_crc = 'Código de Referencia Catastral'
    
    if col_crc not in df.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Descripción del Error': f"Error estructural: Falta la columna '{col_crc}'"
        })
        return errores

    # 1. Limpieza básica
    df_valid = df.dropna(subset=[col_crc])
    df_valid = df_valid[df_valid[col_crc].astype(str).str.strip() != '']
    
    # 2. Aseguramos la longitud correcta de 23 dígitos
    df_valid['CRC_Str'] = df_valid[col_crc].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(23)
    
    # 3. Emulamos el "WHERE crc_unid <> 999" aislando la unidad exacta (posiciones 21-23)
    df_valid = df_valid[df_valid['CRC_Str'].str[20:23] != '999']
    
    # 4. Emulamos el "GROUP BY ... crc_piso" cortando el string hasta el dígito 20
    df_valid['Agrupador_Piso'] = df_valid['CRC_Str'].str[:20]
    
    agrupado = df_valid.groupby('Agrupador_Piso')
    
    for agrupador, grupo in agrupado:
        # Extraemos la parte final del CRC correspondiente a la unidad
        unidades_raw = grupo['CRC_Str'].str[20:23]
        unidades_numericas = []
        
        for u in unidades_raw:
            try:
                num = int(u)
                unidades_numericas.append(num)
            except ValueError:
                pass
                
        if not unidades_numericas:
            continue
            
        # Utilizamos un set() para ignorar duplicados temporales y validamos la secuencia
        unidades_unicas = sorted(list(set(unidades_numericas)))
        error_msg = None
        
        # Emulamos CASE WHEN min(crc_unid) = 1 THEN 'Correcto'
        if unidades_unicas[0] != 1:
            error_msg = f"Error: La unidad debería iniciar en 001 (Inicia en {str(unidades_unicas[0]).zfill(3)}). Unidades registradas: {unidades_unicas}"
            
        # Emulamos WHEN total_consecutivos = total_unidades THEN 'Consecutivas'
        else:
            rango_esperado = list(range(1, max(unidades_unicas) + 1))
            if unidades_unicas != rango_esperado:
                faltantes = list(set(rango_esperado) - set(unidades_unicas))
                faltantes.sort()
                faltantes_str = [str(f).zfill(3) for f in faltantes]
                error_msg = f"Error: Unidades no consecutivas. Faltan en la secuencia: {faltantes_str}. Unidades registradas: {unidades_unicas}"
                
        # Construcción del reporte para el Excel
        if error_msg:
            primer_crc = grupo[col_crc].iloc[0]
            componentes = descomponer_crc(primer_crc)
            
            if componentes:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Sector':   componentes['Sector'],
                    'Manzana':  componentes['Manzana'],
                    'Lote':     componentes['Lote'],
                    'Edifica':  componentes['Edifica'],
                    'Entrada':  componentes['Entrada'],
                    'Piso':     componentes['Piso'],
                    'Unidad':   '', # Queda en blanco porque el error afecta al piso entero
                    'Descripción del Error': error_msg
                })
            else:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Código del Predio (CRC)': primer_crc,
                    'Descripción del Error': error_msg
                })

    return errores
