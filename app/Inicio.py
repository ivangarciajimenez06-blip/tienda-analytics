"""Página de inicio: qué es el proyecto, indicadores principales y las 4 preguntas de negocio.

Arrancar la app desde la raíz del proyecto:
    streamlit run app/Inicio.py
"""
import streamlit as st

import utilidades as u

u.preparar_pagina("Inicio", "🛒")

st.title("🛒 Tienda Analytics")
st.markdown(
    "Analítica completa de una tienda online: una base de datos con dos años de pedidos, "
    "limpieza de los datos y cuatro modelos de *machine learning* que responden a preguntas de "
    "negocio. Esta app permite usar esos modelos sin escribir código: simular la inversión en "
    "publicidad, consultar la ficha de un cliente y revisar los pedidos sospechosos."
)
st.warning("**Datos simulados.** La tienda, los clientes y los pedidos se han generado con un "
           "programa (con Faker y una semilla fija). No corresponden a ninguna empresa ni persona real.",
           icon="⚠️")

# --- Indicadores principales -------------------------------------------------------------
kpis = u.kpis_ventas()
desde, hasta = u.meses()["mes"].iloc[[0, -1]]
st.subheader(f"La tienda en cifras ({desde} a {hasta})")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ingresos", u.euros(kpis["ingresos"]), help="Suma de los pedidos completados "
            "(sin cancelados ni devueltos).")
col2.metric("Pedidos", u.numero(kpis["pedidos"]), help="Pedidos completados.")
col3.metric("Clientes", u.numero(kpis["clientes"]), help="Clientes con al menos un pedido completado.")
col4.metric("Ticket medio", u.euros(kpis["ticket_medio"]), help="Ingresos ÷ pedidos.")

# --- Las 4 preguntas de negocio ------------------------------------------------------------
# Todas las cifras se calculan con los datos y los modelos (no están escritas a mano).
efecto = u.efecto_100_euros()
segmentos = u.resumen_segmentos()
fieles = segmentos.loc["Fieles"]
pedidos = u.pedidos()
marcados = pedidos[pedidos["marcado"]]
n_meses = pedidos["mes"].nunique()
precision = u.precision_alertas()
clientes = u.clientes()
con_compras = clientes[clientes["nombre_segmento"] != u.SIN_COMPRAS]
en_riesgo = con_compras["en_riesgo"].astype(bool)
recuperables = (con_compras["accion"] == u.RECUPERABLE).sum()

st.subheader("Las 4 preguntas de negocio")
texto_precision = (f" Comprobado con las anomalías plantadas en los datos: el {u.porcentaje(precision)} "
                   "de las alertas son reales." if precision is not None else "")
preguntas = [
    ("📈", "¿Cuánto se vende por cada euro de publicidad?",
     f"Cada 100 € más al mes traen unos **{u.numero(efecto['pedidos'], 1)} pedidos** completados y "
     f"**{u.euros(efecto['ingresos'], 1)}** más de ingresos, descontando el efecto de la Navidad.",
     "pages/1_Simulador_publicidad.py", "Probar el simulador"),
    ("👥", "¿Qué tipos de clientes hay?",
     f"{len(segmentos)} segmentos: {', '.join(segmentos.index[:-1])} y {segmentos.index[-1]}. Los Fieles son el "
     f"**{u.porcentaje(fieles['pct_clientes'])} de los clientes** y generan el "
     f"**{u.porcentaje(fieles['pct_ingresos'])} de los ingresos**.",
     "pages/2_Ficha_de_cliente.py", "Ver la ficha de un cliente"),
    ("🚩", "¿Qué pedidos son sospechosos?",
     f"**{u.numero(len(marcados))} pedidos** de {u.numero(len(pedidos))} (unos "
     f"{u.numero(len(marcados) / n_meses)} al mes), sobre todo por muchas unidades, muchas líneas o "
     f"importes fuera de lo normal.{texto_precision}",
     "pages/3_Pedidos_sospechosos.py", "Revisar los pedidos"),
    ("🔁", "¿Qué clientes volverán a comprar en los próximos 90 días?",
     f"**{u.numero(en_riesgo.sum())} de {u.numero(len(con_compras))} clientes** "
     f"({u.porcentaje(en_riesgo.mean())}) están en riesgo de no volver; **{u.numero(recuperables)} son "
     "recuperables** y son los que deberían recibir la campaña de retención.",
     "pages/2_Ficha_de_cliente.py", "Ver la ficha de un cliente"),
]
for icono, pregunta, respuesta, pagina, enlace in preguntas:
    with st.container(border=True):
        st.markdown(f"#### {icono} {pregunta}")
        st.markdown(respuesta)
        st.page_link(pagina, label=enlace, icon="➡️")

# --- Más información ------------------------------------------------------------------------
st.subheader("Más información")
st.markdown(
    f"- Código, notebooks y explicación de cada modelo: [repositorio en GitHub]({u.URL_REPOSITORIO}).\n"
    "- Hay también un **cuadro de mando de Power BI** (ventas, clientes y alertas de pedidos) en la "
    "carpeta `dashboard/` del repositorio (`dashboard/tienda.pbix`)."
)
