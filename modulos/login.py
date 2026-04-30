import streamlit as st
from auth import login_usuario

def render():
    st.image("logo.png", width=600)
    st.title("Sistema de Procesamiento de Reporte de Unidades Administrativas - COFOPRI")
    st.markdown("""
    
    Ingrese sus Credenciales
    """)

    cedula = st.text_input("Cédula")
    password = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        login_usuario(cedula, password)


st.markdown(
    """
    <style>
    /* Oculta el menú de Streamlit (⋮) */
    #MainMenu {visibility: hidden;}

    /* Oculta el footer (GitHub, Share, etc.) */
    footer {visibility: hidden;}

    /* Oculta el header superior */
    header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True
)
