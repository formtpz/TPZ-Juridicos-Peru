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
    # Utilizamos el Excel de Construcciones, ya que tiene los pisos físicos
    if 'construcciones' not in dfs:
        return []
    
    df = dfs['construcciones'].copy()
    errores = []
    nombre_regla = "CO-1003" # Consistencia interna de pisos por Unidad Administrativa
    
    col_crc = 'Código de Referencia Catastral'
    col_piso = 'N° Piso'
    
    if col_crc not in df.columns or col_piso not in df.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Descripción del Error': f"Error estructural: Faltan las columnas '{col_crc}' o '{col_piso}' en Construcciones."
        })
        return errores

    # 1. Limpieza básica
    df_valid = df.dropna(subset=[col_crc, col_piso])
    df_valid = df_valid[df_valid[col_crc].astype(str).str.strip() != '']
    
    # 2. Formato estricto a 23 dígitos
    df_valid['CRC_Str'] = df_valid[col_crc].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(23)
    
    # 3. Emulamos "fua.crc_unid <> '999'" (Excluimos bienes comunes usando las posiciones 21-23)
    df_valid = df_valid[df_valid['CRC_Str'].str[20:23] != '999']
    
    # 4. Agrupamos por el CRC COMPLETO (23 dígitos) para evaluar cada unidad de forma individual
    agrupado = df_valid.groupby('CRC_Str')
    
    for crc, grupo in agrupado:
        # Extraemos el piso declarado directamente del CRC (dígitos 19 y 20 -> índices 18:20)
        piso_declarado_str = crc[18:20]
        try:
            piso_declarado = int(piso_declarado_str)
        except ValueError:
            continue # Si hay un error de formato en el CRC, lo ignora esta regla matemática
            
        pisos_raw = grupo[col_piso].dropna().astype(str).str.strip()
        pisos_numericos = []
        
        for p in pisos_raw:
            try:
                num = int(float(p))
                # Emulamos "fuac.numero_piso < 70" (Ignoramos sótanos/mezanines)
                if num < 70:
                    pisos_numericos.append(num)
            except ValueError:
                pass 
                
        if not pisos_numericos:
            continue
            
        pisos_unicos = sorted(list(set(pisos_numericos)))
        mensajes_error = []
        
        # VALIDACIÓN 1: El primer piso físico debe coincidir con el piso del CRC
        primer_piso_fisico = pisos_unicos[0]
        if primer_piso_fisico != piso_declarado:
            mensajes_error.append(f"El código CRC indica que la unidad se ubica en el piso {str(piso_declarado).zfill(2)}, pero sus construcciones inician físicamente en el piso {primer_piso_fisico}")
            
        # VALIDACIÓN 2: Consecutividad interna (para dúplex, tríplex, etc.)
        rango_esperado = list(range(primer_piso_fisico, max(pisos_unicos) + 1))
        if pisos_unicos != rango_esperado:
            faltantes = list(set(rango_esperado) - set(pisos_unicos))
            faltantes.sort()
            mensajes_error.append(f"Los niveles internos de la unidad no son consecutivos (Faltan los pisos físicos: {faltantes})")
            
        # Si se incumplió alguna de las dos validaciones, armamos el reporte
        if mensajes_error:
            desc_error = " | ".join(mensajes_error) + "."
            componentes = descomponer_crc(crc)
            
            if componentes:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Sector':   componentes['Sector'],
                    'Manzana':  componentes['Manzana'],
                    'Lote':     componentes['Lote'],
                    'Edifica':  componentes['Edifica'],
                    'Entrada':  componentes['Entrada'],
                    'Piso':     componentes['Piso'],
                    'Unidad':   componentes['Unidad'],
                    'Descripción del Error': desc_error
                })
            else:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Código del Predio (CRC)': crc,
                    'Descripción del Error': desc_error
                })

    return errores
