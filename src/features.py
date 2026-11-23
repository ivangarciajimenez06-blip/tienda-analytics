"""Variables (features) para los modelos, calculadas a partir de la base de datos.

S6: tabla_mensual() -> una fila por mes con inversión publicitaria y ventas,
    el dataset de la regresión "¿cuánto se vende por cada euro de publicidad?".

Uso:
    from features import tabla_mensual, umbral_pedidos_extremos
"""
import pandas as pd

from bd import leer_sql

# Un pedido es "extremo" si su importe supera Q3 + K_IQR · IQR del importe por pedido.
# Se usa 3 (y no el 1,5 habitual de los diagramas de caja) porque el importe por pedido
# tiene una cola larga natural: con 1,5 saldrían cientos de pedidos normales. Con 3
# solo se marcan los realmente desproporcionados (el criterio de "outlier extremo" de Tukey).
K_IQR = 3

# Importe de cada pedido completado. Se reutiliza en las dos funciones.
CONSULTA_IMPORTE_POR_PEDIDO = """
SELECT
    p.id_pedido,
    strftime('%Y-%m', p.fecha_pedido)     AS mes,
    SUM(d.cantidad * d.precio_unitario)   AS importe,
    SUM(d.cantidad * pr.coste)            AS coste
FROM pedidos AS p
    JOIN detalle_pedido AS d  ON d.id_pedido   = p.id_pedido
    JOIN productos      AS pr ON pr.id_producto = d.id_producto
WHERE p.estado = 'completado'
GROUP BY p.id_pedido
"""


def umbral_pedidos_extremos() -> dict:
    """Calcula Q1, Q3, IQR y el umbral Q3 + 3·IQR sobre TODOS los pedidos completados.

    Los cuartiles se calculan en pandas porque SQLite no tiene función de percentiles.
    Devuelve un diccionario para poder mostrar y guardar cada valor.
    """
    importes = leer_sql(CONSULTA_IMPORTE_POR_PEDIDO)["importe"]
    q1, q3 = importes.quantile([0.25, 0.75])
    iqr = q3 - q1
    umbral = q3 + K_IQR * iqr
    return {
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "iqr": round(iqr, 2),
        "umbral": round(umbral, 2),
        "n_pedidos": int(len(importes)),
        "n_extremos": int((importes > umbral).sum()),
    }


# Tabla mensual. El "?" se sustituye por el umbral de pedidos extremos.
CONSULTA_TABLA_MENSUAL = f"""
WITH
-- 1) Importe y coste de cada pedido completado
importe_pedido AS (
    {CONSULTA_IMPORTE_POR_PEDIDO}
),
-- 2) Ventas por mes, con y sin los pedidos extremos (importe > umbral)
ventas_mes AS (
    SELECT
        mes,
        COUNT(*)                                            AS n_pedidos,
        SUM(importe)                                        AS ingresos,
        SUM(coste)                                          AS coste_productos,
        SUM(CASE WHEN importe > :umbral THEN 0 ELSE importe END) AS ingresos_sin_extremos,
        SUM(CASE WHEN importe > :umbral THEN 0 ELSE importe - coste END) AS margen_sin_extremos,
        SUM(CASE WHEN importe > :umbral THEN 1 ELSE 0 END)       AS n_pedidos_extremos
    FROM importe_pedido
    GROUP BY mes
),
-- 3) Inversión por mes: un canal por columna (pivot con CASE WHEN)
inversion_mes AS (
    SELECT
        mes,
        SUM(inversion)                                                AS inversion_total,
        SUM(CASE WHEN canal = 'google_ads' THEN inversion ELSE 0 END) AS inversion_google_ads,
        SUM(CASE WHEN canal = 'meta_ads'   THEN inversion ELSE 0 END) AS inversion_meta_ads,
        SUM(CASE WHEN canal = 'email'      THEN inversion ELSE 0 END) AS inversion_email
    FROM campanas
    GROUP BY mes
)
-- 4) Unión por mes. Se parte de las campañas: hay una fila por cada mes del periodo
SELECT
    i.mes,
    CAST(substr(i.mes, 6, 2) AS INTEGER)                            AS mes_del_anio,
    CASE WHEN CAST(substr(i.mes, 6, 2) AS INTEGER) IN (11, 12)
         THEN 1 ELSE 0 END                                          AS temporada_alta,
    i.inversion_total,
    i.inversion_google_ads,
    i.inversion_meta_ads,
    i.inversion_email,
    v.n_pedidos,
    v.ingresos,
    v.coste_productos,
    v.ingresos - v.coste_productos                                  AS margen_bruto,
    v.ingresos_sin_extremos,
    v.margen_sin_extremos,
    v.n_pedidos_extremos
FROM inversion_mes AS i
    LEFT JOIN ventas_mes AS v ON v.mes = i.mes
ORDER BY i.mes
"""


def tabla_mensual() -> pd.DataFrame:
    """Una fila por mes (24) con inversión, pedidos, ingresos, margen y pedidos extremos.

    margen_sin_extremos se añade para estimar la rentabilidad sin depender de unos pocos
    pedidos enormes (ver notebooks/02_regresion.ipynb, sección 7).

    Solo cuentan los pedidos completados. El umbral de pedidos extremos usado se guarda
    en tabla.attrs["umbral_extremos"] para poder consultarlo después.
    """
    umbral = umbral_pedidos_extremos()
    tabla = leer_sql(CONSULTA_TABLA_MENSUAL, params={"umbral": umbral["umbral"]})
    tabla.attrs["umbral_extremos"] = umbral
    return tabla
