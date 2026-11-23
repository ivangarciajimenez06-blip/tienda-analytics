"""Limpia los CSV sucios de data/raw/ y los carga en data/processed/tienda.db.

Pasos:
  1. Leer los CSV (los que empiezan por "_verdad_" no son datos de la tienda: se ignoran).
  2. Limpiar cada tabla: textos, fechas, duplicados, negativos, nulos y total_linea.
  3. Contar outliers con IQR SIN eliminarlos (las anomalías se buscan en la S8).
  4. Eliminar filas huérfanas (que apuntan a un cliente, pedido o producto que ya no existe).
  5. Crear la BD con crear_bd.py y cargar las tablas en orden de dependencias.
  6. Escribir el informe de calidad en data/processed/informe_calidad.md.

Ejecutar con: python src/limpieza.py   (después de python src/generar_datos.py)
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

from crear_bd import crear_bd  # se reutiliza la función, no se copia su código

# Configuración
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RAW = RAIZ / "data" / "raw"
CARPETA_PROCESSED = RAIZ / "data" / "processed"
RUTA_BD = CARPETA_PROCESSED / "tienda.db"  # la misma ruta que usa crear_bd.py
RUTA_INFORME = CARPETA_PROCESSED / "informe_calidad.md"

# Orden de carga: primero las tablas de las que dependen otras (por las claves foráneas)
ORDEN_CARGA = ["categorias", "proveedores", "clientes", "productos",
               "pedidos", "detalle_pedido", "campanas"]

# Valores permitidos por los CHECK del esquema
ESTADOS = {"completado", "cancelado", "devuelto"}
METODOS_PAGO = {"tarjeta", "paypal", "bizum", "transferencia"}

# Diferencia máxima (en €) para considerar que total_linea cuadra con cantidad x precio
TOLERANCIA_TOTAL = 0.01


# ---------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------
def anotar(informe: list, tabla: str, problema: str, casos: int, accion: str) -> None:
    """Apunta un problema de calidad para el informe final."""
    informe.append({"tabla": tabla, "problema": problema, "casos": int(casos), "accion": accion})


def leer_csvs() -> dict[str, pd.DataFrame]:
    """Lee todos los CSV de data/raw/ menos los de evaluación (_verdad_*)."""
    tablas = {}
    for ruta in sorted(CARPETA_RAW.glob("*.csv")):
        if ruta.name.startswith("_verdad_"):
            continue  # datos de evaluación para los modelos, nunca van a la BD
        tablas[ruta.stem] = pd.read_csv(ruta, encoding="utf-8")
    return tablas


def quitar_duplicados_exactos(df: pd.DataFrame, tabla: str, informe: list) -> pd.DataFrame:
    """Elimina filas idénticas en todas las columnas (se queda con la primera)."""
    duplicadas = df.duplicated()
    anotar(informe, tabla, "Filas duplicadas exactas", duplicadas.sum(), "Eliminadas (se conserva una)")
    return df[~duplicadas]


def quitar_claves_repetidas(df: pd.DataFrame, clave: list[str], tabla: str,
                            problema: str, informe: list) -> pd.DataFrame:
    """Elimina filas que repiten una clave que tiene que ser única (PK o UNIQUE)."""
    repetidas = df.duplicated(subset=clave)
    anotar(informe, tabla, problema, repetidas.sum(), "Eliminadas (se conserva la primera)")
    return df[~repetidas]


def normalizar_texto(serie: pd.Series, transformar, tabla: str, problema: str,
                     informe: list) -> pd.Series:
    """Aplica una transformación de texto y apunta cuántos valores ha cambiado."""
    nueva = transformar(serie)
    cambiados = (nueva != serie) & serie.notna()
    anotar(informe, tabla, problema, cambiados.sum(), "Normalizado")
    return nueva


def convertir_fechas(serie: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Convierte texto a fecha probando dos formatos: AAAA-MM-DD y dd/mm/aaaa.

    Devuelve (fechas, es_europea). Lo que no encaja en ningún formato queda como NaT
    (fecha vacía o imposible, como 2025-13-45).
    """
    iso = pd.to_datetime(serie, format="%Y-%m-%d", errors="coerce")
    europea = pd.to_datetime(serie, format="%d/%m/%Y", errors="coerce")
    es_europea = iso.isna() & europea.notna()
    return iso.fillna(europea), es_europea


def es_vacio(serie: pd.Series) -> pd.Series:
    """True si el valor es nulo o texto vacío."""
    return serie.isna() | (serie.astype("string").str.strip() == "")


# ---------------------------------------------------------------
# Limpieza de cada tabla
# ---------------------------------------------------------------
def limpiar_tabla_maestra(df: pd.DataFrame, tabla: str, clave: str, informe: list) -> pd.DataFrame:
    """categorias, proveedores, productos y campanas: no se ensucian en la generación,
    pero se revisan igual (duplicados y claves repetidas) por si acaso."""
    df = quitar_duplicados_exactos(df, tabla, informe)
    return quitar_claves_repetidas(df, [clave], tabla, f"{clave} repetido", informe)


def limpiar_pedidos(pedidos: pd.DataFrame, informe: list) -> pd.DataFrame:
    t = "pedidos"
    df = quitar_duplicados_exactos(pedidos, t, informe)

    # Estado: " Completado" / "COMPLETADO" -> "completado"
    df["estado"] = normalizar_texto(df["estado"], lambda s: s.str.strip().str.lower(), t,
                                    "estado con mayúsculas o espacios", informe)
    no_validos = ~df["estado"].isin(ESTADOS) | ~df["metodo_pago"].isin(METODOS_PAGO)
    anotar(informe, t, "estado o metodo_pago fuera de los valores permitidos", no_validos.sum(), "Eliminadas")
    df = df[~no_validos]

    # Sin cliente no sabemos de quién es el pedido: no se puede recuperar
    sin_cliente = df["id_cliente"].isna()
    anotar(informe, t, "id_cliente nulo", sin_cliente.sum(), "Eliminadas (no se puede saber el cliente)")
    df = df[~sin_cliente]
    df["id_cliente"] = df["id_cliente"].astype(int)

    # Fechas: el formato dd/mm/aaaa se recupera; vacías e imposibles no
    fechas, es_europea = convertir_fechas(df["fecha_pedido"])
    vacias = es_vacio(df["fecha_pedido"])
    imposibles = fechas.isna() & ~vacias
    anotar(informe, t, "fecha_pedido en formato dd/mm/aaaa", es_europea.sum(), "Convertida a AAAA-MM-DD")
    anotar(informe, t, "fecha_pedido nula o vacía", vacias.sum(), "Eliminadas (no se puede recuperar)")
    anotar(informe, t, "fecha_pedido imposible (p. ej. 2025-13-45)", imposibles.sum(),
           "Eliminadas (no se puede recuperar)")
    df["fecha_pedido"] = fechas.dt.strftime("%Y-%m-%d")
    df = df[fechas.notna()]

    return quitar_claves_repetidas(df, ["id_pedido"], t, "id_pedido repetido", informe)


def limpiar_clientes(clientes: pd.DataFrame, pedidos: pd.DataFrame, informe: list) -> pd.DataFrame:
    """pedidos (ya limpios) se usa para recalcular la fecha de alta que falte."""
    t = "clientes"
    df = quitar_duplicados_exactos(clientes, t, informe)

    df["email"] = normalizar_texto(df["email"], lambda s: s.str.strip().str.lower(), t,
                                   "email con mayúsculas o espacios", informe)
    df["ciudad"] = normalizar_texto(df["ciudad"], lambda s: s.str.strip().str.title(), t,
                                    "ciudad con mayúsculas/minúsculas incorrectas", informe)

    # El email es obligatorio y único: sin él no se puede identificar al cliente
    sin_email = es_vacio(df["email"])
    anotar(informe, t, "email nulo", sin_email.sum(),
           "Eliminadas (y después sus pedidos, por huérfanos)")
    df = df[~sin_email]

    # Fecha de alta: el formato dd/mm/aaaa se recupera. Si está vacía o es imposible,
    # se usa la fecha de su primer pedido (el alta no puede ser posterior a su primera compra)
    fechas, es_europea = convertir_fechas(df["fecha_alta"])
    anotar(informe, t, "fecha_alta en formato dd/mm/aaaa", es_europea.sum(), "Convertida a AAAA-MM-DD")
    sin_fecha = fechas.isna()
    primer_pedido = pd.to_datetime(pedidos.groupby("id_cliente")["fecha_pedido"].min())
    recuperada = df["id_cliente"].map(primer_pedido)
    se_recupera = sin_fecha & recuperada.notna()
    anotar(informe, t, "fecha_alta nula, vacía o imposible", sin_fecha.sum(),
           f"{se_recupera.sum()} recalculadas con la fecha del primer pedido; "
           f"{(sin_fecha & ~se_recupera).sum()} eliminadas (cliente sin pedidos)")
    fechas = fechas.fillna(recuperada)
    df["fecha_alta"] = fechas.dt.strftime("%Y-%m-%d")
    df = df[fechas.notna()]

    df = quitar_claves_repetidas(df, ["id_cliente"], t, "id_cliente repetido", informe)
    return quitar_claves_repetidas(df, ["email"], t, "email repetido (UNIQUE)", informe)


def limpiar_detalle(detalle: pd.DataFrame, informe: list) -> pd.DataFrame:
    t = "detalle_pedido"
    df = quitar_duplicados_exactos(detalle, t, informe)

    # Negativos: un signo menos mal exportado; el valor absoluto es la cantidad real
    negativas = df["cantidad"] < 0
    anotar(informe, t, "cantidad negativa", negativas.sum(), "Corregida con valor absoluto (.abs())")
    df["cantidad"] = df["cantidad"].abs()

    # Nulos: se recalculan con total_linea = cantidad x precio_unitario
    sin_cantidad = df["cantidad"].isna()
    cantidad_calc = df["total_linea"] / df["precio_unitario"]
    # Solo vale si sale un número entero positivo
    cantidad_ok = sin_cantidad & ((cantidad_calc - cantidad_calc.round()).abs() < 0.01) & (cantidad_calc.round() > 0)
    df.loc[cantidad_ok, "cantidad"] = cantidad_calc[cantidad_ok].round()
    anotar(informe, t, "cantidad nula", sin_cantidad.sum(),
           f"{cantidad_ok.sum()} recalculadas con total_linea / precio_unitario; "
           f"{(sin_cantidad & ~cantidad_ok).sum()} eliminadas")

    sin_precio = df["precio_unitario"].isna()
    precio_calc = (df["total_linea"] / df["cantidad"]).round(2)
    precio_ok = sin_precio & (precio_calc > 0)
    df.loc[precio_ok, "precio_unitario"] = precio_calc[precio_ok]
    anotar(informe, t, "precio_unitario nulo", sin_precio.sum(),
           f"{precio_ok.sum()} recalculados con total_linea / cantidad; "
           f"{(sin_precio & ~precio_ok).sum()} eliminados")

    df = df[df["cantidad"].notna() & df["precio_unitario"].notna()]
    df["cantidad"] = df["cantidad"].astype(int)

    # total_linea incoherente: se confía en cantidad y precio_unitario (son los que van a la BD;
    # total_linea es un campo calculado de la exportación) y la fila se conserva
    incoherente = (df["total_linea"] - df["cantidad"] * df["precio_unitario"]).abs() > TOLERANCIA_TOTAL
    anotar(informe, t, "total_linea distinto de cantidad x precio_unitario", incoherente.sum(),
           "Se conservan cantidad y precio_unitario; total_linea se descarta")
    df = df.drop(columns="total_linea")  # no existe en la BD

    return quitar_claves_repetidas(df, ["id_pedido", "id_producto"], t,
                                   "producto repetido en un pedido (PK)", informe)


# ---------------------------------------------------------------
# Outliers (solo se cuentan) y huérfanos
# ---------------------------------------------------------------
def contar_outliers_iqr(serie: pd.Series) -> int:
    """Cuenta los valores fuera de [Q1 - 1,5·IQR, Q3 + 1,5·IQR]."""
    q1, q3 = serie.quantile([0.25, 0.75])
    iqr = q3 - q1
    return int(((serie < q1 - 1.5 * iqr) | (serie > q3 + 1.5 * iqr)).sum())


def contar_outliers(detalle: pd.DataFrame, productos: pd.DataFrame) -> list[dict]:
    """IQR solo informativo: NO se elimina nada, las anomalías tienen que llegar a la BD."""
    precio_catalogo = detalle["id_producto"].map(productos.set_index("id_producto")["precio"])
    return [
        {"variable": "cantidad por línea", "outliers": contar_outliers_iqr(detalle["cantidad"])},
        {"variable": "precio_unitario / precio de catálogo",
         "outliers": contar_outliers_iqr(detalle["precio_unitario"] / precio_catalogo)},
        {"variable": "líneas por pedido",
         "outliers": contar_outliers_iqr(detalle.groupby("id_pedido").size())},
    ]


def eliminar_huerfanos(tablas: dict[str, pd.DataFrame], informe: list) -> None:
    """Quita filas que apuntan a algo que ya no existe. El orden importa:
    primero pedidos (por los clientes eliminados) y después detalle (por esos pedidos)."""
    pedidos, detalle = tablas["pedidos"], tablas["detalle_pedido"]

    huerfanos = ~pedidos["id_cliente"].isin(tablas["clientes"]["id_cliente"])
    anotar(informe, "pedidos", "pedido de un cliente que no existe", huerfanos.sum(), "Eliminadas")
    pedidos = pedidos[~huerfanos]

    sin_pedido = ~detalle["id_pedido"].isin(pedidos["id_pedido"])
    sin_producto = ~detalle["id_producto"].isin(tablas["productos"]["id_producto"])
    anotar(informe, "detalle_pedido", "línea de un pedido que no existe", sin_pedido.sum(), "Eliminadas")
    anotar(informe, "detalle_pedido", "línea de un producto que no existe", sin_producto.sum(), "Eliminadas")
    detalle = detalle[~sin_pedido & ~sin_producto]

    # Pedidos que se quedan sin ninguna línea: se cuentan pero no se borran
    # (el pedido existió; simplemente su detalle se perdió en la exportación)
    vacios = ~pedidos["id_pedido"].isin(detalle["id_pedido"])
    anotar(informe, "pedidos", "pedido sin ninguna línea de detalle", vacios.sum(), "Solo se cuenta")

    tablas["pedidos"], tablas["detalle_pedido"] = pedidos, detalle


# ---------------------------------------------------------------
# Carga en la base de datos
# ---------------------------------------------------------------
def a_python(valor):
    """sqlite3 no entiende los tipos de numpy (int64...) ni NaN: se pasan a Python / None."""
    if pd.isna(valor):
        return None
    return valor.item() if hasattr(valor, "item") else valor


def cargar_bd(tablas: dict[str, pd.DataFrame]) -> None:
    """Crea la BD vacía y la llena fila a fila; si una fila incumple el esquema, para y lo dice."""
    crear_bd()
    conexion = sqlite3.connect(RUTA_BD)
    try:
        # Las claves foráneas se activan por conexión: hay que hacerlo en cada una
        conexion.execute("PRAGMA foreign_keys = ON")
        for tabla in ORDEN_CARGA:
            df = tablas[tabla]
            columnas = ", ".join(df.columns)
            huecos = ", ".join("?" for _ in df.columns)
            sql = f"INSERT INTO {tabla} ({columnas}) VALUES ({huecos})"
            for numero, fila in enumerate(df.itertuples(index=False), start=1):
                try:
                    conexion.execute(sql, [a_python(v) for v in fila])
                except sqlite3.Error as error:
                    conexion.rollback()  # no se guarda nada a medias
                    print(f"\nERROR al cargar la tabla '{tabla}' (fila {numero} de los datos limpios):")
                    print(f"  Fila: {dict(zip(df.columns, fila))}")
                    print(f"  Motivo: {error}")
                    sys.exit(1)
        conexion.commit()
    finally:
        conexion.close()


# ---------------------------------------------------------------
# Informe
# ---------------------------------------------------------------
def escribir_informe(antes: dict, despues: dict, informe: list, outliers: list) -> str:
    lineas = ["# Informe de calidad de datos", "",
              "Generado por `src/limpieza.py` a partir de los CSV de `data/raw/`.", "",
              "## Filas por tabla", "",
              "| Tabla | Antes | Después | Eliminadas |", "|---|---:|---:|---:|"]
    for tabla in ORDEN_CARGA:
        lineas.append(f"| {tabla} | {antes[tabla]} | {despues[tabla]} | {antes[tabla] - despues[tabla]} |")

    lineas += ["", "## Problemas encontrados", "",
               "| Tabla | Problema | Casos | Qué se hizo |", "|---|---|---:|---|"]
    for p in informe:
        if p["casos"] > 0:
            lineas.append(f"| {p['tabla']} | {p['problema']} | {p['casos']} | {p['accion']} |")

    revisados_sin_casos = [p for p in informe if p["casos"] == 0]
    lineas += ["", "Comprobaciones sin ningún caso: "
               + "; ".join(f"{p['tabla']}: {p['problema']}" for p in revisados_sin_casos) + "."]

    lineas += ["", "## Outliers (método IQR, solo informativo)", "",
               "No se elimina ninguno: son pedidos válidos y los necesita Isolation Forest en la S8.", "",
               "| Variable | Outliers |", "|---|---:|"]
    for o in outliers:
        lineas.append(f"| {o['variable']} | {o['outliers']} |")

    texto = "\n".join(lineas) + "\n"
    RUTA_INFORME.write_text(texto, encoding="utf-8")
    return texto


# ---------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------
def main() -> None:
    tablas = leer_csvs()
    antes = {nombre: len(df) for nombre, df in tablas.items()}
    informe = []

    # Las tablas maestras primero; pedidos antes que clientes porque la limpieza
    # de clientes usa los pedidos para recalcular fechas de alta
    for tabla, clave in [("categorias", "id_categoria"), ("proveedores", "id_proveedor"),
                         ("productos", "id_producto"), ("campanas", "id_campana")]:
        tablas[tabla] = limpiar_tabla_maestra(tablas[tabla], tabla, clave, informe)
    tablas["pedidos"] = limpiar_pedidos(tablas["pedidos"], informe)
    tablas["clientes"] = limpiar_clientes(tablas["clientes"], tablas["pedidos"], informe)
    tablas["detalle_pedido"] = limpiar_detalle(tablas["detalle_pedido"], informe)
    eliminar_huerfanos(tablas, informe)
    outliers = contar_outliers(tablas["detalle_pedido"], tablas["productos"])

    cargar_bd(tablas)
    despues = {nombre: len(df) for nombre, df in tablas.items()}
    print()
    print(escribir_informe(antes, despues, informe, outliers))
    print(f"Informe guardado en: {RUTA_INFORME}")


if __name__ == "__main__":
    main()
