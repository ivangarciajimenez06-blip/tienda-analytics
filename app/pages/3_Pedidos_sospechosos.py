"""S8 · Pedidos sospechosos: lista de alertas de Isolation Forest con filtros y alertas por mes."""
import altair as alt
import pandas as pd
import streamlit as st

import utilidades as u

u.preparar_pagina("Pedidos sospechosos", "🚩")

st.title("🚩 Pedidos sospechosos")
st.markdown("Pedidos que un modelo de detección de anomalías (Isolation Forest) marca para que alguien "
            "los revise: no son necesariamente fraudes, sino pedidos muy distintos de lo habitual.")

paquete = u.cargar_modelo("anomalias_iforest")
pedidos = u.pedidos()
todos_marcados = pedidos[pedidos["marcado"]]
n_meses = pedidos["mes"].nunique()

with st.expander("¿Cómo se decide qué pedidos se marcan?", expanded=True):
    st.markdown(
        f"Cada pedido recibe una **puntuación entre 0 y 1**: cuanto más alta, más raro es. Se marcan los "
        f"que pasan de **{u.numero(paquete['umbral'], 3)}**, el punto a partir del cual una puntuación es "
        "atípica frente a las demás (la misma regla que marca los valores extremos en un diagrama de caja). "
        f"Así salen **{u.numero(len(todos_marcados))} pedidos, unos {u.numero(len(todos_marcados) / n_meses)} "
        f"al mes**. El equipo puede revisar {paquete['capacidad_mensual']} al mes, pero eso es un tope, no un "
        "objetivo: llenarlo significaría revisar sobre todo pedidos normales."
    )

# --- Filtros ----------------------------------------------------------------------------------------
anios = sorted(pedidos["fecha_pedido"].dt.year.unique())
segmentos = [s for s in u.ORDEN_SEGMENTOS if s in set(todos_marcados["nombre_segmento"])]
col1, col2 = st.columns(2)
anios_elegidos = col1.multiselect("Año", anios, default=anios)
segmentos_elegidos = col2.multiselect("Segmento del cliente", segmentos, default=segmentos)

filtro = (pedidos["fecha_pedido"].dt.year.isin(anios_elegidos)
          & pedidos["nombre_segmento"].isin(segmentos_elegidos))
en_periodo = pedidos[pedidos["fecha_pedido"].dt.year.isin(anios_elegidos)]
marcados = pedidos[filtro & pedidos["marcado"]].sort_values("ranking")

if marcados.empty:
    st.info("No hay pedidos marcados con estos filtros.")
    st.stop()

# --- Indicadores ----------------------------------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Pedidos marcados", u.numero(len(marcados)))
c2.metric("Importe de los pedidos marcados", u.euros(marcados["importe_total"].sum()))
c3.metric("% de los pedidos del periodo", u.porcentaje(len(marcados) / len(en_periodo), 2),
          help="Pedidos marcados (con los filtros) ÷ todos los pedidos de los años elegidos.")

# --- Alertas por mes ------------------------------------------------------------------------------
# Todos los meses de los años elegidos, también los que no tienen ninguna alerta (con 0)
meses = en_periodo["mes"].drop_duplicates().sort_values()
por_mes = (marcados.groupby("mes").size().reindex(meses, fill_value=0)
           .rename("alertas").rename_axis("mes").reset_index())
por_mes["fecha"] = por_mes["mes"].dt.to_timestamp()
grafico = alt.Chart(por_mes).mark_bar(color="#d03b3b").encode(
    # Ordinal (una categoría por mes) para que cada barra ocupe su hueco y no sea una línea fina
    x=alt.X("yearmonth(fecha):O", title=None, axis=alt.Axis(format="%m/%Y", labelAngle=-45)),
    y=alt.Y("alertas:Q", title="Pedidos marcados", axis=alt.Axis(tickMinStep=1)),
    tooltip=[alt.Tooltip("fecha:T", title="Mes", format="%m/%Y"), alt.Tooltip("alertas:Q", title="Pedidos marcados")],
).properties(height=280)
st.subheader("Alertas por mes")
st.altair_chart(grafico, width="stretch")

# --- Tabla de alertas ----------------------------------------------------------------------------
st.subheader("Pedidos marcados, del más sospechoso al menos")
tabla = pd.DataFrame({
    "Ranking": marcados["ranking"],
    "Pedido": marcados["id_pedido"],
    "Fecha": marcados["fecha_pedido"],
    "Cliente": marcados["id_cliente"],
    "Segmento": marcados["nombre_segmento"],
    "Motivo": marcados["motivo"],
    "Puntuación": marcados["puntuacion"],
    "Importe": marcados["importe_total"],
})
# El motivo es lo que más interesa leer y llega a ~130 caracteres. En st.dataframe (Streamlit 1.67)
# el texto de una celda no se parte en varias líneas: se corta o obliga a desplazar la tabla en
# horizontal. st.table es una tabla HTML normal, que sí parte el texto. Para que las 121 filas no
# alarguen la página, va dentro de un contenedor de altura fija con desplazamiento vertical.
with st.container(height=460):
    st.table(
        # Espacio de no separación antes del "€" para que el importe no se parta en dos líneas
        tabla.style.format({"Fecha": u.fecha, "Puntuación": lambda v: u.numero(v, 3),
                            "Importe": lambda v: u.euros(v).replace(" ", "\u00a0")}),
        hide_index=True,
    )
st.caption("El ranking ordena todos los pedidos de la tienda por su puntuación (1 = el más raro). "
           "El motivo indica las 2 o 3 características más alejadas de un pedido normal.")
