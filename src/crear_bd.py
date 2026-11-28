# Crea la base de datos vacía de la tienda a partir de sql/schema.sql.

import sqlite3
from pathlib import Path

RAIZ= Path(__file__).resolve().parent.parent
RUTA_SCHEMA= RAIZ/"sql" / "schema.sql"
RUTA_BD=RAIZ / "data" / "processed" / "tienda.db"

def crear_bd() -> None:
    RUTA_BD.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(RUTA_BD)as conexion:
        conexion.executescript(RUTA_SCHEMA.read_text(encoding="utf-8"))
        tablas=conexion.execute( "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()

    print(f"Base de datos creada en: {RUTA_BD}")
    print("Tablas:", ", ".join(t[0] for t in tablas))
if __name__ == "__main__":
    crear_bd()
