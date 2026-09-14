"""Utilidades compartidas para filtrar reportes catastrales por entregas."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unicodedata

import pandas as pd


ENTREGAS_FILES = {
    "Entregas a COFOPRI": "Entregas_a_cofopri.xlsx",
    "Entregas a Campo": "Entregas_a_campo.xlsx",
}


def normalize_field_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def find_column(df: pd.DataFrame, expected: str, *, fallback_index: int | None = None) -> object:
    """Encuentra una columna ignorando tildes, espacios y puntuación."""
    target = normalize_field_name(expected)
    for column in df.columns:
        normalized = normalize_field_name(column)
        if normalized == target or target in normalized:
            return column
    if fallback_index is not None and len(df.columns) > fallback_index:
        return df.columns[fallback_index]
    raise ValueError(f"No se encontró la columna '{expected}'.")


def find_crc_column(df: pd.DataFrame) -> object:
    """Ubica el CRC y solo usa la quinta columna para encabezados genéricos FieldN."""
    try:
        return find_column(df, "Código de Referencia Catastral")
    except ValueError:
        generic_headers = all(
            re.fullmatch(r"field\d+", normalize_field_name(column))
            for column in df.columns
        )
        if generic_headers and len(df.columns) >= 5:
            return df.columns[4]
        raise


def normalize_identifier(value: object, width: int) -> str | None:
    """Normaliza identificadores enteros sin descartar ceros de texto."""
    if value is None or pd.isna(value):
        return None

    is_numeric_value = not isinstance(value, str)
    text = re.sub(r"\s+", "", str(value).strip())
    if not text:
        return None

    if re.fullmatch(r"\d+", text):
        digits = text
    elif re.fullmatch(r"[+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text):
        try:
            number = Decimal(text)
        except InvalidOperation:
            return None
        if not number.is_finite() or number != number.to_integral_value():
            return None
        digits = format(number.quantize(Decimal(1)), "f")
        is_numeric_value = True
    else:
        return None

    if is_numeric_value and len(digits) < width:
        digits = digits.zfill(width)
    return digits


def normalize_crc(value: object) -> str | None:
    return normalize_identifier(value, 24)


def normalize_concat_sec(value: object, width: int = 5) -> str | None:
    normalized = normalize_identifier(value, width)
    return normalized.zfill(width) if normalized is not None else None


def normalize_ubigeo(value: object) -> str | None:
    normalized = normalize_identifier(value, 6)
    return normalized.zfill(6) if normalized is not None else None


def normalize_segment(value: object, start: int, end: int, pad_length: int | None = None) -> str | None:
    text = normalize_identifier(value, pad_length or end)
    if text is None:
        return None
    if pad_length and len(text) < pad_length:
        text = text.zfill(pad_length)
    return text[start:end] if len(text) >= end else None


def delivery_file_names(source: str) -> list[str]:
    if source == "Ambas":
        return list(ENTREGAS_FILES.values())
    if source not in ENTREGAS_FILES:
        raise ValueError(f"Fuente de entregas desconocida: {source}")
    return [ENTREGAS_FILES[source]]


def load_deliveries(source: str, base_dir: str | Path = "Rentas_resumidos") -> pd.DataFrame:
    frames = []
    for file_name in delivery_file_names(source):
        path = Path(base_dir) / file_name
        frame = pd.read_excel(path, engine="openpyxl")
        frame["fuente_entrega"] = file_name
        frames.append(frame)

    deliveries = pd.concat(frames, ignore_index=True)
    required = {"poligono", "concat_sec"}
    missing = required.difference(deliveries.columns)
    if missing:
        raise ValueError(f"Faltan columnas requeridas en entregas: {sorted(missing)}")
    return deliveries


def prepare_delivery_keys(deliveries: pd.DataFrame, polygons: list[str] | tuple[str, ...]) -> pd.DataFrame:
    """Normaliza y deduplica claves antes de cualquier cruce con un reporte."""
    normalized_polygons = {str(value).strip() for value in polygons}
    selected = deliveries.copy()
    selected["poligono"] = selected["poligono"].astype(str).str.strip()
    selected = selected[selected["poligono"].isin(normalized_polygons)].copy()
    selected["concat_sec_norm"] = selected["concat_sec"].map(normalize_concat_sec)
    if "ubigeo" in selected.columns:
        selected["ubigeo_norm"] = selected["ubigeo"].map(normalize_ubigeo)
    else:
        selected["ubigeo_norm"] = None

    selected = selected.dropna(subset=["concat_sec_norm"])
    source_columns = ["fuente_entrega"] if "fuente_entrega" in selected.columns else []
    selected = selected.drop_duplicates(
        subset=source_columns + ["poligono", "ubigeo_norm", "concat_sec_norm"]
    )
    return selected.reset_index(drop=True)


def report_delivery_mask(
    ubigeos: pd.Series,
    sector_manzanas: pd.Series,
    delivery_keys: pd.DataFrame,
) -> pd.Series:
    """Filtra por Ubigeo+SectorManzana y usa SectorManzana solo si falta Ubigeo."""
    exact_rows = delivery_keys[delivery_keys["ubigeo_norm"].notna()]
    exact_keys = set(zip(exact_rows["ubigeo_norm"], exact_rows["concat_sec_norm"]))
    fallback_keys = set(
        delivery_keys.loc[delivery_keys["ubigeo_norm"].isna(), "concat_sec_norm"]
    )
    pairs = pd.Series(list(zip(ubigeos, sector_manzanas)), index=ubigeos.index)
    return pairs.isin(exact_keys) | sector_manzanas.isin(fallback_keys)
