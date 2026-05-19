import pandas as pd

def descomponer_crc(crc):
    """
    Descompone el CRC aplicando los índices (23 caracteres).
    """
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
    # Verificamos que el Excel de Ingresos (por unidad) esté cargado
    if 'ingresos' not in dfs:
        return []
    
    df = dfs['ingresos'].copy()
    errores = []
    nombre_regla = "IN-1003" # Control de duplicidad de ingresos por UA
    
    col_crc = 'Código de Referencia Catastral' 
    
    # Columnas que juntas identifican físicamente la puerta de forma única
    columnas_identificadoras_puerta = ['Tipo Vía', 'Nombre Vía', 'Tipo de Puerta', 'Número Municipal']
    
    # Verificar columnas estructurales en el dataframe
    columnas_requeridas = [col_crc] + columnas_identificadoras_puerta
    for col in columnas_requeridas:
        if col not in df.columns:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Descripción del Error': f"Error estructural: Falta la columna '{col}' en el Excel de Ingresos."
            })
            return errores

    # 1. Limpieza básica (eliminamos filas que no tengan el CRC)
    df_valid = df.dropna(subset=[col_crc])
    df_valid = df_valid[df_valid[col_crc].astype(str).str.strip() != '']
    
    # 2. Estandarizamos los formatos de texto para asegurar una agrupación limpia
    df_valid['CRC_Str'] = df_valid[col_crc].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(23)
    
    for col in columnas_identificadoras_puerta:
        df_valid[col] = df_valid[col].fillna('').astype(str).str.strip().str.upper()
    
    # 3. Emulamos el GROUP BY compuesto de SQL usando todas las variables físicas de la puerta
    agrupadores = ['CRC_Str'] + columnas_identificadoras_puerta
    agrupado = df_valid.groupby(agrupadores).size().reset_index(name='Cantidad')
    
    # Filtramos solo aquellas combinaciones que se repitan más de una vez para una misma UA
    duplicados = agrupado[agrupado['Cantidad'] > 1]
    
    # 4. Construcción del reporte
    for index, fila in duplicados.iterrows():
        crc = fila['CRC_Str']
        t_via = fila['Tipo Vía']
        n_via = fila['Nombre Vía']
        t_puerta = fila['Tipo de Puerta']
        n_municipal = fila['Número Municipal']
        cantidad = fila['Cantidad']
        
        # Construimos un mensaje descriptivo con los datos físicos para que el digitador lo busque rápido
        direccion_puerta = f"{t_via} {n_via}".strip()
        detalles_puerta = f"Puerta: {t_puerta}, N° Municipal: {n_municipal}"
        
        desc_error = (f"Duplicidad relacional: La unidad administrativa tiene asignado el ingreso en "
                      f"'{direccion_puerta}' ({detalles_puerta}) un total de {cantidad} veces de forma duplicada.")
        
        componentes = descomponer_crc(crc)
        
        if componentes:
            # Excluir las unidades de bienes comunes (999) si corresponde
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
                'Descripción del Error': desc_error
            })
        else:
            errores.append({
                'Nombre de la Regla': nombre_regla,
                'Código del Predio (CRC)': crc,
                'Descripción del Error': desc_error
            })

    return errores
