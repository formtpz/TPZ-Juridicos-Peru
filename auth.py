# auth.py (sin cambios)
import streamlit as st
from db import get_connection

def login_usuario(usuario, password):
    conn = get_connection()
    cur = conn.cursor()
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
    cur.close()
    # No liberamos explícitamente porque la conexión se devuelve al pool al cerrar
    # Pero para ser más ordenados, podríamos hacer:
    # from db import release_connection
    # release_connection(conn)
    
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
