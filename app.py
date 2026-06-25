import streamlit as st
from permisos import obtener_permisos


# =========================
# CONFIGURACIÓN GENERAL
# =========================
st.set_page_config(
    page_title="Procesamiento de Reportes COFOPRI",
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
puesto = usuario.get("puesto")
nombre = usuario.get("nombre")
opciones = obtener_permisos(perfil, puesto, nombre)


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

elif opcion == "Compilar Detalle Errores":
    from modulos.procesar_detalle_muestra import render
    render()

elif opcion == "Filtro de Errores":
    from modulos.filtro_errores import render
    render()
    
elif opcion == "Resultados Calidad":
    from modulos.resultados_calidad import render
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


elif opcion == "Rentas Filtrado":

    from modulos.rentas_filtrado import render
    render()

elif opcion == "Seguimiento Supervisor":
    # Submenú en el sidebar
    with st.sidebar:
        st.markdown("### Submódulos")
        subopcion = st.radio(
            "Seleccione una vista",
            options=["📊 Resumen General", "⏱️ Horas Extra", "📋 Control de Calidad"],
            key="submodulo_supervisor"
        )
    
    if subopcion == "📊 Resumen General":
        from modulos.seguimiento_supervision import render
        render()
    elif subopcion == "⏱️ Horas Extra":
        # Aquí importarás tu módulo de horas extra cuando esté listo
        # from modulos.seguimiento_horas_extra import render
        # render()
        st.info("Módulo en construcción: Horas Extra")
    elif subopcion == "📋 Control de Calidad":
        # Aquí importarás tu módulo de control de calidad cuando esté listo
        # from modulos.seguimiento_calidad import render
        # render()
        st.info("Módulo en construcción: Control de Calidad")
    
elif opcion == "Reporte de Horas":   
    from modulos.reporte_horas import render
    render()
    
# Cerrar sesión
elif opcion == "Cerrar Sesion":

    from modulos.cerrar_sesion import render
    render()
