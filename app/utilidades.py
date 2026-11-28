"""Lógica compartida de la app: datos, modelos, cálculos y formato.

Las páginas solo dibujan; todo lo que se calcula está aquí para no repetir código.

Regla de la app: NO lee los CSV que generan los notebooks (segmentos_clientes.csv,
pedidos_sospechosos.csv, riesgo_recompra.csv). Calcula lo mismo con las funciones de
src/features.py y los modelos guardados en models/, igual que hacen los notebooks. Así la app
funciona con solo generar la base de datos, sin ejecutar ningún notebook.

Cachés de Streamlit (ver docs/explicacion_s11.md):
    st.cache_resource -> objetos que se comparten tal cual: la generación de datos y los modelos.
    st.cache_data     -> tablas (DataFrames): cada página recibe su propia copia.
"""
import contextlib
import io
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.linear_model import LinearRegression

# Rutas: la app está en app/, el código de análisis en src/
RAIZ = Path(__file__).resolve().parent.parent
CARPETA_SRC = RAIZ / "src"
CARPETA_MODELOS = RAIZ / "models"
if str(CARPETA_SRC) not in sys.path:
    sys.path.append(str(CARPETA_SRC))

from bd import RUTA_BD, leer_sql  # noqa: E402  (tiene que ir después de añadir src/ al path)
from features import (PERCENTIL_ESTRICTO, fecha_corte, tabla_mensual, tabla_pedidos,  # noqa: E402
                      tabla_recompra, tabla_rfm)

URL_REPOSITORIO = "https://github.com/ivangarciajimenez06-blip/tienda-analytics"

# Regla de negocio de la S9 (notebook 05, sección 9): un cliente en riesgo que lleva 365 días o más
# sin comprar (un año entero, Navidad incluida) se da por perdido. No está guardada en el .joblib
# porque no es parte del modelo, sino una decisión de negocio que se aplica después.
RECENCIA_PERDIDO = 365
RECUPERABLE, PERDIDO, NO_EN_RIESGO = "Recuperable", "Probablemente perdido", "No en riesgo"
SIN_COMPRAS = "Sin compras completadas"

# Orden de los segmentos para tablas y gráficos (del más valioso al menos)
ORDEN_SEGMENTOS = ["Fieles", "Habituales", "Compra única", "Perdidos", SIN_COMPRAS]


# ---------------------------------------------------------------------------------------
# Formato español de números
# ---------------------------------------------------------------------------------------

def numero(valor: float, decimales: int = 0) -> str:
    """1234567.891 -> '1.234.567,89' (punto para los miles y coma para los decimales).

    Python escribe '1,234,567.89'; se intercambian la coma y el punto pasando por una X
    para no pisar uno con otro.
    """
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def euros(valor: float, decimales: int = 2) -> str:
    """883360.54 -> '883.360,54 €'."""
    return f"{numero(valor, decimales)} €"


def porcentaje(fraccion: float, decimales: int = 1) -> str:
    """0.395 -> '39,5 %' (recibe una fracción entre 0 y 1)."""
    return f"{numero(100 * fraccion, decimales)} %"


def fecha(valor) -> str:
    """Timestamp -> '07/06/2026'."""
    return pd.Timestamp(valor).strftime("%d/%m/%Y")


# Expresiones de Vega (el motor de Altair) para que los ejes de los gráficos usen el formato español
EJE_EUROS = "replace(format(datum.value, ',.0f'), regexp(',', 'g'), '.') + ' €'"
EJE_NUMERO = "replace(format(datum.value, ',.0f'), regexp(',', 'g'), '.')"


# ---------------------------------------------------------------------------------------
# Datos: se generan solos la primera vez
# ---------------------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def asegurar_datos() -> bool:
    """Si no existe la base de datos, la genera con los scripts de src/. Devuelve True si la generó.

    Se importan y llaman las funciones main() de los scripts (no se lanza otro proceso con
    subprocess): es el mismo código que `python src/generar_datos.py` y `python src/limpieza.py`.
    Gracias a st.cache_resource solo se ejecuta una vez mientras la app esté en marcha, aunque la
    llamen todas las páginas en cada interacción.
    """
    if RUTA_BD.exists():
        return False
    import generar_datos  # se importan aquí: solo hacen falta si no hay datos
    import limpieza

    with st.spinner("Generando los datos simulados de la tienda por primera vez. "
                    "Tarda menos de un minuto y solo ocurre una vez…"):
        # Los scripts imprimen su progreso; se recoge en un texto para que no salga por la consola
        # (en Windows, algunos caracteres como "€" pueden dar error al imprimirse)
        salida = io.StringIO()
        try:
            with contextlib.redirect_stdout(salida):
                generar_datos.main()
                limpieza.main()
        except (Exception, SystemExit):
            # Si algo falla a medias, se borra la BD incompleta para que el siguiente intento empiece de cero
            RUTA_BD.unlink(missing_ok=True)
            raise RuntimeError("No se pudieron generar los datos:\n" + salida.getvalue()[-2000:])
    return True


# Los únicos modelos que la app puede cargar. Cargar un .joblib ejecuta código (ver la sección
# "Seguridad" de docs/explicacion_s11.md), así que solo se aceptan estos nombres fijos: nunca una
# ruta que venga del usuario, de la URL o de un archivo subido.
MODELOS_PERMITIDOS = ("regresion_pedidos", "segmentacion_kmeans", "anomalias_iforest", "recompra_knn")


@st.cache_resource
def cargar_modelo(nombre: str) -> dict:
    """Carga models/<nombre>.joblib (un diccionario con el modelo y sus datos) una sola vez."""
    if nombre not in MODELOS_PERMITIDOS:
        raise ValueError(f"Modelo no permitido: {nombre!r}. Solo se cargan {MODELOS_PERMITIDOS}.")
    return joblib.load(CARPETA_MODELOS / f"{nombre}.joblib")


def preparar_pagina(titulo: str, icono: str) -> None:
    """Lo que hace cada página al empezar: configuración, datos y aviso de datos simulados."""
    st.set_page_config(page_title=f"{titulo} · Tienda Analytics", page_icon=icono, layout="wide")
    asegurar_datos()
    st.sidebar.caption("⚠️ Todos los datos son **simulados**: no corresponden a ninguna tienda ni "
                       "persona real.")


# ---------------------------------------------------------------------------------------
# Inicio: indicadores de ventas
# ---------------------------------------------------------------------------------------

CONSULTA_KPIS = """
SELECT
    SUM(d.cantidad * d.precio_unitario)  AS ingresos,
    COUNT(DISTINCT p.id_pedido)          AS pedidos,
    COUNT(DISTINCT p.id_cliente)         AS clientes
FROM pedidos AS p
    JOIN detalle_pedido AS d ON d.id_pedido = p.id_pedido
WHERE p.estado = 'completado'
"""


@st.cache_data
def kpis_ventas() -> dict:
    """Ingresos, pedidos, clientes con compras y ticket medio. Solo pedidos completados."""
    fila = leer_sql(CONSULTA_KPIS).iloc[0]
    return {"ingresos": float(fila["ingresos"]), "pedidos": int(fila["pedidos"]),
            "clientes": int(fila["clientes"]), "ticket_medio": float(fila["ingresos"] / fila["pedidos"])}


# ---------------------------------------------------------------------------------------
# S6 · Simulador de publicidad
# ---------------------------------------------------------------------------------------

@st.cache_data
def meses() -> pd.DataFrame:
    """Una fila por mes con inversión, pedidos completados e ingresos sin pedidos excepcionales.

    ingresos_sin_extremos usa el criterio elegido en la S6: sin los pedidos por encima del
    percentil 99,5 del importe (los pedidos enormes no dependen de la publicidad).
    """
    mensual = tabla_mensual(criterio="p995")
    mensual["temporada"] = np.where(mensual["temporada_alta"] == 1, "Noviembre y diciembre", "Resto del año")
    return mensual


@st.cache_resource
def modelo_ingresos() -> LinearRegression:
    """Modelo M2 de ingresos de la S6 (notebook 02, sección 6.1), la "cifra elegida".

    No está guardado en un .joblib (el modelo guardado predice pedidos), así que se vuelve a
    ajustar igual que en el notebook: regresión lineal de los ingresos sin pedidos por encima del
    percentil 99,5 frente a inversión y temporada, con los 24 meses. Mismos datos y mismo método
    dan exactamente los mismos coeficientes (cada 100 € -> 566,5 €).
    """
    variables = cargar_modelo("regresion_pedidos")["variables"]
    mensual = meses()
    return LinearRegression().fit(mensual[variables], mensual["ingresos_sin_extremos"])


def simular(inversion: float, temporada_alta: bool) -> dict:
    """Pedidos completados esperados e ingresos estimados de un mes con esa inversión."""
    paquete = cargar_modelo("regresion_pedidos")
    X = pd.DataFrame({"inversion_total": [inversion], "temporada_alta": [int(temporada_alta)]})[paquete["variables"]]
    return {"pedidos": float(paquete["modelo"].predict(X)[0]),
            "ingresos": float(modelo_ingresos().predict(X)[0])}


def efecto_100_euros() -> dict:
    """Cuánto más se vende al mes por cada 100 € más de publicidad (pendiente de cada modelo)."""
    paquete = cargar_modelo("regresion_pedidos")
    posicion = paquete["variables"].index("inversion_total")
    return {"pedidos": 100 * float(paquete["modelo"].coef_[posicion]),
            "ingresos": 100 * float(modelo_ingresos().coef_[posicion])}


# ---------------------------------------------------------------------------------------
# S7 + S9 · Clientes: segmento, probabilidad de volver y acción
# ---------------------------------------------------------------------------------------

def _accion(en_riesgo: bool, recencia_dias: float) -> str:
    """Regla de negocio de la S9: qué hacer con cada cliente."""
    if not en_riesgo:
        return NO_EN_RIESGO
    return RECUPERABLE if recencia_dias < RECENCIA_PERDIDO else PERDIDO


@st.cache_data
def clientes() -> pd.DataFrame:
    """Una fila por cliente (los 493) con RFM, segmento, probabilidad de volver y acción.

    Segmento (S7): el pipeline de K-Means guardado asigna un segmento a cada cliente con compras.
    Recompra (S9): con la fecha de corte de hoy (el día siguiente al último pedido), el KNN
    guardado da la probabilidad de volver en los próximos 90 días; por debajo del umbral, el
    cliente está en riesgo, y la regla de los 365 días decide si es recuperable.
    Los clientes sin ningún pedido completado no tienen segmento ni probabilidad.
    """
    # Datos básicos de todos los clientes (sin nombre ni email: no hacen falta)
    base = leer_sql("SELECT id_cliente, ciudad, fecha_alta FROM clientes ORDER BY id_cliente")
    base["fecha_alta"] = pd.to_datetime(base["fecha_alta"])

    # S7 · Segmento
    seg = cargar_modelo("segmentacion_kmeans")
    rfm = tabla_rfm()
    rfm["segmento"] = seg["pipeline"].predict(rfm[seg["variables"]])
    rfm["nombre_segmento"] = rfm["segmento"].map(seg["nombres_segmentos"])

    # S9 · Probabilidad de volver y acción
    rec = cargar_modelo("recompra_knn")
    actual = tabla_recompra(fecha_corte(), rec["horizonte_dias"])
    actual["prob_volver"] = rec["pipeline"].predict_proba(actual[rec["variables"]])[:, 1]
    actual["en_riesgo"] = actual["prob_volver"] < rec["umbral"]
    actual["accion"] = [_accion(r, d) for r, d in zip(actual["en_riesgo"], actual["recencia_dias"])]

    tabla = (base
             .merge(rfm[["id_cliente", "recencia_dias", "frecuencia", "monetario", "antiguedad_dias",
                         "ticket_medio", "segmento", "nombre_segmento"]], on="id_cliente", how="left")
             .merge(actual[["id_cliente", "pedidos_por_mes", "prob_volver", "en_riesgo", "accion"]],
                    on="id_cliente", how="left"))
    tabla["nombre_segmento"] = tabla["nombre_segmento"].fillna(SIN_COMPRAS)
    tabla["accion"] = tabla["accion"].fillna(SIN_COMPRAS)
    return tabla.set_index("id_cliente")


def resumen_segmentos() -> pd.DataFrame:
    """% de clientes y % de ingresos de cada segmento (solo clientes con compras)."""
    con_compras = clientes().query("nombre_segmento != @SIN_COMPRAS")
    resumen = con_compras.groupby("nombre_segmento").agg(clientes=("monetario", "size"),
                                                        ingresos=("monetario", "sum"))
    resumen["pct_clientes"] = resumen["clientes"] / resumen["clientes"].sum()
    resumen["pct_ingresos"] = resumen["ingresos"] / resumen["ingresos"].sum()
    return resumen.reindex([s for s in ORDEN_SEGMENTOS if s in resumen.index])


# ---------------------------------------------------------------------------------------
# S8 · Pedidos sospechosos
# ---------------------------------------------------------------------------------------

def _aplicar_umbral(pedidos: pd.DataFrame, umbral: float, capacidad: int) -> np.ndarray:
    """Marca los pedidos con puntuación ≥ umbral, pero como mucho `capacidad` por mes.

    Copia de aplicar_umbral() del notebook 04: dentro de cada mes se ordenan por puntuación (con
    empates, el id_pedido más bajo) y solo se marcan los `capacidad` primeros.
    """
    tabla = pedidos[["puntuacion", "mes", "id_pedido"]].sort_values(
        ["puntuacion", "id_pedido"], ascending=[False, True], kind="stable")
    tabla["puesto_en_el_mes"] = tabla.groupby("mes").cumcount() + 1
    tabla = tabla.sort_index()
    return ((tabla["puntuacion"] >= umbral) & (tabla["puesto_en_el_mes"] <= capacidad)).to_numpy()


def _describir_variable(variable: str, valor: float, sentido: float, medianas: pd.Series) -> str:
    """Texto para negocio de una variable rara (copia de describir_variable() del notebook 04)."""
    if variable.startswith("ratio"):
        lado = "por encima" if valor > 1 else "por debajo"
        return f"Precio {lado} del catálogo (×{numero(valor, 2)})"
    alto_bajo = "alto" if sentido > 0 else "bajo"
    muchas = "Muchas" if sentido > 0 else "Pocas"
    textos = {
        "importe_total": f"Importe {alto_bajo}: {euros(valor, 0)} (mediana {euros(medianas[variable], 0)})",
        "n_lineas": f"{muchas} líneas: {valor:.0f} (mediana {medianas[variable]:.0f})",
        "unidades_totales": f"{muchas} unidades: {valor:.0f} (mediana {medianas[variable]:.0f})",
        "max_cantidad_linea": f"{valor:.0f} unidades en una línea (mediana {medianas[variable]:.0f})",
        "importe_por_unidad": f"Importe por unidad {alto_bajo}: {euros(valor, 0)} (mediana {euros(medianas[variable], 0)})",
    }
    return textos[variable]


def _motivo(desviacion: pd.Series, pedido: pd.Series, medianas: pd.Series, extrema: float) -> str:
    """Las 2-3 variables más extremas del pedido, de más a menos (copia de variables_motivo())."""
    unidades = {"unidades_totales", "max_cantidad_linea"}
    orden = desviacion.abs().sort_values(ascending=False, kind="stable").index
    elegidas = []
    for v in orden:
        # Unidades totales y unidades en una línea con el mismo valor: solo se muestra una
        if v in unidades and any(e in unidades for e in elegidas) \
                and pedido["unidades_totales"] == pedido["max_cantidad_linea"]:
            continue
        if len(elegidas) >= 2 and abs(desviacion[v]) < extrema:
            break
        elegidas.append(v)
        if len(elegidas) == 3:
            break
    return " · ".join(_describir_variable(v, pedido[v], desviacion[v], medianas) for v in elegidas)


@st.cache_data
def pedidos() -> pd.DataFrame:
    """Una fila por pedido (todos los estados) con puntuación, ranking, marca y motivo (S8).

    puntuacion: entre 0 y 1, más alta = más raro (-score_samples de Isolation Forest).
    marcado:    puntuación ≥ umbral guardado, con el tope de revisiones al mes.
    ranking:    1 = el más sospechoso de todos.
    motivo:     solo en los marcados; las 2-3 variables más alejadas de lo normal.
    """
    paquete = cargar_modelo("anomalias_iforest")
    variables = paquete["variables"]
    tabla = tabla_pedidos()
    tabla["mes"] = tabla["fecha_pedido"].dt.to_period("M")
    tabla["puntuacion"] = -paquete["pipeline"].score_samples(tabla[variables])
    tabla["marcado"] = _aplicar_umbral(tabla, paquete["umbral"], paquete["capacidad_mensual"])

    # Ranking: 1 = más sospechoso; con empates, el id_pedido más bajo
    orden = tabla.sort_values(["puntuacion", "id_pedido"], ascending=[False, True], kind="stable").index
    tabla.loc[orden, "ranking"] = np.arange(1, len(tabla) + 1)
    tabla["ranking"] = tabla["ranking"].astype(int)

    # Motivo: desviación robusta de cada variable (en la escala transformada del modelo) frente a la
    # mediana guardada en el .joblib; se describe con las medianas en unidades originales
    transformador = paquete["pipeline"].named_steps["log"]
    transformado = pd.DataFrame(transformador.transform(tabla[variables]), index=tabla.index,
                                columns=[c.split("__")[1] for c in transformador.get_feature_names_out()])[variables]
    ref = paquete["referencia_motivo"]
    desviacion = (transformado - pd.Series(ref["mediana"])) / pd.Series(ref["escala"])
    medianas = tabla[variables].median()
    tabla["motivo"] = ""
    for i in tabla.index[tabla["marcado"]]:
        tabla.at[i, "motivo"] = _motivo(desviacion.loc[i], tabla.loc[i], medianas, ref["desviacion_extrema"])

    # Segmento del cliente, para filtrar
    tabla["nombre_segmento"] = tabla["id_cliente"].map(clientes()["nombre_segmento"])
    return tabla


def precision_alertas() -> float | None:
    """% de alertas que son anomalías reales, con las anomalías plantadas por el generador.

    Solo se puede calcular porque los datos son simulados (data/raw/_verdad_anomalias.csv).
    Si ese archivo no existe, devuelve None.
    """
    ruta = RAIZ / "data" / "raw" / "_verdad_anomalias.csv"
    if not ruta.exists():
        return None
    reales = set(pd.read_csv(ruta)["id_pedido"])
    marcados = pedidos().query("marcado")
    return float(marcados["id_pedido"].isin(reales).mean())
