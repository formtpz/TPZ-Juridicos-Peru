import streamlit as st

# =====================================================
# PERMISOS POR CLAVE (jerárquico)
# =====================================================
PERMISOS = {
    # Perfiles base (clave = str(perfil))
    "1": [
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Resultados Calidad",
        "RentasFiltrado",
        "Cerrar Sesion",
    ],
    "2": [
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Resultados Calidad",
        "Cerrar Sesion",
    ],
    "3": [
        "Depuración de Datos",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Cerrar Sesion"
    ],
    "4": [
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Cerrar Sesion"
    ],
    "5": [
        "RentasFiltrado",
        "Cerrar Sesion"
    ],

    # Especificaciones por perfil + puesto
    "2;Analista Senior": [
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Resultados Calidad",
        "Cerrar Sesion"
    ],
    "4;Control Calidad": [
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Cerrar Sesion"
    ],

    # Especificaciones por perfil + puesto + nombre
    "4;Control Calidad;Linnette Ceciliano": [
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Resultados Calidad",   # adicional
        "Cerrar Sesion"
    ],
    "2;Analista;Juan Perez": [
        "Depuración de Datos",
        "Filtro de Errores",    # solo algunos
        "Cerrar Sesion"
    ],
}

# =====================================================
# FUNCIÓN PARA OBTENER PERMISOS (jerárquica)
# =====================================================
def obtener_permisos(perfil, puesto=None, nombre=None):
    """
    Devuelve la lista de permisos según la especificidad:
    1. perfil;puesto;nombre (si nombre no es None)
    2. perfil;puesto (si puesto no es None)
    3. perfil (siempre debe existir)
    Si no se encuentra ninguna, devuelve lista vacía.
    """
    # Convertir perfil a string por si es int
    perfil_str = str(perfil)
    
    # Clave con nombre
    if nombre:
        clave = f"{perfil_str};{puesto};{nombre}" if puesto else f"{perfil_str};{nombre}"
        if clave in PERMISOS:
            return PERMISOS[clave]
    
    # Clave con puesto
    if puesto:
        clave = f"{perfil_str};{puesto}"
        if clave in PERMISOS:
            return PERMISOS[clave]
    
    # Clave solo perfil
    if perfil_str in PERMISOS:
        return PERMISOS[perfil_str]
    
    # Si no hay nada, devolver vacío
    return []

# =====================================================
# FUNCIÓN PARA VALIDAR ACCESO (actualizada)
# =====================================================
def validar_acceso(nombre_pagina: str):
    usuario = st.session_state.get("usuario")
    if not usuario:
        st.warning("Debe iniciar sesión para continuar")
        st.stop()

    perfil = usuario.get("perfil")
    puesto = usuario.get("puesto")  # asumimos que existe en sesión
    nombre = usuario.get("nombre") or usuario.get("usuario")

    if perfil is None:
        st.error("Perfil no definido")
        st.stop()

    permisos = obtener_permisos(perfil, puesto, nombre)

    if nombre_pagina not in permisos:
        st.error("⛔ No tiene permiso para acceder a esta sección")
        st.stop()
