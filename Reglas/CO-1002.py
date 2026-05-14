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
    nombre_regla = "CO-1002"
    
    col_crc = 'Código de Referencia Catastral'
    col_piso = 'N° Piso'
    col_fecha = 'Fecha Construcción'
    
    # 1. Validar columnas estructurales
    if col_crc not in df.columns or col_piso not in df.columns or col_fecha not in df.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Descripción del Error': f"Error estructural: Faltan las columnas necesarias en Construcciones."
        })
        return errores

    # 2. Limpieza básica de datos
    df_valid = df.dropna(subset=[col_crc, col_piso, col_fecha])
    df_valid = df_valid[df_valid[col_crc].astype(str).str.strip() != '']
    
    # Convertimos la columna de fechas a objetos datetime de Pandas (robusto contra años o fechas completas)
    df_valid['Fecha_Format'] = pd.to_datetime(df_valid[col_fecha], errors='coerce')
    
    # Descartamos filas donde la fecha o el piso quedaron nulos tras la conversión
    df_valid = df_valid.dropna(subset=['Fecha_Format'])
    
    # 3. Agrupamos cortando hasta la Edificación (dígito 16)
    df_valid['CRC_Str'] = df_valid[col_crc].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(23)
    df_valid['Agrupador_Edifica'] = df_valid['CRC_Str'].str[:16]
    
    agrupado = df_valid.groupby('Agrupador_Edifica')
    
    for crc, grupo in agrupado:
        diccionario_pisos = {}
        
        # 4. Extraer la fecha más antigua registrada para cada número de piso
        for _, fila in grupo.iterrows():
            valor_piso_raw = str(fila[col_piso]).strip()
            fecha = fila['Fecha_Format']
            
            # Intentar convertir el piso a número entero (ignorando Sótanos/Azoteas en texto)
            try:
                num_piso = int(float(valor_piso_raw))
            except ValueError:
                continue
                
            # Guardamos la fecha mínima (más antigua) para ese piso
            if num_piso not in diccionario_pisos:
                diccionario_pisos[num_piso] = fecha
            else:
                if fecha < diccionario_pisos[num_piso]:
                    diccionario_pisos[num_piso] = fecha
                    
        # Si no hay al menos dos pisos válidos para comparar, pasamos al siguiente CRC
        if len(diccionario_pisos) < 2:
            continue
            
        # 5. Ordenamos los pisos de menor a mayor (1, 2, 3...)
        pisos_ordenados = sorted(diccionario_pisos.keys())
        
        error_msg = None
        
        # 6. Evaluación cronológica: El piso actual no puede ser más antiguo que el piso inferior
        for i in range(1, len(pisos_ordenados)):
            piso_actual = pisos_ordenados[i]
            piso_anterior = pisos_ordenados[i-1]
            
            fecha_actual = diccionario_pisos[piso_actual]
            fecha_anterior = diccionario_pisos[piso_anterior]
            
            # Regla: La fecha más antigua del Piso N debe ser mayor o igual a la del Piso N-1
            if fecha_actual < fecha_anterior:
                año_ant = fecha_anterior.year
                año_act = fecha_actual.year
                error_msg = (f"Inconsistencia cronológica: El Piso {piso_actual} registra una construcción en el año {año_act}, "
                             f"lo cual es anterior a la fecha de soporte del Piso {piso_anterior} (año {año_ant}).")
                break # Rompemos el ciclo al primer error encontrado en el predio
                
        # 7. Reportar el error
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
