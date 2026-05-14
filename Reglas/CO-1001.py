import pandas as pd

def descomponer_crc(crc):
    if pd.isna(crc) or str(crc).strip() == '':
        return None
        
    crc_str = str(crc).strip().zfill(23) 
    
    try:
        return {
            'Prefix':   crc_str[0:6],
            'Sector':   crc_str[6:8],   
            'Manzana':  crc_str[8:11],  
            'Lote':     crc_str[11:14], 
            'Edifica':  crc_str[14:16], 
            'Entrada':  crc_str[16:18], 
            'Piso':     crc_str[18:20], 
            'Unidad':   crc_str[20:23], 
        }
    except Exception:
        return None

def validar(dfs):
    if 'construcciones' not in dfs:
        return []
    
    df = dfs['construcciones'].copy()
    errores = []
    nombre_regla = "CO-1001"
    
    col_crc = 'Código de Referencia Catastral'
    col_piso = 'N° Piso'
    
    if col_crc not in df.columns or col_piso not in df.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Descripción del Error': f"Error estructural: Faltan las columnas '{col_crc}' o '{col_piso}' en Construcciones."
        })
        return errores

    df_valid = df.dropna(subset=[col_crc])
    df_valid = df_valid[df_valid[col_crc].astype(str).str.strip() != '']
    
    # --- CORRECCIÓN CLAVE ---
    # Convertimos a string de 23 dígitos y extraemos hasta la Edificación (dígito 16)
    df_valid['CRC_Str'] = df_valid[col_crc].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(23)
    df_valid['Agrupador_Edifica'] = df_valid['CRC_Str'].str[:16]
    
    # Ahora agrupamos por el edificio base, no por el CRC completo
    agrupado = df_valid.groupby('Agrupador_Edifica')
    
    for agrupador, grupo in agrupado:
        pisos_raw = grupo[col_piso].dropna().astype(str).str.strip()
        pisos_numericos = []
        
        for p in pisos_raw:
            try:
                num = int(float(p))
                pisos_numericos.append(num)
            except ValueError:
                pass 
                
        if not pisos_numericos:
            continue
            
        pisos_unicos = sorted(list(set(pisos_numericos)))
        error_msg = None
        
        if pisos_unicos[0] != 1:
            error_msg = f"El primer piso registrado es {pisos_unicos[0]}, pero la numeración siempre debe empezar en 1. (Pisos encontrados: {pisos_unicos})"
        else:
            rango_esperado = list(range(1, max(pisos_unicos) + 1))
            if pisos_unicos != rango_esperado:
                faltantes = list(set(rango_esperado) - set(pisos_unicos))
                faltantes.sort()
                error_msg = f"La numeración de pisos no es consecutiva. Faltan los pisos: {faltantes}. (Pisos encontrados: {pisos_unicos})"
                
        if error_msg:
            primer_crc_del_grupo = grupo[col_crc].iloc[0]
            componentes = descomponer_crc(primer_crc_del_grupo)
            
            if componentes:
                if componentes['Unidad'] == '999':
                    continue
                    
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Sector':   componentes['Sector'],
                    'Manzana':  componentes['Manzana'],
                    'Lote':     componentes['Lote'],
                    'Edifica':  componentes['Edifica'],
                    'Entrada':  '', # Se dejan vacíos porque el error es del edificio general
                    'Piso':     '', 
                    'Unidad':   '',
                    'Descripción del Error': error_msg
                })
            else:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Código del Predio (CRC)': primer_crc_del_grupo,
                    'Descripción del Error': error_msg
                })

    return errores
