import pandas as pd

def descomponer_codigo_lote(codigo_lote):
    """Descompone un CRC parcial de 14 dígitos (hasta Lote)"""
    if pd.isna(codigo_lote) or str(codigo_lote).strip() == '':
        return None
        
    lote_str = str(codigo_lote).strip().zfill(14) 
    
    try:
        return {
            'Sector':   lote_str[6:8],   
            'Manzana':  lote_str[8:11],  
            'Lote':     lote_str[11:14], 
            'Edifica':  '', 
            'Entrada':  '', 
            'Piso':     '', 
            'Unidad':   '', 
        }
    except Exception:
        return None

def validar(dfs):
    # Verificamos que el Excel de "Ingresos por Lote" esté en el diccionario
    if 'ingresos_lote' not in dfs:
        return []
    
    df = dfs['ingresos_lote'].copy()
    errores = []
    nombre_regla = "INL-1001"
    
    col_lote = 'Código del Lote'
    col_orden = 'Número Orden'
    
    # 1. Validar columnas estructurales
    if col_lote not in df.columns or col_orden not in df.columns:
        errores.append({
            'Nombre de la Regla': nombre_regla,
            'Descripción del Error': f"Error estructural: Faltan las columnas '{col_lote}' o '{col_orden}' en Ingresos por Lote."
        })
        return errores

    # 2. Limpiar datos vacíos
    df_valid = df.dropna(subset=[col_lote])
    df_valid = df_valid[df_valid[col_lote].astype(str).str.strip() != '']
    
    # 3. Agrupar la información por cada Código del Lote
    agrupado = df_valid.groupby(col_lote)
    
    for lote, grupo in agrupado:
        ordenes_raw = grupo[col_orden].dropna().astype(str).str.strip()
        ordenes_numericos = []
        
        # 4. Convertir a enteros para evaluación matemática
        for o in ordenes_raw:
            try:
                num = int(float(o))
                ordenes_numericos.append(num)
            except ValueError:
                pass 
                
        if not ordenes_numericos:
            continue
            
        # Para esta regla, no usamos set() para eliminar duplicados, porque aquí un duplicado SÍ es un error.
        ordenes_ordenados = sorted(ordenes_numericos)
        error_msg = None
        
        # 5. Lógica de validación estricta
        # Condición A: No pueden haber duplicados
        if len(ordenes_ordenados) != len(set(ordenes_ordenados)):
            duplicados = list(set([x for x in ordenes_ordenados if ordenes_ordenados.count(x) > 1]))
            error_msg = f"Existen números de orden duplicados. Se repiten los ingresos: {duplicados}. (Registros encontrados: {ordenes_ordenados})"
            
        # Condición B: Debe empezar siempre en 1
        elif ordenes_ordenados[0] != 1:
            error_msg = f"El primer número de orden registrado es {ordenes_ordenados[0]}, pero la numeración siempre debe empezar en 1. (Registros encontrados: {ordenes_ordenados})"
            
        # Condición C: Deben ser estrictamente consecutivos (1, 2, 3...) sin saltos
        else:
            rango_esperado = list(range(1, max(ordenes_ordenados) + 1))
            if ordenes_ordenados != rango_esperado:
                faltantes = list(set(rango_esperado) - set(ordenes_ordenados))
                faltantes.sort()
                error_msg = f"La numeración no es consecutiva. Faltan los números de orden: {faltantes}. (Registros encontrados: {ordenes_ordenados})"
                
        # 6. Construir reporte si se activó algún error
        if error_msg:
            componentes = descomponer_codigo_lote(lote)
            
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
                    'Descripción del Error': error_msg
                })
            else:
                errores.append({
                    'Nombre de la Regla': nombre_regla,
                    'Código del Predio (CRC)': lote,
                    'Descripción del Error': error_msg
                })

    return errores