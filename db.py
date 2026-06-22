# db.py
import psycopg2
import streamlit as st
from sqlalchemy import create_engine

def _db_uri():
    return st.secrets["db_credentials"]["URI"]

@st.cache_resource
def _conn_holder():
    return {"conn": psycopg2.connect(_db_uri())}

def get_connection():
    """Returns a live psycopg2 connection, reconnecting automatically if stale."""
    holder = _conn_holder()
    conn = holder["conn"]
    if conn.closed:
        holder["conn"] = psycopg2.connect(_db_uri())
        return holder["conn"]
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT 1")
        finally:
            cur.close()
        if conn.status != psycopg2.extensions.STATUS_READY:
            conn.rollback()
    except psycopg2.Error:
        holder["conn"] = psycopg2.connect(_db_uri())
    return holder["conn"]

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
