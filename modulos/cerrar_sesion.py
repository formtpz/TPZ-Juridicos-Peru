import streamlit as st
from permisos import validar_acceso

def render():
    # =========================
    # Control de acceso
    # =========================
    validar_acceso("Cerrar Sesion")

    st.title("馃毆 Cerrar sesi贸n")

    st.info("Su sesi贸n ser谩 cerrada de forma segura.")

    if st.button("Confirmar cierre de sesi贸n"):
        # =========================
        # Cerrar conexi贸n a BD si existe
        # =========================
        conn = st.session_state.get("conn")
        if conn:
            try:
                conn.close()
            except:
                pass

        # =========================
        # Limpiar sesi贸n
        # =========================
        st.session_state.clear()

        st.success("鉁?Sesi贸n cerrada correctamente")
        st.info("Volviendo al login...")

        # Fuerza recarga para volver a app.py 鈫?login
        st.rerun()
