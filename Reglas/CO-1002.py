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
    
    # Convertimos la columna de fechas a objetos datetime de Pandas
    df_valid['Fecha_Format'] = pd.to_datetime(df_valid[col_fecha], errors='coerce')
    df_valid = df_valid.dropna(subset=['Fecha_Format'])
    
    # 3. CORRECCIÓN CLAVE: Agrupamos cortando hasta la Edificación (dígito 16)
    df_valid['CRC_Str'] = df_valid[col_crc].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(23)
    df_valid['Agrupador_Edifica'] = df_valid['CRC_Str'].str[:16]
    
    agrupado = df_valid.groupby('Agrupador_Edifica')
    
    for agrupador, grupo in agrupado:
        diccionario_pisos = {}
        
        # 4. Extraer la fecha más antigua registrada para cada número de piso
        for _, fila in grupo.iterrows():
            valor_piso_raw = str(fila[col_piso]).strip()
            fecha = fila['Fecha_Format']
            
            try:
                num_piso = int(float(valor_piso_raw))
            except ValueError:
                continue
                
            if num_piso not in diccionario_pisos:
                diccionario_pisos[num_piso] = fecha
            else:
                if fecha < diccionario_pisos[num_piso]:
                    diccionario_pisos[num_piso] = fecha
                    
        if len(diccionario_pisos) < 2:
            continue
            
        # 5. Ordenamos los pisos de menor a mayor
        pisos_ordenados = sorted(diccionario_pisos.keys())
        
        error_msg = None
        
        # 6. Evaluación cronológica estricta
        for i in range(1, len(pisos_ordenados)):
            piso_actual = pisos_ordenados[i]
            piso_anterior = pisos_ordenados[i-1]
            
            fecha_actual = diccionario_pisos[piso_actual]
            fecha_anterior = diccionario_pisos[piso_anterior]
            
            if fecha_actual < fecha_anterior:
                # Extraemos la fecha completa en formato Día/Mes/Año para el reporte
                str_fecha_ant = fecha_anterior.strftime('%d/%m/%Y')
                str_fecha_act = fecha_actual.strftime('%d/%m/%Y')
                
                error_msg = (f"Inconsistencia cronológica: El Piso {piso_actual} registra una construcción con fecha "
                             f"{str_fecha_act}, lo cual es anterior a la fecha de soporte del Piso {piso_anterior} ({str_fecha_ant}).")
                break 
                
        # 7. Reportar el error
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
                    'Entrada':  '', # Se dejan vacíos porque es un error de la edificación en general
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
