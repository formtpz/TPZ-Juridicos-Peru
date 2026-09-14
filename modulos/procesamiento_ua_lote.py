"""Procesamiento puro del reporte de unidades administrativas por lote."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl.styles import Font, PatternFill

from modulos.depuracion_comun import find_column, find_crc_column, normalize_crc, report_delivery_mask


OUTPUT_COLUMNS = [
    "Departamento",
    "Provincia",
    "Distrito",
    "Ubigeo",
    "Código de Referencia Catastral",
    "Sector",
    "Manzana",
    "Lote",
    "Edifica",
    "Entrada",
    "Piso",
    "Unidad",
    "Concat",
    "UC",
    "Número de Partida Registral",
]
SUMMARY_COUNT_COLUMN = "Count of Código de Referencia Catastral"


def extract_crc_components(crc: str) -> dict[str, str]:
    if len(crc) != 24 or not crc.isdigit():
        raise ValueError("El CRC debe contener exactamente 24 dígitos.")
    return {
        "Ubigeo": crc[0:6],
        "Sector": crc[6:8],
        "Manzana": crc[8:11],
        "Lote": crc[11:14],
        "Edifica": crc[14:16],
        "Entrada": crc[16:18],
        "Piso": crc[18:20],
        "Unidad": crc[20:23],
        "Concat": crc[6:14],
    }


def process_report(df: pd.DataFrame, delivery_keys: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    crc_column = find_crc_column(df)
    source_columns = {
        name: find_column(df, name)
        for name in ["Departamento", "Provincia", "Distrito", "Ubigeo"]
    }
    partida_column = find_column(df, "Número de Partida Registral")

    normalized_crc = df[crc_column].map(normalize_crc)
    valid_crc = normalized_crc.fillna("").str.fullmatch(r"\d{24}")
    valid_unit = normalized_crc.fillna("").str[20:23].ne("999")
    ubigeos = normalized_crc.fillna("").str[0:6]
    sector_manzanas = normalized_crc.fillna("").str[6:11]
    selected = valid_crc & valid_unit & report_delivery_mask(ubigeos, sector_manzanas, delivery_keys)

    source = df.loc[selected].copy()
    crc = normalized_crc.loc[selected]
    result = pd.DataFrame(index=source.index)
    for output_name, input_name in source_columns.items():
        result[output_name] = source[input_name]
    result["Código de Referencia Catastral"] = crc
    result["Sector"] = crc.str[6:8]
    result["Manzana"] = crc.str[8:11]
    result["Lote"] = crc.str[11:14]
    result["Edifica"] = crc.str[14:16]
    result["Entrada"] = crc.str[16:18]
    result["Piso"] = crc.str[18:20]
    result["Unidad"] = crc.str[20:23]
    result["Concat"] = crc.str[6:14]
    result["UC"] = result.groupby("Concat")["Concat"].transform("size").astype(int)
    result["Número de Partida Registral"] = source[partida_column]
    result = result[OUTPUT_COLUMNS].reset_index(drop=True)

    counts = result.groupby("Concat", sort=True).size()
    summary_rows = [
        {"Row Labels": str(concat), SUMMARY_COUNT_COLUMN: int(count)}
        for concat, count in counts.items()
    ]
    summary_rows.extend(
        [
            {"Row Labels": "(blank)", SUMMARY_COUNT_COLUMN: None},
            {"Row Labels": "Grand Total", SUMMARY_COUNT_COLUMN: int(len(result))},
        ]
    )
    summary = pd.DataFrame(summary_rows, columns=["Row Labels", SUMMARY_COUNT_COLUMN])
    return result, summary


def build_excel(filtered: pd.DataFrame, summary: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        filtered.to_excel(writer, index=False, sheet_name="Filtrado")
        summary.to_excel(writer, index=False, sheet_name="Sheet1")

        detail_sheet = writer.book["Filtrado"]
        detail_sheet.auto_filter.ref = detail_sheet.dimensions
        header_fill = PatternFill("solid", fgColor="D9EAF7")
        for cell in detail_sheet[1]:
            cell.font = Font(bold=True)
            cell.fill = header_fill
        for column in ["E", "F", "G", "H", "I", "J", "K", "L", "M", "O"]:
            for cell in detail_sheet[column][1:]:
                cell.number_format = "@"
        detail_sheet.column_dimensions["E"].width = 31
        detail_sheet.column_dimensions["M"].width = 12
        detail_sheet.column_dimensions["O"].width = 30

    return output.getvalue()
