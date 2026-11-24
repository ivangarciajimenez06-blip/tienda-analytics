"""Exporta un modelo en estrella para Power BI a data/processed/powerbi/.

Tablas:
    dim_fecha       un día por fila (años completos que cubren todos los datos)
    dim_cliente     cliente + segmento (S7) + probabilidad de volver y acción (S9), sin datos personales
    dim_producto    producto + categoría + proveedor
    fact_ventas     una fila por línea de pedido (todos los estados)
    fact_alertas    una fila por pedido con la puntuación de Isolation Forest (S8)
    fact_campanas   inversión publicitaria por mes y canal

Formato pensado para Power BI en español: separador ";", decimal ",", UTF-8 con BOM y fechas ISO.

Requisitos:
    python src/generar_datos.py
    python src/limpieza.py
    notebooks 03_segmentacion, 04_anomalias y 05_recompra ejecutados (generan los CSV que se cruzan aquí)

Uso:
    python src/exportar_powerbi.py
"""
import sys
from pathlib import Path

import pandas as pd

from bd import leer_sql
from features import tabla_mensual

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_DATOS = RAIZ / "data" / "processed"
CARPETA_SALIDA = CARPETA_DATOS / "powerbi"

# CSV de los notebooks que se cruzan con la BD, y qué notebook los genera
CSV_NOTEBOOKS = {
    "segmentos_clientes.csv": "notebooks/03_segmentacion.ipynb (S7)",
    "pedidos_sospechosos.csv": "notebooks/04_anomalias.ipynb (S8)",
    "riesgo_recompra.csv": "notebooks/05_recompra.ipynb (S9)",
}

# Valores explícitos para los clientes sin puntuación (mejor un texto que una celda vacía en Power BI)
SIN_SEGMENTO = "Sin compras completadas"
SIN_DATOS = "Sin datos"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Valores que deben salir, documentados en las semanas anteriores (se comprueban con asserts)
ACCION_ESPERADA = {"Recuperable": 95, "Probablemente perdido": 92, "No en riesgo": 287}   # S9
PEDIDOS_MARCADOS_ESPERADOS = 121                                                          # S8


# ---------------------------------------------------------------------------------------
# Consultas SQL
# ---------------------------------------------------------------------------------------

# Clientes SIN nombre ni email: para el análisis bastan la ciudad y la fecha de alta
# (minimización de datos personales: no se exporta lo que no se va a usar)
CONSULTA_CLIENTES = """
SELECT
    c.id_cliente,
    c.ciudad,
    c.fecha_alta
FROM clientes AS c
ORDER BY c.id_cliente
"""

# Productos con su categoría y su proveedor (dos JOIN a las tablas maestras)
CONSULTA_PRODUCTOS = """
SELECT
    pr.id_producto,
    pr.nombre        AS nombre_producto,
    ca.nombre        AS categoria,
    pv.nombre        AS proveedor,
    pv.pais          AS pais_proveedor,
    pr.precio        AS precio_catalogo,
    pr.coste         AS coste_catalogo
FROM productos AS pr
    JOIN categorias  AS ca ON ca.id_categoria = pr.id_categoria
    JOIN proveedores AS pv ON pv.id_proveedor = pr.id_proveedor
ORDER BY pr.id_producto
"""

# Una fila por línea de pedido. El importe y el coste se calculan aquí (no se guardan en la BD):
#   importe = cantidad × precio cobrado;  coste = cantidad × coste de catálogo;  margen = importe − coste
# Se incluyen TODOS los estados: las medidas DAX filtran los completados.
CONSULTA_VENTAS = """
SELECT
    d.id_pedido,
    d.id_producto,
    p.id_cliente,
    p.fecha_pedido                                   AS fecha,
    p.estado,
    p.metodo_pago,
    d.cantidad,
    d.precio_unitario,
    d.cantidad * d.precio_unitario                   AS importe,
    d.cantidad * pr.coste                            AS coste,
    d.cantidad * (d.precio_unitario - pr.coste)      AS margen
FROM detalle_pedido AS d
    JOIN pedidos   AS p  ON p.id_pedido   = d.id_pedido
    JOIN productos AS pr ON pr.id_producto = d.id_producto
ORDER BY d.id_pedido, d.id_producto
"""

# Datos de cada pedido para las alertas: cliente, fecha e importe total (suma de sus líneas)
CONSULTA_PEDIDOS = """
SELECT
    p.id_pedido,
    p.id_cliente,
    p.fecha_pedido                       AS fecha,
    SUM(d.cantidad * d.precio_unitario)  AS importe_total
FROM pedidos AS p
    JOIN detalle_pedido AS d ON d.id_pedido = p.id_pedido
GROUP BY p.id_pedido
ORDER BY p.id_pedido
"""

# Campañas: el mes 'AAAA-MM' pasa a fecha (primer día del mes) para relacionarlo con dim_fecha
CONSULTA_CAMPANAS = """
SELECT
    c.id_campana,
    date(c.mes || '-01')  AS fecha_mes,
    c.canal,
    c.inversion
FROM campanas AS c
ORDER BY c.mes, c.canal
"""

# Límites de todas las fechas de los datos (altas, pedidos y campañas) para construir dim_fecha
CONSULTA_LIMITES_FECHAS = """
SELECT MIN(f) AS primera, MAX(f) AS ultima
FROM (
    SELECT fecha_alta          AS f FROM clientes
    UNION ALL
    SELECT fecha_pedido        AS f FROM pedidos
    UNION ALL
    SELECT date(mes || '-01')  AS f FROM campanas
)
"""


# ---------------------------------------------------------------------------------------
# Construcción de las tablas
# ---------------------------------------------------------------------------------------

def leer_csv_notebook(nombre: str) -> pd.DataFrame:
    """Lee un CSV generado por un notebook; si no existe, para con un mensaje que dice qué ejecutar."""
    ruta = CARPETA_DATOS / nombre
    if not ruta.exists():
        sys.exit(f"ERROR: falta {ruta.relative_to(RAIZ)}.\n"
                 f"Ejecuta antes el notebook {CSV_NOTEBOOKS[nombre]}, por ejemplo desde notebooks/:\n"
                 f"    jupyter nbconvert --to notebook --execute --inplace {Path(CSV_NOTEBOOKS[nombre].split()[0]).name}")
    return pd.read_csv(ruta)


def crear_dim_fecha() -> pd.DataFrame:
    """Un día por fila, sin huecos, desde el 1 de enero del primer año hasta el 31 de diciembre del último.

    Se usan años completos porque las funciones de inteligencia de tiempo de DAX (TOTALYTD,
    DATEADD...) necesitan una tabla de fechas continua, y con años completos no hay sorpresas.
    """
    limites = leer_sql(CONSULTA_LIMITES_FECHAS)
    primera = pd.Timestamp(limites.loc[0, "primera"])
    ultima = pd.Timestamp(limites.loc[0, "ultima"])
    dias = pd.date_range(f"{primera.year}-01-01", f"{ultima.year}-12-31", freq="D")
    return pd.DataFrame({
        "fecha": dias.strftime("%Y-%m-%d"),
        "anio": dias.year,
        "mes_num": dias.month,
        "nombre_mes": [MESES[m - 1] for m in dias.month],
        "anio_mes": dias.strftime("%Y-%m"),
        "trimestre": dias.quarter,
        "dia_semana_num": dias.day_of_week + 1,          # 1 = lunes ... 7 = domingo
        "dia_semana": [DIAS[d] for d in dias.day_of_week],
        "temporada_alta": dias.month.isin([11, 12]).astype(int),   # noviembre y diciembre, como en la S6
    })


def crear_dim_cliente() -> pd.DataFrame:
    """Clientes con el segmento de la S7 y la probabilidad de volver y la acción de la S9."""
    clientes = leer_sql(CONSULTA_CLIENTES)
    segmentos = leer_csv_notebook("segmentos_clientes.csv")[["id_cliente", "segmento", "nombre_segmento"]]
    riesgo = leer_csv_notebook("riesgo_recompra.csv")[["id_cliente", "prob_volver", "accion"]]
    dim = clientes.merge(segmentos, on="id_cliente", how="left").merge(riesgo, on="id_cliente", how="left")
    # Clientes sin segmento o sin puntuación: valor explícito
    dim["segmento"] = dim["segmento"].fillna(-1).astype(int)
    dim["nombre_segmento"] = dim["nombre_segmento"].fillna(SIN_SEGMENTO)
    dim["accion"] = dim["accion"].fillna(SIN_DATOS)
    dim["prob_volver"] = dim["prob_volver"].round(6)   # se queda vacío (nulo) si no hay puntuación
    return dim


def crear_dim_producto() -> pd.DataFrame:
    return leer_sql(CONSULTA_PRODUCTOS)


def crear_fact_ventas() -> pd.DataFrame:
    ventas = leer_sql(CONSULTA_VENTAS)
    for col in ["precio_unitario", "importe", "coste", "margen"]:
        ventas[col] = ventas[col].round(2)
    return ventas


def crear_fact_alertas() -> pd.DataFrame:
    """Pedidos con la puntuación de Isolation Forest (S8), más cliente, fecha e importe de la BD."""
    sospechosos = leer_csv_notebook("pedidos_sospechosos.csv")
    alertas = leer_sql(CONSULTA_PEDIDOS).merge(sospechosos, on="id_pedido", how="inner")
    alertas["importe_total"] = alertas["importe_total"].round(2)
    alertas["puntuacion"] = alertas["puntuacion"].round(6)
    alertas["motivo_principal"] = alertas["motivo_principal"].fillna("")   # solo los marcados tienen motivo
    return alertas[["id_pedido", "id_cliente", "fecha", "importe_total", "puntuacion", "ranking",
                    "marcado", "motivo_principal"]].sort_values("id_pedido").reset_index(drop=True)


def crear_fact_campanas() -> pd.DataFrame:
    campanas = leer_sql(CONSULTA_CAMPANAS)
    campanas["inversion"] = campanas["inversion"].round(2)
    return campanas


# ---------------------------------------------------------------------------------------
# Guardado y verificación
# ---------------------------------------------------------------------------------------

def num(valor: float, decimales: int = 2) -> str:
    """1234.567 -> '1.234,57' (formato español, como en los notebooks)."""
    return f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def guardar(tabla: pd.DataFrame, nombre: str) -> Path:
    """CSV para Power BI en español: ';' como separador, ',' como decimal y UTF-8 con BOM.

    lineterminator="\\n" hace que el archivo sea idéntico en Windows y en otros sistemas.
    """
    ruta = CARPETA_SALIDA / f"{nombre}.csv"
    tabla.to_csv(ruta, sep=";", decimal=",", encoding="utf-8-sig", index=False, lineterminator="\n")
    return ruta


def verificar(tablas: dict) -> None:
    """Comprobaciones con assert. Si alguna falla, el script se para con el motivo."""
    fecha, cliente, producto = tablas["dim_fecha"], tablas["dim_cliente"], tablas["dim_producto"]
    ventas, alertas, campanas = tablas["fact_ventas"], tablas["fact_alertas"], tablas["fact_campanas"]

    # 1) Claves de las dimensiones: únicas y sin nulos
    for dim, clave in [(fecha, "fecha"), (cliente, "id_cliente"), (producto, "id_producto")]:
        assert dim[clave].notna().all(), f"Hay nulos en la clave {clave}"
        assert dim[clave].is_unique, f"La clave {clave} tiene duplicados"
    # dim_fecha sin huecos: tantas filas como días entre la primera y la última fecha
    dias = (pd.Timestamp(fecha["fecha"].iloc[-1]) - pd.Timestamp(fecha["fecha"].iloc[0])).days + 1
    assert len(fecha) == dias, "dim_fecha tiene huecos"
    print("OK  claves de las dimensiones únicas, sin nulos, y dim_fecha sin huecos")

    # 2) Cada clave de las tablas de hechos existe en su dimensión
    comprobaciones = [
        (ventas, "id_cliente", cliente, "id_cliente"), (ventas, "id_producto", producto, "id_producto"),
        (ventas, "fecha", fecha, "fecha"), (alertas, "id_cliente", cliente, "id_cliente"),
        (alertas, "fecha", fecha, "fecha"), (campanas, "fecha_mes", fecha, "fecha"),
        (cliente, "fecha_alta", fecha, "fecha"),
    ]
    for hecho, col, dim, clave in comprobaciones:
        huerfanas = ~hecho[col].isin(dim[clave])
        assert not huerfanas.any(), f"{huerfanas.sum()} valores de {col} no están en la dimensión"
    print("OK  todas las claves de los hechos existen en su dimensión")

    # 3) Ingresos de los pedidos completados = los de tabla_mensual() (los del notebook 01 y la S6)
    completados = ventas[ventas["estado"] == "completado"]
    ingresos_export = completados["importe"].sum()
    ingresos_mensual = tabla_mensual()["ingresos"].sum()
    assert abs(ingresos_export - ingresos_mensual) < 0.01, (ingresos_export, ingresos_mensual)
    por_mes = completados.groupby(completados["fecha"].str[:7])["importe"].sum()
    referencia = tabla_mensual().set_index("mes")["ingresos"]
    assert (por_mes - referencia).abs().max() < 0.01, "Los ingresos de algún mes no coinciden"
    print(f"OK  ingresos de pedidos completados = tabla_mensual(): {num(ingresos_export)} € (y mes a mes)")

    # 4) Clientes por acción = lo documentado en la S9
    por_accion = cliente["accion"].value_counts().to_dict()
    for accion, n in ACCION_ESPERADA.items():
        assert por_accion.get(accion) == n, f"{accion}: {por_accion.get(accion)} en lugar de {n}"
    print(f"OK  clientes por acción = S9: {por_accion}")

    # 5) Pedidos marcados = S8
    marcados = int(alertas["marcado"].sum())
    assert marcados == PEDIDOS_MARCADOS_ESPERADOS, marcados
    assert len(alertas) == ventas["id_pedido"].nunique(), "fact_alertas no tiene un pedido por fila"
    print(f"OK  pedidos marcados en fact_alertas = S8: {marcados}")

    # 6) Releer un CSV con el formato de Power BI en español y comprobar los importes
    releido = pd.read_csv(CARPETA_SALIDA / "fact_ventas.csv", sep=";", decimal=",", encoding="utf-8-sig")
    assert releido.columns.tolist() == ventas.columns.tolist()
    assert pd.api.types.is_float_dtype(releido["importe"]), "El importe no se lee como número"
    assert abs(releido["importe"].sum() - ventas["importe"].sum()) < 0.01
    assert (releido["importe"] - ventas["importe"]).abs().max() < 1e-9
    releido_cli = pd.read_csv(CARPETA_SALIDA / "dim_cliente.csv", sep=";", decimal=",", encoding="utf-8-sig")
    assert releido_cli["nombre_segmento"].eq("Compra única").any(), "Las tildes no se leen bien"
    print("OK  fact_ventas.csv releído con sep=';' y decimal=',': importes idénticos; tildes correctas")


def resumen_comprobacion(tablas: dict) -> None:
    """Los números que deben salir en las tarjetas del informe (lista de comprobación de la guía)."""
    ventas, cliente, alertas = tablas["fact_ventas"], tablas["dim_cliente"], tablas["fact_alertas"]
    comp = ventas[ventas["estado"] == "completado"]
    ingresos, coste = comp["importe"].sum(), comp["coste"].sum()
    n_pedidos = comp["id_pedido"].nunique()
    pedidos_estado = ventas.drop_duplicates("id_pedido")["estado"]
    inversion = tablas["fact_campanas"]["inversion"].sum()
    recuperables = cliente.loc[cliente["accion"] == "Recuperable", "id_cliente"]
    marcados = alertas[alertas["marcado"] == 1]
    print("\nNúmeros para la lista de comprobación (todo el periodo, sin filtros):")
    print(f"  Ingresos                         {num(ingresos)} €")
    print(f"  Coste                            {num(coste)} €")
    print(f"  Margen bruto                     {num(ingresos - coste)} €")
    print(f"  % Margen                         {num(100 * (ingresos - coste) / ingresos)} %")
    print(f"  Nº pedidos (completados)         {n_pedidos}")
    print(f"  Ticket medio                     {num(ingresos / n_pedidos)} €")
    print(f"  Nº clientes con compras          {comp['id_cliente'].nunique()}")
    print(f"  % Cancelados y devueltos         {num(100 * pedidos_estado.isin(['cancelado', 'devuelto']).mean())} % "
          f"de {len(pedidos_estado)} pedidos")
    print(f"  Inversión publicitaria           {num(inversion)} €")
    print(f"  Ingresos por € de publicidad     {num(ingresos / inversion)} €")
    print(f"  Clientes recuperables            {len(recuperables)}")
    print(f"  Gasto histórico recuperables     {num(comp.loc[comp['id_cliente'].isin(recuperables), 'importe'].sum())} €")
    print(f"  Pedidos marcados                 {len(marcados)}")
    print(f"  Importe de los pedidos marcados  {num(marcados['importe_total'].sum())} €")
    por_anio = comp.groupby(comp["fecha"].str[:4])["importe"].sum()
    print("  Ingresos acumulados de cada año (hasta el 31 de diciembre o el último dato): "
          + " · ".join(f"{a}: {num(v)} €" for a, v in por_anio.items()))
    ult = comp.groupby(comp["fecha"].str[:7])["importe"].sum().tail(2)
    print(f"  Ingresos {ult.index[-1]}: {num(ult.iloc[-1])} € · mes anterior ({ult.index[0]}): {num(ult.iloc[0])} € · "
          f"variación {num(100 * (ult.iloc[-1] / ult.iloc[0] - 1))} %")


def main() -> None:
    # Primero los CSV de los notebooks: si falta alguno, se para antes de hacer nada
    for nombre in CSV_NOTEBOOKS:
        leer_csv_notebook(nombre)
    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)

    tablas = {
        "dim_fecha": crear_dim_fecha(),
        "dim_cliente": crear_dim_cliente(),
        "dim_producto": crear_dim_producto(),
        "fact_ventas": crear_fact_ventas(),
        "fact_alertas": crear_fact_alertas(),
        "fact_campanas": crear_fact_campanas(),
    }
    print(f"Exportando a {CARPETA_SALIDA.relative_to(RAIZ)}:")
    print(f"  {'tabla':<15}{'filas':>8}{'columnas':>10}")
    for nombre, tabla in tablas.items():
        guardar(tabla, nombre)
        print(f"  {nombre:<15}{len(tabla):>8}{tabla.shape[1]:>10}")
    print()
    verificar(tablas)
    resumen_comprobacion(tablas)


if __name__ == "__main__":
    main()
