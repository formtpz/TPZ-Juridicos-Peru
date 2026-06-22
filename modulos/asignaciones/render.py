import streamlit as st
from permisos import validar_acceso


def render():
    validar_acceso("Asignaciones")

    st.title("📋 Asignaciones - Piloto Discord")
    st.info("Módulo en construcción. Aquí se gestionarán las asignaciones enviadas a través de Discord.")
