import pandas as pd

def descomponer_crc(crc):
    if pd.isna(crc) or str(crc).strip() == '':
        return None
        
    crc_pad = str(crc).strip().zfill(23)
    
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
    nombre_regla = "UA-1012" # Secuencia de Entradas
    
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
    
    # 3. Emulamos "WHERE crc_entr <> '99'" 
    # La entrada está en las posiciones 17 y 18 (índices 16:18 en Python)
    df_valid = df_valid[df_valid['CRC_Str'].str[16:18] != '99']
    
    # 4. Agrupamos cortando hasta la Edificación (dígito 16)
    df_valid['Agrupador_Edifica'] = df_valid['CRC_Str'].str[:16]
    
    agrupado = df_valid.groupby('Agrupador_Edifica')
    
    for agrupador, grupo in agrupado:
        # Extraemos solo los dígitos de la entrada
        entradas_raw = grupo['CRC_Str'].str[16:18]
        entradas_numericas = []
        
        for e in entradas_raw:
            try:
                num = int(e)
                entradas_numericas.append(num)
            except ValueError:
                pass
                
        if not entradas_numericas:
            continue
            
        # Utilizamos set() para obtener entradas únicas (equivalente al DISTINCT en SQL)
        entradas_unicas = sorted(list(set(entradas_numericas)))
        error_msg = None
        
        # Emulamos: CASE WHEN min(crc_entr) = 1 THEN 'Correcto'
        if entradas_unicas[0] != 1:
            entr_str = [str(e).zfill(2) for e in entradas_unicas]
            error_msg = f"Error: La entrada debería iniciar en 01 (Inicia en {str(entradas_unicas[0]).zfill(2)}). Entradas registradas: {entr_str}"
            
        # Emulamos: WHEN total_consecutivos = total_entradas THEN 'Consecutivas'
        else:
            rango_esperado = list(range(1, max(entradas_unicas) + 1))
            if entradas_unicas != rango_esperado:
                faltantes = list(set(rango_esperado) - set(entradas_unicas))
                faltantes.sort()
                
                # Formateamos con ceros a la izquierda para el reporte (Ej: 02, 03)
                faltantes_str = [str(f).zfill(2) for f in faltantes]
                entr_str = [str(e).zfill(2) for e in entradas_unicas]
                
                error_msg = f"Error: Entradas no consecutivas. Faltan en la secuencia: {faltantes_str}. Entradas registradas: {entr_str}"
                
        # Construcción del reporte
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
                    'Entrada':  '', # Se deja en blanco porque el error aplica a la edificación completa
                    'Piso':     '',
                    'Unidad':   '', 
                    'Descripción del Error': error_msg
                })
            else:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Código del Predio (CRC)': primer_crc,
                    'Descripción del Error': error_msg
                })

    return errores
