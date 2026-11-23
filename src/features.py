"""Variables (features) para los modelos, calculadas a partir de la base de datos.

S6: tabla_mensual() -> una fila por mes con inversión publicitaria y ventas,
    el dataset de la regresión "¿cuánto se vende por cada euro de publicidad?".

S7: tabla_rfm() -> una fila por cliente con recencia, frecuencia y valor monetario (RFM),
    el dataset de la segmentación "¿qué tipos de clientes hay?".

Uso:
    from features import tabla_mensual, umbral_pedidos_extremos, tabla_rfm
    tabla_mensual()                   # pedidos extremos según Q3 + 3·IQR (referencia)
    tabla_mensual(criterio="p995")    # pedidos extremos según el percentil 99,5
    tabla_rfm()                       # RFM de los clientes con al menos un pedido completado
"""
import pandas as pd

from bd import leer_sql

# Un pedido es "extremo" si su importe supera Q3 + K_IQR · IQR del importe por pedido.
# Se usa 3 (y no el 1,5 habitual de los diagramas de caja) porque el importe por pedido
# tiene una cola larga natural: con 1,5 saldrían cientos de pedidos normales. Con 3
# solo se marcan los realmente desproporcionados (el criterio de "outlier extremo" de Tukey).
K_IQR = 3

# Criterio alternativo, más estricto: un pedido es "extremo" si supera el percentil 99,5 del
# importe por pedido (el 0,5 % más grande). Q3 + 3·IQR marca 161 pedidos que suman el 18,3 %
# de los ingresos, muchos de ellos pedidos Premium normales; el P99,5 se queda con los
# realmente excepcionales. Ver notebooks/02_regresion.ipynb, sección 6.
PERCENTIL_ESTRICTO = 0.995
CRITERIOS_EXTREMOS = ("iqr", "p995")

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


def umbral_pedidos_extremos(criterio: str = "iqr") -> dict:
    """Umbral de pedido extremo calculado sobre TODOS los pedidos completados.

    criterio="iqr"  -> Q3 + 3·IQR (referencia)
    criterio="p995" -> percentil 99,5 del importe por pedido (más estricto)

    Los cuartiles y percentiles se calculan en pandas porque SQLite no tiene función de
    percentiles. Devuelve un diccionario para poder mostrar y guardar cada valor.
    """
    if criterio not in CRITERIOS_EXTREMOS:
        raise ValueError(f"criterio debe ser uno de {CRITERIOS_EXTREMOS}, no {criterio!r}")
    importes = leer_sql(CONSULTA_IMPORTE_POR_PEDIDO)["importe"]
    q1, q3 = importes.quantile([0.25, 0.75])
    iqr = q3 - q1
    if criterio == "iqr":
        umbral = q3 + K_IQR * iqr
    else:
        umbral = float(importes.quantile(PERCENTIL_ESTRICTO))
    extremos = importes > umbral
    return {
        "criterio": criterio,
        "q1": round(q1, 2),
        "q3": round(q3, 2),
        "iqr": round(iqr, 2),
        "umbral": round(umbral, 2),
        "n_pedidos": int(len(importes)),
        "n_extremos": int(extremos.sum()),
        "pct_ingresos_extremos": round(float(100 * importes[extremos].sum() / importes.sum()), 2),
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


def tabla_mensual(criterio: str = "iqr") -> pd.DataFrame:
    """Una fila por mes (24) con inversión, pedidos, ingresos, margen y pedidos extremos.

    margen_sin_extremos se añade para estimar la rentabilidad sin depender de unos pocos
    pedidos enormes (ver notebooks/02_regresion.ipynb, sección 7).

    criterio elige qué es un pedido extremo ("iqr" por defecto o "p995", ver
    umbral_pedidos_extremos). Las columnas *_sin_extremos y n_pedidos_extremos usan ese
    criterio; el resto no cambia.

    Solo cuentan los pedidos completados. El umbral de pedidos extremos usado se guarda
    en tabla.attrs["umbral_extremos"] para poder consultarlo después.
    """
    umbral = umbral_pedidos_extremos(criterio)
    tabla = leer_sql(CONSULTA_TABLA_MENSUAL, params={"umbral": umbral["umbral"]})
    tabla.attrs["umbral_extremos"] = umbral
    return tabla


# ---------------------------------------------------------------------------------------
# S7 · Segmentación de clientes (RFM)
# ---------------------------------------------------------------------------------------

# Fecha de corte del análisis: el día siguiente al último pedido de la BD (de cualquier estado).
# Es el "hoy" del análisis: la recencia se mide hasta esta fecha. Se usa el día siguiente para
# que un cliente que compró el último día tenga recencia 1 y no 0. No se usa la fecha real de
# hoy porque los datos son de un periodo cerrado: con date('now') la recencia de todos los
# clientes crecería cada día que pasa y el resultado no sería reproducible.
CONSULTA_FECHA_CORTE = "SELECT date(MAX(fecha_pedido), '+1 day') AS fecha_corte FROM pedidos"

CONSULTA_RFM = f"""
WITH
-- 1) Fecha de corte (una sola fila)
corte AS (
    {CONSULTA_FECHA_CORTE}
),
-- 2) Importe de cada pedido completado, con su cliente y su fecha
pedido_completado AS (
    SELECT
        p.id_pedido,
        p.id_cliente,
        p.fecha_pedido,
        SUM(d.cantidad * d.precio_unitario) AS importe
    FROM pedidos AS p
        JOIN detalle_pedido AS d ON d.id_pedido = p.id_pedido
    WHERE p.estado = 'completado'
    GROUP BY p.id_pedido
),
-- 3) Resumen por cliente: último pedido (R), nº de pedidos (F) y gasto total (M)
por_cliente AS (
    SELECT
        id_cliente,
        MAX(fecha_pedido) AS ultimo_pedido,
        COUNT(*)          AS frecuencia,
        SUM(importe)      AS monetario
    FROM pedido_completado
    GROUP BY id_cliente
)
-- 4) Una fila por cliente. El JOIN (no LEFT JOIN) deja fuera a los clientes sin ningún
--    pedido completado: no tienen recencia ni gasto (ver clientes_sin_compras()).
--    julianday() convierte una fecha en un número de días, así que la resta da días.
SELECT
    c.id_cliente,
    CAST(julianday(corte.fecha_corte) - julianday(r.ultimo_pedido) AS INTEGER) AS recencia_dias,
    r.frecuencia,
    r.monetario,
    CAST(julianday(corte.fecha_corte) - julianday(c.fecha_alta) AS INTEGER)    AS antiguedad_dias,
    r.monetario / r.frecuencia                                                 AS ticket_medio
FROM clientes AS c
    JOIN por_cliente AS r ON r.id_cliente = c.id_cliente
    CROSS JOIN corte
ORDER BY c.id_cliente
"""

# Clientes sin ningún pedido completado (sin pedidos, o solo cancelados o devueltos)
CONSULTA_CLIENTES_SIN_COMPRAS = """
SELECT c.id_cliente
FROM clientes AS c
WHERE NOT EXISTS (
    SELECT 1 FROM pedidos AS p
    WHERE p.id_cliente = c.id_cliente AND p.estado = 'completado'
)
ORDER BY c.id_cliente
"""


def fecha_corte() -> str:
    """Fecha de corte del RFM ('AAAA-MM-DD'): el día siguiente al último pedido de la BD."""
    return leer_sql(CONSULTA_FECHA_CORTE)["fecha_corte"].iloc[0]


def clientes_sin_compras() -> pd.DataFrame:
    """id_cliente de los clientes sin ningún pedido completado (fuera de tabla_rfm())."""
    return leer_sql(CONSULTA_CLIENTES_SIN_COMPRAS)


def tabla_rfm() -> pd.DataFrame:
    """Una fila por cliente con al menos un pedido completado.

    Columnas:
        recencia_dias   días desde su último pedido completado hasta la fecha de corte
        frecuencia      nº de pedidos completados
        monetario       gasto total en pedidos completados (€)
        antiguedad_dias días desde su alta hasta la fecha de corte
        ticket_medio    monetario / frecuencia (€ por pedido)

    Los clientes sin pedidos completados se excluyen: no tienen recencia ni gasto, y meterlos
    con recencia "infinita" y gasto 0 crearía un grupo artificial. Se cuentan aparte con
    clientes_sin_compras(). La fecha de corte y ese recuento se guardan en tabla.attrs.
    """
    tabla = leer_sql(CONSULTA_RFM)
    tabla.attrs["fecha_corte"] = fecha_corte()
    tabla.attrs["n_clientes_sin_compras"] = len(clientes_sin_compras())
    return tabla
