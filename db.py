# db.py
import streamlit as st
import pandas as pd
from sqlalchemy import text

@st.cache_resource
def get_connection():
    """Retorna una conexión a PostgreSQL usando la URI de secrets."""
    uri = st.secrets["db_credentials"]["URI"]
    return st.connection("postgresql", type="sql", url=uri)

@st.cache_data(ttl=600)
def _fetch_df_cached(query: str, params_tuple=None):
    """Función interna cacheable para SELECTs."""
    conn = get_connection()
    with conn.session as session:
        if params_tuple:
            result = session.execute(text(query), params_tuple)
        else:
            result = session.execute(text(query))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df

def fetch_df(query: str, params=None):
    """Ejecuta SELECT y devuelve DataFrame. params puede ser lista/tupla."""
    if params is not None:
        if isinstance(params, dict):
            params_tuple = tuple(params.values())
        elif isinstance(params, (list, tuple)):
            params_tuple = tuple(params)
        else:
            params_tuple = (params,)
    else:
        params_tuple = None
    return _fetch_df_cached(query, params_tuple)

def fetch_one(query: str, params=None):
    df = fetch_df(query, params)
    return df.iloc[0].to_dict() if not df.empty else None

def execute(query: str, params=None):
    conn = get_connection()
    with conn.session as session:
        if params:
            session.execute(text(query), params)
        else:
            session.execute(text(query))
        session.commit()

def get_engine():
    return get_connection().engine
