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
    # Verificamos que el archivo de construcciones haya sido cargado
    if 'construcciones' not in dfs:
        return []
    
    df = dfs['construcciones'].copy()
    errores = []
    nombre_regla = "CO-1001"
    
    col_crc = 'Código de Referencia Catastral'
    col_piso = 'N° Piso'
    
    # 1. Validar columnas estructurales
    if col_crc not in df.columns or col_piso not in df.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Descripción del Error': f"Error estructural: Faltan las columnas '{col_crc}' o '{col_piso}' en Construcciones."
        })
        return errores

    # 2. Limpiar datos vacíos
    df_valid = df.dropna(subset=[col_crc])
    df_valid = df_valid[df_valid[col_crc].astype(str).str.strip() != '']
    
    # 3. Agrupar la información por cada Código de Referencia Catastral
    agrupado = df_valid.groupby(col_crc)
    
    for crc, grupo in agrupado:
        # Extraer todos los pisos registrados para este predio
        pisos_raw = grupo[col_piso].dropna().astype(str).str.strip()
        pisos_numericos = []
        
        # 4. Convertir a enteros para evaluar matemáticamente
        for p in pisos_raw:
            try:
                # Se usa float primero para manejar casos donde Excel exporte "1.0" en vez de "1"
                num = int(float(p))
                pisos_numericos.append(num)
            except ValueError:
                # Si el campo tiene texto (ej. "Sótano", "Azotea"), se ignora para el cálculo de consecutividad numérica
                pass 
                
        if not pisos_numericos:
            continue
            
        # Extraer pisos únicos y ordenarlos de menor a mayor
        # Ej: [1, 1, 2, 4] -> set elimina duplicados -> [1, 2, 4]
        pisos_unicos = sorted(list(set(pisos_numericos)))
        
        error_msg = None
        
        # 5. Condición A: Debe empezar siempre en 1
        if pisos_unicos[0] != 1:
            error_msg = f"El primer piso registrado es {pisos_unicos[0]}, pero la numeración siempre debe empezar en 1. (Pisos encontrados: {pisos_unicos})"
        else:
            # 6. Condición B: Deben ser consecutivos
            # Compara la lista real con una lista teórica ideal (ej: [1,2,3,4])
            rango_esperado = list(range(1, max(pisos_unicos) + 1))
            
            if pisos_unicos != rango_esperado:
                # Identifica cuáles pisos exactos faltan para el mensaje de error
                faltantes = list(set(rango_esperado) - set(pisos_unicos))
                faltantes.sort()
                error_msg = f"La numeración de pisos no es consecutiva. Faltan los pisos: {faltantes}. (Pisos encontrados: {pisos_unicos})"
                
        # 7. Construir reporte si hay error
        if error_msg:
            componentes = descomponer_crc(crc)
            
            if componentes:
                if componentes['Unidad'] == '999':
                    continue
                    
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Sector':   componentes['Sector'],
                    'Manzana':  componentes['Manzana'],
                    'Lote':     componentes['Lote'],
                    'Edifica':  componentes['Edifica'],
                    'Entrada':  componentes['Entrada'],
                    'Piso':     componentes['Piso'], 
                    'Unidad':   componentes['Unidad'],
                    'Descripción del Error': error_msg
                })
            else:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Código del Predio (CRC)': crc,
                    'Descripción del Error': error_msg
                })

    return errores