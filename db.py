# db.py
import psycopg2
import streamlit as st
from sqlalchemy import create_engine
from urllib.parse import urlparse

@st.cache_resource
def get_connection():
    return psycopg2.connect(st.secrets["db_credentials"]["URI"])

@st.cache_resource
def get_engine():
    """Crea un engine de SQLAlchemy para pandas.read_sql"""
    uri = st.secrets["db_credentials"]["URI"]
    return create_engine(uri)

def execute(query: str, params=None):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(query, params)
        conn.commit()
    finally:
        cur.close()
