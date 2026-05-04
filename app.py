import streamlit as st
from permisos import PERMISOS_POR_PERFIL


# =========================
# CONFIGURACIÓN GENERAL
# =========================
st.set_page_config(
    page_title="Sistema de Reportes",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# ESTILOS GLOBALES
# =========================
st.markdown("""
<style>

/* Ocultar menú ⋮ */
#MainMenu {
    visibility: hidden;
}

/* Ocultar footer */
footer {
    visibility: hidden;
}

/* Ocultar iconos superiores (Share, GitHub, etc.) */
div[data-testid="stToolbarActions"] {
    display: none !important;
}

/* Mantener toolbar funcional */
div[data-testid="stToolbar"] {
    min-height: 2rem;
}

/* Quitar decoración superior */
div[data-testid="stDecoration"] {
    display: none;
}

</style>
""", unsafe_allow_html=True)


# =========================
# VERIFICAR SESIÓN
# =========================
usuario = st.session_state.get("usuario")

# =========================
# SI NO HAY SESIÓN → LOGIN
# =========================
if not usuario:

    from modulos.login import render
    render()

    st.stop()


# =========================
# USUARIO LOGUEADO
# =========================
perfil = usuario["perfil"]
opciones = PERMISOS_POR_PERFIL.get(perfil, [])


# =========================
# MENÚ LATERAL
# =========================
with st.sidebar:

    st.image("logo.png", width=250)

    st.markdown("### Menú")

    opcion = st.radio(
        "Seleccione una opción",
        opciones
    )


# =========================
# ROUTER DE MÓDULOS
# =========================

# Depuracion de Datos
if opcion == "Depuración de Datos":

    from modulos.depuracion import render
    render()


# Reglas
elif opcion == "Reglas":

    from modulos.reglas import render
    render()


# Cargar asignaciones
#elif opcion == "Cargar Asignaciones":

#    from modulos.cargar_asignaciones import render
 #   render()


# Reportes producción
#elif opcion == "Reportes Producción":

#    from modulos.produccion import render
#    render()


# RRHH
#elif opcion == "RRHH":

#    from modulos.rrhh import render
#    render()


# Eventos
#elif opcion == "Eventos":

#    from modulos.eventos import render
#    render()


# Historial
#elif opcion == "Historial":

#    from modulos.historial import render
#    render()


# Correcciones
#elif opcion == "Correcciones":

#    from modulos.correcciones import render
#    render()


# Cerrar sesión
elif opcion == "Cerrar Sesion":

    from modulos.cerrar_sesion import render
    render()
