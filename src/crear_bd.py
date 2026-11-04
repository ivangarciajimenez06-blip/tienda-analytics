# Crea la base de datos vacía de la tienda a partir de sql/schema.sql.

import sqlite3
from pathlib import Path

raiz= Path(__file__).resolve().parent.parent
schema= raiz/"sql" / "schema.sql"
bd=raiz / "data" / "processed" / "tienda.db"

def crear_bd() -> None:
    bd.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(bd)as conexion:
        conexion.executescript(schema.read_text(encoding="utf-8"))
        tablas=conexion.execute( "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").fetchall()

    print(f"Base de datos creada en: {bd}")
    print("Tablas:", ", ".join(t[0] for t in tablas))
if __name__ == "__main__":
    crear_bd()
