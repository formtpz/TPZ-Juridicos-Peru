# db.py
import psycopg2
import streamlit as st
import pandas as pd
from psycopg2 import pool
from urllib.parse import urlparse
import logging

logging.basicConfig(level=logging.INFO)

uri = st.secrets["db_credentials"]["URI"]
result = urlparse(uri)
hostname = result.hostname
database = result.path[1:]
username = result.username
pwd = result.password
port_id = result.port

@st.cache_resource
def get_pool():
    return psycopg2.pool.SimpleConnectionPool(
        2, 100,                     # mínimo 2, máximo 100
        host=hostname,
        dbname=database,
        user=username,
        password=pwd,
        port=port_id
    )

def get_connection():
    """Devuelve una conexión del pool con autocommit activado."""
    pool_obj = get_pool()
    conn = pool_obj.getconn()
    conn.autocommit = True
    return conn

def release_connection(conn):
    """Devuelve la conexión al pool."""
    pool_obj = get_pool()
    pool_obj.putconn(conn)

# Funciones de acceso a datos
def fetch_df(query: str, params=None):
    conn = get_connection()
    try:
        return pd.read_sql_query(query, con=conn, params=params)
    finally:
        release_connection(conn)

def fetch_one(query: str, params=None):
    df = fetch_df(query, params)
    if df.empty:
        return None
    return df.iloc[0].to_dict()

def execute(query: str, params=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error(f"Error en execute: {e}")
        raise
    finally:
        cur.close()
        release_connection(conn)

# (Opcional) get_engine eliminado para evitar uso externo
