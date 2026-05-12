# db.py
import psycopg2
import streamlit as st

@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["db_credentials"]["URI"])


def execute(query: str, params=None):
    """
    Ejecuta una consulta SQL (INSERT, UPDATE, DELETE) con parámetros.
    Similar a la función execute() que existía en db_core.py
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        conn.commit()
    finally:
        cur.close()
