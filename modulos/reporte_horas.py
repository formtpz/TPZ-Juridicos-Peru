# modulos/reporte_horas.py
import streamlit as st
import pandas as pd
from datetime import datetime
import pytz

# Usamos db_core para todas las consultas (optimizado con caché y reconexión)
from db_core import fetch_df, fetch_one, execute

# Zona horaria Guatemala
TZ = pytz.timezone('America/Guatemala')
FECHA_BASE_COMPENSACION = "2026-06-01"  # Fecha fija según requerimiento


def render():
    """Función principal que renderiza el módulo 'Reporte de Horas'."""
    
    # --------------------------------
    # Obtener datos del usuario logueado
    # --------------------------------
    usuario_data = st.session_state.get("usuario")
    if not usuario_data:
        st.warning("Debe iniciar sesión")
        st.stop()

    perfil = usuario_data.get("perfil")
    nombre_usuario = usuario_data.get("nombre") or usuario_data.get("usuario")
    puesto = usuario_data.get("puesto", "")

    # Título de la página
    st.title("📋 Reporte de Horas")

    # --------------------------------
    # 1. FORMULARIO DE REGISTRO
    # --------------------------------
    st.subheader("Registro de Horas")

    # Obtener lista de personal activo para el multiselect
    df_personal = fetch_df("SELECT nombre FROM usuarios WHERE estado = 'Activo' ORDER BY nombre")
    lista_personal = df_personal["nombre"].tolist() if not df_personal.empty else []

    col1, col2 = st.columns(2)
    with col1:
        personal_seleccionado = st.multiselect(
            "Personal",
            options=lista_personal,
            help="Seleccione uno o varios empleados"
        )
        fecha_registro = st.date_input(
            "Fecha",
            value=datetime.now(TZ).date(),
            key="fecha_reporte_horas"
        )

    with col2:
        # Lista de motivos (incluyendo los existentes y el nuevo "Horas Compensadas")
        motivos = (
            "Reposición de tiempo", "Cita CCSS", "Entregas", "Incapacidad",
            "Control de Calidad Masivos", "Fallos en Aplicativo o Conexión",
            "Horas Extras",
            "Licencia por Fallecimiento de Familiar", "Licencia por Maternidad, Paternidad o Lactancia",
            "Reunión", "Supervisión", "Vacaciones", "Horas Extra Apoyo Otros Proyectos",
            "Horas Ordinarias Apoyo a Otros Proyectos",
            "Horas Compensadas",   # <--- NUEVO MOTIVO
            "Otros"
        )
        motivo_seleccionado = st.selectbox("Motivo", options=motivos)
        horas = st.number_input(
            "Cantidad de Horas Individuales",
            min_value=0.0,
            step=0.25,
            format="%.2f"
        )
        observaciones = st.text_input("Observaciones", max_chars=60)

    # Botón de registro
    if st.button("Registrar Horas", key="btn_registrar_horas"):
        if not personal_seleccionado:
            st.error("Debe seleccionar al menos una persona.")
        elif horas <= 0:
            st.error("Las horas deben ser mayores a cero.")
        else:
            try:
                marca = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
                for nombre in personal_seleccionado:
                    # Obtener datos del empleado (usuario, puesto, supervisor)
                    empleado = fetch_one(
                        "SELECT usuario, puesto, supervisor FROM usuarios WHERE nombre = %s LIMIT 1",
                        params=[nombre]
                    )
                    if not empleado:
                        st.warning(f"No se encontró información para {nombre}, se saltará.")
                        continue

                    execute(
                        """
                        INSERT INTO otros_registros (
                            marca, usuario, nombre, puesto, supervisor,
                            fecha, motivo, horas, observaciones, reporte, horas_bi
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        params=[
                            marca,
                            empleado["usuario"],
                            nombre,
                            empleado["puesto"],
                            empleado["supervisor"],
                            fecha_registro,
                            motivo_seleccionado,
                            horas,
                            observaciones,
                            nombre_usuario,   # reporte = usuario logueado
                            float(horas)
                        ]
                    )
                st.success("✅ Registro(s) enviado(s) correctamente.")
            except Exception as e:
                st.error(f"❌ Error al guardar: {str(e)}")

    st.divider()

    # --------------------------------
    # 2. RESUMEN DE HORAS DISPONIBLES
    # --------------------------------
    st.subheader("📊 Resumen de Horas Disponibles por Compensar")

    # Consultas para el usuario logueado (nombre = nombre_usuario)
    # Suma de Horas Extras con fecha >= FECHA_BASE_COMPENSACION
    df_extras = fetch_df(
        """
        SELECT COALESCE(SUM(horas), 0) AS total
        FROM otros_registros
        WHERE nombre = %s
          AND motivo = 'Horas Extras'
          AND fecha::date >= %s
        """,
        params=[nombre_usuario, FECHA_BASE_COMPENSACION]
    )
    total_extras = df_extras.iloc[0]["total"] if not df_extras.empty else 0.0

    # Suma de Horas Compensadas con fecha >= FECHA_BASE_COMPENSACION
    df_compensadas = fetch_df(
        """
        SELECT COALESCE(SUM(horas), 0) AS total
        FROM otros_registros
        WHERE nombre = %s
          AND motivo = 'Horas Compensadas'
          AND fecha::date >= %s
        """,
        params=[nombre_usuario, FECHA_BASE_COMPENSACION]
    )
    total_compensadas = df_compensadas.iloc[0]["total"] if not df_compensadas.empty else 0.0

    disponible = total_extras - total_compensadas

    # Mostrar métricas
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Horas Extras (desde 2026-06-01)", f"{total_extras:.2f}")
    col_b.metric("Horas Compensadas (desde 2026-06-01)", f"{total_compensadas:.2f}")
    col_c.metric("Horas Disponibles por Compensar", f"{disponible:.2f}", 
                 delta=f"{disponible:.2f}" if disponible != 0 else None)

    st.divider()

    # --------------------------------
    # 3. HISTORIAL DE REGISTROS REPORTADOS POR EL USUARIO
    # --------------------------------
    st.subheader("📜 Historial de Registros Reportados")

    # Filtros de fecha
    hoy = datetime.now(TZ).date()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_inicio = st.date_input("Fecha de Inicio", value=hoy, key="hist_fecha_inicio")
    with col_f2:
        fecha_fin = st.date_input("Fecha de Finalización", value=hoy, key="hist_fecha_fin")

    if fecha_inicio > fecha_fin:
        st.warning("La fecha de inicio no puede ser mayor a la fecha final.")
    else:
        # Consulta: todos los registros donde reporte = nombre_usuario
        df_historial = fetch_df(
            """
            SELECT id, marca, usuario, nombre, puesto, supervisor,
                   fecha, motivo, horas, observaciones, reporte
            FROM otros_registros
            WHERE reporte = %s
              AND fecha::date >= %s
              AND fecha::date <= %s
            ORDER BY fecha DESC, id DESC
            """,
            params=[nombre_usuario, fecha_inicio, fecha_fin]
        )

        if df_historial.empty:
            st.info("No hay registros en el período seleccionado.")
        else:
            # Mostrar dataframe (se pueden ocultar columnas internas)
            columnas_mostrar = ["id", "fecha", "nombre", "puesto", "motivo", "horas", "observaciones", "reporte"]
            # Asegurarse de que existan
            columnas_disponibles = [col for col in columnas_mostrar if col in df_historial.columns]
            st.dataframe(df_historial[columnas_disponibles], use_container_width=True)

            # Botón para exportar a CSV
            csv = df_historial.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"historial_horas_{nombre_usuario.replace(' ', '_')}_{fecha_inicio}_{fecha_fin}.csv",
                mime="text/csv"
            )
