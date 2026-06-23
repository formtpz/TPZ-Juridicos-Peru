# modulos/rentas_filtrado.py
import streamlit as st
import pandas as pd
import re
from db import fetch_df   # ya no importamos get_engine

# ============ FUNCIONES DE CARGA CON CACHÉ (usando fetch_df) ============
@st.cache_data(ttl=3600)
def load_filter_data():
    query = """
        SELECT codigo_contribuyente, codigo_predio, manzana, lote, cod_hu 
        FROM public.rentas_vs_predio_urbano
    """
    df = fetch_df(query)
    return df

@st.cache_data(ttl=3600)
def load_full_tables():
    contrib = fetch_df("SELECT * FROM public.rentas_vs_contribuyente")
    construc = fetch_df("SELECT * FROM public.rentas_vs_construcciones")
    predios = fetch_df("SELECT * FROM public.rentas_vs_predio_urbano")
    
    # Reordenar columnas de predios según lo solicitado
    orden_deseado = [
        'codigo_contribuyente', 'codigo_predio', 'manzana', 'lote',
        'codigo_habilitacion_urbana', 'zona_habilitacion', 'fecha_adquisicion',
        'descripcion_del_uso', 'tipo_predio', 'condicion_propiedad',
        'porcentaje_condominio', 'area_terreno', 'area_terreno_comun',
        'area_construida', 'area_construida_comun',
    ]
    columnas_existentes = predios.columns.tolist()
    orden_final = [col for col in orden_deseado if col in columnas_existentes]
    orden_final += [col for col in columnas_existentes if col not in orden_final]
    predios = predios[orden_final]
    
    return contrib, construc, predios

# ============ RESTO DE LA FUNCIÓN render (sin cambios) ============
def render():
    # ... (el resto del código permanece igual, solo cambia la importación de fetch_df)
    # Asegúrate de que las funciones load_filter_data y load_full_tables se llaman igual.
    pass
