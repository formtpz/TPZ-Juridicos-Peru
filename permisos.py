import streamlit as st


# =====================================================
# PERMISOS POR PERFIL
# =====================================================

PERMISOS_POR_PERFIL = {

    # 1 = Administrador / Coordinador
    1: [
        "Depuración de Datos",
        "Cerrar Sesion"
    ],

    # 2 = RRHH
    2: [
        "Depuración de Datos",
        "Cerrar Sesion"
    ],

    # 3 = Operador
    3: [
        "Depuración de Datos",
        "Cerrar Sesion"
    ],

    # 4 = Control de Calidad
    4: [
        "Depuración de Datos",
        "Cerrar Sesion"
    ],

    # 5 = Supervisor
    5: [
        "Depuración de Datos",
        "Cerrar Sesion"
    ],
}


# =====================================================
# FUNCIÓN PARA VALIDAR ACCESO
# =====================================================

def validar_acceso(nombre_pagina: str):

    usuario = st.session_state.get("usuario")

    # =========================
    # USUARIO NO LOGUEADO
    # =========================
    if not usuario:
        st.warning("Debe iniciar sesión para continuar")
        st.stop()

    perfil = usuario.get("perfil")

    # =========================
    # PERFIL NO VÁLIDO
    # =========================
    if perfil not in PERMISOS_POR_PERFIL:
        st.error("Perfil no reconocido")
        st.stop()

    # =========================
    # PÁGINA NO PERMITIDA
    # =========================
    if nombre_pagina not in PERMISOS_POR_PERFIL[perfil]:
        st.error("⛔ No tiene permiso para acceder a esta sección")
        st.stop()
