import pandas as pd

def descomponer_codigo(codigo, tipo='crc'):
    """Descompone el código dependiendo de si es un CRC completo (23) o solo Lote (14)"""
    if pd.isna(codigo) or str(codigo).strip() == '':
        return None
        
    if tipo == 'crc':
        cod_str = str(codigo).strip().replace(".0", "").zfill(23)
        try:
            return {
                'Sector':   cod_str[6:8],   
                'Manzana':  cod_str[8:11],  
                'Lote':     cod_str[11:14], 
                'Edifica':  cod_str[14:16], 
                'Entrada':  cod_str[16:18], 
                'Piso':     cod_str[18:20], 
                'Unidad':   cod_str[20:23], 
            }
        except: return None
    else:
        cod_str = str(codigo).strip().replace(".0", "").zfill(14)
        try:
            return {
                'Sector':   cod_str[6:8],   
                'Manzana':  cod_str[8:11],  
                'Lote':     cod_str[11:14],
                'Edifica':  '', 'Entrada': '', 'Piso': '', 'Unidad': ''
            }
        except: return None

def validar(dfs):
    errores = []
    
    # ==============================================================
    # MÓDULO EST-UA: Conteo total de Unidades Administrativas
    # ==============================================================
    if 'unidades' in dfs:
        df_ua = dfs['unidades'].copy()
        col_crc_ua = 'Código de Referencia Catastral'
        
        if col_crc_ua in df_ua.columns:
            df_ua_valid = df_ua.dropna(subset=[col_crc_ua])
            df_ua_valid = df_ua_valid[df_ua_valid[col_crc_ua].astype(str).str.strip() != '']
            
            df_ua_valid['CRC_Str'] = df_ua_valid[col_crc_ua].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(23)
            
            # Excluir las unidades que terminen en '999'
            df_ua_valid = df_ua_valid[df_ua_valid['CRC_Str'].str[-3:] != '999']
            
            # Agrupar por Lote (los primeros 14 dígitos del CRC)
            df_ua_valid['Agrupador_Lote'] = df_ua_valid['CRC_Str'].str[:14]
            conteo_ua = df_ua_valid.groupby('Agrupador_Lote').size()
            
            # Se iteran TODOS los lotes sin filtrar por cantidad
            for lote, cantidad in conteo_ua.items():
                componentes = descomponer_codigo(lote, tipo='lote')
                # Asignamos estrictamente el valor numérico
                msg = str(cantidad)
                
                if componentes:
                    errores.append({
                        'Nombre de la Regla': 'EST-UA',
                        'Sector':   componentes['Sector'],
                        'Manzana':  componentes['Manzana'],
                        'Lote':     componentes['Lote'],
                        'Edifica':  '', 'Entrada': '', 'Piso': '', 'Unidad': '',
                        'Descripción del Error': msg
                    })
                else:
                    errores.append({
                        'Nombre de la Regla': 'EST-UA',
                        'Código del Predio (CRC)': lote,
                        'Descripción del Error': msg
                    })

    # ==============================================================
    # MÓDULO EST-INL: Conteo total de Ingresos por Lote
    # ==============================================================
    if 'ingresos_lote' in dfs:
        df_inl = dfs['ingresos_lote'].copy()
        col_lote_inl = 'Código del Lote'
        
        if col_lote_inl in df_inl.columns:
            df_inl_valid = df_inl.dropna(subset=[col_lote_inl])
            df_inl_valid = df_inl_valid[df_inl_valid[col_lote_inl].astype(str).str.strip() != '']
            
            df_inl_valid['Lote_Str'] = df_inl_valid[col_lote_inl].astype(str).str.strip().str.replace(".0", "", regex=False).str.zfill(14)
            
            # Agrupar y contar ingresos por cada lote
            conteo_inl = df_inl_valid.groupby('Lote_Str').size()
            
            # Se iteran TODOS los lotes sin filtrar por cantidad
            for lote, cantidad in conteo_inl.items():
                componentes = descomponer_codigo(lote, tipo='lote')
                # Asignamos estrictamente el valor numérico
                msg = str(cantidad)
                
                if componentes:
                    errores.append({
                        'Nombre de la Regla': 'EST-INL',
                        'Sector':   componentes['Sector'],
                        'Manzana':  componentes['Manzana'],
                        'Lote':     componentes['Lote'],
                        'Edifica':  '', 'Entrada': '', 'Piso': '', 'Unidad': '',
                        'Descripción del Error': msg
                    })
                else:
                    errores.append({
                        'Nombre de la Regla': 'EST-INL',
                        'Código del Predio (CRC)': lote,
                        'Descripción del Error': msg
                    })

    return errores
