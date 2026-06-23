import streamlit as st

# =====================================================
# PERMISOS POR CLAVE (jerárquico)
# =====================================================
PERMISOS = {
    # ---------- Perfiles base (clave = str(perfil)) ----------
    "1": [
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Resultados Calidad",
        "Rentas Filtrado",
        "Seguimiento Supervisor",
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
        "Rentas Filtrado",
        "Cerrar Sesion"
    ],

    # ---------- Perfil + puesto (sobrescriben al perfil base) ----------
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

    # ---------- Perfil + puesto + nombre (máxima especificidad) ----------
    "1;Coordinador;Linnette Ceciliano Calderon": [
        "Reporte de Horas",
        "Depuración de Datos",
        "Reglas",
        "Compilar Detalle Errores",
        "Filtro de Errores",
        "Resultados Calidad",   # opción extra que no tiene el perfil 4 base
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
    perfil_str = str(perfil)  # por si es int
    
    # 1. Clave con nombre (si existe)
    if nombre:
        clave = f"{perfil_str};{puesto};{nombre}" if puesto else f"{perfil_str};{nombre}"
        if clave in PERMISOS:
            return PERMISOS[clave]
    
    # 2. Clave con puesto (si existe)
    if puesto:
        clave = f"{perfil_str};{puesto}"
        if clave in PERMISOS:
            return PERMISOS[clave]
    
    # 3. Clave solo perfil
    return PERMISOS.get(perfil_str, [])

# =====================================================
# FUNCIÓN PARA VALIDAR ACCESO (actualizada)
# =====================================================
def validar_acceso(nombre_pagina: str):
    usuario = st.session_state.get("usuario")
    if not usuario:
        st.warning("Debe iniciar sesión para continuar")
        st.stop()

    perfil = usuario.get("perfil")
    puesto = usuario.get("puesto")   # puede ser None
    nombre = usuario.get("nombre") or usuario.get("usuario")

    if perfil is None:
        st.error("Perfil no definido")
        st.stop()

    permisos = obtener_permisos(perfil, puesto, nombre)

    if nombre_pagina not in permisos:
        st.error("⛔ No tiene permiso para acceder a esta sección")
        st.stop()
