"""Módulo Streamlit: unidades administrativas válidas agrupadas por lote."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from permisos import validar_acceso
from modulos.depuracion_comun import (
    load_deliveries,
    prepare_delivery_keys,
)
from modulos.procesamiento_ua_lote import build_excel, process_report


PAGE_NAME = "Unidades Administrativas por Lote"


def read_report(uploaded_file) -> pd.DataFrame:
    workbook = pd.ExcelFile(uploaded_file, engine="openpyxl")
    sheet_name = "data" if "data" in workbook.sheet_names else workbook.sheet_names[0]
    return workbook.parse(sheet_name=sheet_name, dtype=object)


@st.cache_data(show_spinner=False)
def cached_deliveries(source: str) -> pd.DataFrame:
    return load_deliveries(source)


def output_file_name(original_name: str, polygons: list[str]) -> str:
    safe_original = Path(original_name).name
    polygon_label = "_".join(str(item).strip() for item in polygons)
    return f"Filtrado_{polygon_label}_{safe_original}"


def render() -> None:
    validar_acceso(PAGE_NAME)
    st.title("Unidades Administrativas por Lote")
    st.caption(
        "Filtra reportes de unidades administrativas por polígonos de entregas, "
        "excluye la unidad 999 y cuenta las unidades válidas de cada lote."
    )

    source = st.selectbox(
        "Fuente de entregas",
        ["Entregas a COFOPRI", "Entregas a Campo", "Ambas"],
        key="ua_lote_fuente",
    )
    try:
        deliveries = cached_deliveries(source)
    except Exception as exc:
        st.error(f"No se pudieron cargar las entregas: {exc}")
        return

    polygons_available = sorted(deliveries["poligono"].dropna().astype(str).unique())
    polygons = st.multiselect(
        "Seleccione uno o varios polígonos",
        polygons_available,
        key="ua_lote_poligonos",
    )
    uploaded_files = st.file_uploader(
        "Cargar uno o varios reportes Excel",
        type=["xlsx"],
        accept_multiple_files=True,
        key="ua_lote_reportes",
    )

    if not uploaded_files:
        st.info("Suba al menos un reporte Excel para comenzar.")
        return
    if not polygons:
        st.warning("Seleccione al menos un polígono.")
        return
    selection_key = (
        source,
        tuple(polygons),
        tuple((item.name, getattr(item, "size", None)) for item in uploaded_files),
    )
    if st.button("Procesar reportes", type="primary", key="ua_lote_procesar"):
        delivery_keys = prepare_delivery_keys(deliveries, polygons)
        results = []
        if delivery_keys.empty:
            st.warning("No se encontraron claves para los polígonos seleccionados.")
            return

        with st.spinner("Procesando reportes..."):
            for uploaded_file in uploaded_files:
                try:
                    report = read_report(uploaded_file)
                    filtered, summary = process_report(report, delivery_keys)
                    results.append(
                        {
                            "name": uploaded_file.name,
                            "rows": len(filtered),
                            "lots": filtered["Concat"].nunique(),
                            "preview": filtered.head(20),
                            "excel": build_excel(filtered, summary) if not filtered.empty else None,
                        }
                    )
                except Exception as exc:
                    results.append({"name": uploaded_file.name, "error": str(exc)})
        st.session_state["ua_lote_resultados"] = {
            "selection": selection_key,
            "items": results,
        }

    stored = st.session_state.get("ua_lote_resultados")
    if not stored or stored.get("selection") != selection_key:
        return

    for index, result in enumerate(stored["items"]):
        st.subheader(result["name"])
        if "error" in result:
            st.error(f"Error al procesar {result['name']}: {result['error']}")
            continue
        if result["excel"] is None:
            st.warning("No se encontraron unidades administrativas válidas para la selección.")
            continue

        st.write(f"Registros válidos: **{result['rows']:,}** · Lotes: **{result['lots']:,}**")
        st.dataframe(result["preview"], use_container_width=True)
        st.download_button(
            "Descargar resultado",
            data=result["excel"],
            file_name=output_file_name(result["name"], polygons),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"ua_lote_descarga_{index}_{result['name']}",
        )
