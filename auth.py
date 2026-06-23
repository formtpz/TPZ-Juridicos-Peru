# auth.py
import streamlit as st
from db import fetch_one  # <--- Importamos fetch_one en lugar de get_connection

def login_usuario(usuario, password):
    # Limpiar espacios
    usuario_clean = usuario.strip()
    password_clean = password.strip()

    # Consulta usando fetch_one (que ya maneja la conexión con st.connection)
    query = """
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
    """
    user = fetch_one(query, params=[usuario_clean, password_clean])

    if user:
        # user es un diccionario con las claves de los SELECT
        st.session_state["usuario"] = {
            "cedula": user["usuario"],        # mantienes compatibilidad
            "nombre": user["nombre"],
            "perfil": int(user["perfil"]),    # convertimos a int
            "puesto": user["puesto"],
            "supervisor": user["supervisor"],
            "horario": user["horario"]
        }
        st.rerun()
    else:
        st.error("Credenciales incorrectas o usuario inactivo")
