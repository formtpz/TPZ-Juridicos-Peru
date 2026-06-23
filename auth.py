# auth.py
import streamlit as st
from db import get_connection, release_connection

def login_usuario(usuario, password):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                usuario,
                nombre,
                perfil,
                puesto,
                supervisor,
                horario
            FROM public.usuarios
            WHERE usuario = %s
              AND contraseña = %s
              AND LOWER(estado) = 'activo'
        """, (usuario.strip(), password.strip()))
        
        user = cur.fetchone()
        if user:
            st.session_state["usuario"] = {
                "cedula": user[0],
                "nombre": user[1],
                "perfil": int(user[2]),
                "puesto": user[3],
                "supervisor": user[4],
                "horario": user[5]
            }
            st.rerun()
        else:
            st.error("Credenciales incorrectas o usuario inactivo")
    finally:
        cur.close()
        release_connection(conn)   # <--- Liberación obligatoria
