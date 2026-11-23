"""Acceso a la base de datos de la tienda (data/processed/tienda.db).

Módulo pequeño para reutilizar en los notebooks y scripts de análisis:
    from bd import leer_sql, ventas_por_linea

Las consultas están escritas en SQL a propósito: el trabajo de unir y filtrar
lo hace la base de datos, y pandas solo recibe el resultado.
"""
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

# Configuración (mismo patrón que el resto de scripts)
RAIZ = Path(__file__).resolve().parent.parent
RUTA_BD = RAIZ / "data" / "processed" / "tienda.db"


def leer_sql(consulta: str, params=None) -> pd.DataFrame:
    """Ejecuta una consulta SELECT y devuelve el resultado como DataFrame.

    params: valores para los "?" de la consulta, p. ej. leer_sql("... WHERE estado = ?", ["completado"]).
    Usar "?" en vez de meter el valor en el texto evita errores de comillas e inyección SQL.
    """
    if not RUTA_BD.exists():
        raise FileNotFoundError(f"No existe {RUTA_BD}. Ejecuta antes: python src/generar_datos.py "
                                "y python src/limpieza.py")
    # closing() cierra la conexión al salir del bloque, aunque haya un error
    # (el "with" de sqlite3 por sí solo NO cierra la conexión, solo confirma la transacción)
    with closing(sqlite3.connect(RUTA_BD)) as conexion:
        return pd.read_sql_query(consulta, conexion, params=params)


# Una fila por línea de pedido, con todo lo necesario para analizar ventas
CONSULTA_VENTAS_POR_LINEA = """
SELECT
    -- Pedido
    p.id_pedido,
    p.fecha_pedido,
    p.estado,
    p.metodo_pago,
    -- Cliente
    c.id_cliente,
    c.ciudad,
    c.fecha_alta,
    -- Producto y categoría
    pr.id_producto,
    pr.nombre                          AS producto,
    ca.nombre                          AS categoria,
    pr.precio                          AS precio_catalogo,
    pr.coste,
    -- Línea vendida
    d.cantidad,
    d.precio_unitario,
    d.cantidad * d.precio_unitario     AS importe
FROM detalle_pedido AS d
    JOIN pedidos    AS p  ON p.id_pedido     = d.id_pedido
    JOIN productos  AS pr ON pr.id_producto  = d.id_producto
    JOIN categorias AS ca ON ca.id_categoria = pr.id_categoria
    JOIN clientes   AS c  ON c.id_cliente    = p.id_cliente
ORDER BY p.id_pedido, pr.id_producto
"""


def ventas_por_linea() -> pd.DataFrame:
    """Detalle + pedidos + productos + categorias + clientes, con importe = cantidad x precio.

    Incluye todos los estados (completado, cancelado, devuelto): filtra tú si solo
    quieres las ventas efectivas, p. ej. df[df["estado"] == "completado"].
    """
    df = leer_sql(CONSULTA_VENTAS_POR_LINEA)
    # SQLite guarda las fechas como texto: se convierten a datetime para poder agrupar por mes
    df["fecha_pedido"] = pd.to_datetime(df["fecha_pedido"])
    df["fecha_alta"] = pd.to_datetime(df["fecha_alta"])
    return df
