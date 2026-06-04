# db_correcciones.py
# Módulo para manejar correcciones en SQLite

import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "correcciones.db"

def init_db():
    """Inicializa la base de datos y crea la tabla si no existe"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS correcciones (
            id_predio TEXT PRIMARY KEY,
            Estado TEXT,
            Usuario_Corrigió TEXT,
            Fecha_Corrección TEXT
        )
    """)
    conn.commit()
    conn.close()

def guardar_correccion(id_predio, estado, usuario):
    """Inserta o actualiza una corrección para un predio"""
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO correcciones (id_predio, Estado, Usuario_Corrigió, Fecha_Corrección)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(id_predio) DO UPDATE SET
            Estado=excluded.Estado,
            Usuario_Corrigió=excluded.Usuario_Corrigió,
            Fecha_Corrección=excluded.Fecha_Corrección
    """, (id_predio, estado, usuario, fecha))
    conn.commit()
    conn.close()

def obtener_correcciones():
    """Devuelve todas las correcciones como DataFrame"""
    conn = sqlite3.connect(DB_PATH)
    correcciones_df = pd.read_sql_query("SELECT * FROM correcciones", conn)
    conn.close()
    return correcciones_df

def aplicar_correcciones(df, id_col="id_predio"):
    """Aplica las correcciones guardadas a un DataFrame de backup"""
    correcciones_df = obtener_correcciones()
    if id_col in df.columns:
        df = df.merge(correcciones_df, on=id_col, how="left", suffixes=("", "_corr"))
        for col in ["Estado", "Usuario_Corrigió", "Fecha_Corrección"]:
            if col + "_corr" in df.columns:
                df[col] = df[col + "_corr"].combine_first(df[col])
                df.drop(columns=[col + "_corr"], inplace=True)
    return df
