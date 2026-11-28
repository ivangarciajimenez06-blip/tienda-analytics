"""S6 · Simulador de publicidad: pedidos e ingresos esperados según la inversión mensual."""
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import utilidades as u

u.preparar_pagina("Simulador de publicidad", "📈")

st.title("📈 Simulador de publicidad")
st.markdown("¿Cuántos pedidos e ingresos se pueden esperar en un mes según lo que se invierta en "
            "publicidad? Mueve el control y marca si es temporada alta.")

paquete = u.cargar_modelo("regresion_pedidos")
minimo, maximo = paquete["rango_inversion"]   # inversión mensual más baja y más alta de los datos
mensual = u.meses()
efecto = u.efecto_100_euros()

st.warning(
    f"**Es una estimación, no una garantía.** El modelo aprendió de {len(mensual)} meses en los que se "
    f"invirtió entre {u.euros(minimo, 0)} y {u.euros(maximo, 0)} al mes, así que **solo vale dentro de "
    "ese rango**: fuera de él no sabemos si la relación se mantiene. Por eso el control no deja salir "
    "de esos límites. Además, es una relación observada en los datos, no un experimento.",
    icon="⚠️",
)

# --- Controles ------------------------------------------------------------------------------
col_controles, col_resultado = st.columns([1, 2])
with col_controles:
    # Opciones de 10 en 10 € dentro del rango observado. Se usa select_slider (y no slider) porque
    # permite mostrar cada valor con formato español ("3.230 €"); slider solo admite "3230 €".
    PASO = 10
    opciones = list(range(int(np.ceil(minimo / PASO)) * PASO, int(maximo) + 1, PASO))
    mediana = mensual["inversion_total"].median()   # valor inicial: la inversión de un mes típico
    inversion = st.select_slider("Inversión mensual en publicidad", options=opciones,
                                 value=min(opciones, key=lambda v: abs(v - mediana)),
                                 format_func=lambda v: u.euros(v, 0))
    temporada_alta = st.checkbox("Temporada alta (noviembre o diciembre)",
                                 help="En Navidad se vende más aunque no se invierta más: el modelo lo descuenta.")

resultado = u.simular(inversion, temporada_alta)
with col_resultado:
    c1, c2 = st.columns(2)
    c1.metric("Pedidos completados esperados", u.numero(resultado["pedidos"]))
    c2.metric("Ingresos estimados del mes", u.euros(resultado["ingresos"], 0),
              help=f"Sin contar los pedidos excepcionalmente grandes (el {u.porcentaje(1 - u.PERCENTIL_ESTRICTO)} "
                   "más caro), que no dependen de la publicidad.")
    st.markdown(f"Cada **100 € más** de publicidad al mes traen unos **{u.numero(efecto['pedidos'], 1)} pedidos** "
                f"y **{u.euros(efecto['ingresos'], 1)}** más de ingresos (la cifra elegida en el análisis).")

# --- Gráfico: meses reales y punto simulado ---------------------------------------------------
# Rectas del modelo para cada temporada, dentro del rango observado
rejilla = np.linspace(minimo, maximo, 50)
rectas = pd.concat([
    pd.DataFrame({"inversion_total": rejilla, "temporada_alta": alta,
                  "temporada": "Noviembre y diciembre" if alta else "Resto del año"})
    for alta in (0, 1)
])
rectas["n_pedidos"] = paquete["modelo"].predict(rectas[paquete["variables"]])

simulado = pd.DataFrame({"inversion_total": [inversion], "n_pedidos": [resultado["pedidos"]],
                         "texto_inversion": [u.euros(inversion, 0)], "texto_pedidos": [u.numero(resultado["pedidos"])]})
reales = mensual.assign(texto_inversion=mensual["inversion_total"].map(lambda v: u.euros(v, 0)),
                        texto_ingresos=mensual["ingresos_sin_extremos"].map(lambda v: u.euros(v, 0)))

colores = alt.Scale(domain=["Resto del año", "Noviembre y diciembre"], range=["#2a78d6", "#eb6834"])
eje_x = alt.X("inversion_total:Q", title="Inversión en publicidad del mes",
              scale=alt.Scale(zero=False), axis=alt.Axis(labelExpr=u.EJE_EUROS))
eje_y = alt.Y("n_pedidos:Q", title="Pedidos completados del mes", scale=alt.Scale(zero=False))

puntos = alt.Chart(reales).mark_circle(size=90, opacity=0.8).encode(
    x=eje_x, y=eje_y, color=alt.Color("temporada:N", scale=colores, title="Meses reales"),
    tooltip=[alt.Tooltip("mes:N", title="Mes"), alt.Tooltip("texto_inversion:N", title="Inversión"),
             alt.Tooltip("n_pedidos:Q", title="Pedidos"), alt.Tooltip("texto_ingresos:N", title="Ingresos")],
)
lineas = alt.Chart(rectas).mark_line(strokeDash=[6, 4]).encode(
    x=eje_x, y=eje_y, color=alt.Color("temporada:N", scale=colores, legend=None))
punto_simulado = alt.Chart(simulado).mark_point(shape="diamond", size=400, filled=True,
                                                color="black", stroke="white", strokeWidth=2).encode(
    x=eje_x, y=eje_y,
    tooltip=[alt.Tooltip("texto_inversion:N", title="Inversión simulada"),
             alt.Tooltip("texto_pedidos:N", title="Pedidos esperados")])

st.subheader("Meses reales y tu simulación")
st.altair_chart((puntos + lineas + punto_simulado).properties(height=420), width="stretch")
st.caption("Cada punto es un mes real. Las líneas discontinuas son lo que predice el modelo para cada "
           "temporada; el rombo negro es tu simulación.")

with st.expander("¿Cómo funciona?"):
    st.markdown(
        f"Es una **regresión lineal** entrenada con los meses de {paquete['meses_entrenamiento']}: "
        "explica los pedidos completados de cada mes con la inversión en publicidad y con si es "
        "temporada alta. Tener en cuenta la temporada es importante: en Navidad se invierte más **y** "
        "se vende más, y sin separarla el modelo atribuiría a la publicidad ventas que se deben a la "
        "Navidad.\n\n"
        "Los ingresos se estiman igual, pero sin los pedidos excepcionalmente grandes (por encima del "
        f"percentil {u.numero(100 * u.PERCENTIL_ESTRICTO, 1)} del importe): unos pocos pedidos de miles de euros no dependen de la "
        "publicidad e inflarían la estimación."
    )
