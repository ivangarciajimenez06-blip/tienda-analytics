"""S7 + S9 · Ficha de cliente: segmento, probabilidad de volver, acción e historial de pedidos."""
import altair as alt
import streamlit as st

import utilidades as u

u.preparar_pagina("Ficha de cliente", "👤")

st.title("👤 Ficha de cliente")

clientes = u.clientes()
pedidos = u.pedidos()
rec = u.cargar_modelo("recompra_knn")

# Cliente inicial: el recuperable que más ha gastado (el primero de la lista de la campaña)
recuperables = clientes[clientes["accion"] == u.RECUPERABLE].sort_values("monetario", ascending=False)
ids = clientes.index.tolist()
id_cliente = st.selectbox(
    "Elige un cliente", ids, index=ids.index(recuperables.index[0]),
    format_func=lambda i: f"Cliente {i} · {clientes.at[i, 'ciudad']} · {clientes.at[i, 'nombre_segmento']}",
    help="Puedes escribir el número para buscarlo. Al abrir la página se muestra el cliente recuperable "
         "con más gasto, el primero de la campaña de retención.",
)
cliente = clientes.loc[id_cliente]
sus_pedidos = pedidos[pedidos["id_cliente"] == id_cliente].sort_values("fecha_pedido")
sospechosos = sus_pedidos[sus_pedidos["marcado"]]

# --- Aviso destacado: pedidos sospechosos (S8) -------------------------------------------------
for _, pedido in sospechosos.iterrows():
    texto = (f"**🚩 Este cliente tiene un pedido sospechoso.** El pedido **{pedido['id_pedido']}** del "
             f"{u.fecha(pedido['fecha_pedido'])}, de **{u.euros(pedido['importe_total'])}**, es el nº "
             f"**{pedido['ranking']}** del ranking de pedidos sospechosos. Motivo: {pedido['motivo']}.")
    if pedido["estado"] == "completado" and cliente["monetario"] > 0:
        resto = cliente["monetario"] - pedido["importe_total"]
        texto += (f"\n\nEse pedido es el **{u.porcentaje(pedido['importe_total'] / cliente['monetario'])} de su "
                  f"gasto total**: sin él, habría gastado {u.euros(resto)}. Conviene revisarlo antes de "
                  "tomar decisiones con este cliente (por ejemplo, incluirlo en una campaña).")
    st.error(texto)

# --- Sin compras completadas ----------------------------------------------------------------------
if cliente["nombre_segmento"] == u.SIN_COMPRAS:
    st.info("Este cliente no tiene ningún pedido completado (o no ha comprado, o sus pedidos se "
            "cancelaron o devolvieron). Sin compras no se le puede asignar un segmento ni calcular "
            "su probabilidad de volver.")
else:
    # --- Resumen: segmento, probabilidad y acción ----------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Segmento", cliente["nombre_segmento"], help="Tipo de cliente según cuándo compró por última vez, "
                "cuántas veces y cuánto ha gastado (K-Means sobre las variables RFM).")
    col2.metric(f"Probabilidad de volver en {rec['horizonte_dias']} días", u.porcentaje(cliente["prob_volver"]),
                help=f"Por debajo del {u.porcentaje(rec['umbral'], 0)} se considera que el cliente está en "
                     "riesgo de no volver.")
    col3.metric("Acción", cliente["accion"])

    explicacion = {
        u.RECUPERABLE: f"Está en riesgo de no volver, pero compró hace menos de {u.RECENCIA_PERDIDO} días: "
                       "**debería recibir la campaña de retención**.",
        u.PERDIDO: f"Está en riesgo y lleva {u.RECENCIA_PERDIDO} días o más sin comprar: probablemente ya "
                   "no volverá y una campaña tiene pocas opciones de recuperarlo.",
        u.NO_EN_RIESGO: "Lo más probable es que vuelva a comprar pronto: no hace falta hacer nada.",
    }
    st.markdown(explicacion[cliente["accion"]])

    # --- Variables RFM --------------------------------------------------------------------------
    st.subheader("Su forma de comprar")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Días sin comprar", u.numero(cliente["recencia_dias"]), help="Recencia (R): días "
              "desde su último pedido completado hasta el día siguiente al último pedido de la tienda.")
    c2.metric("Pedidos completados", u.numero(cliente["frecuencia"]), help="Frecuencia (F).")
    c3.metric("Gasto total", u.euros(cliente["monetario"]), help="Valor monetario (M): suma de sus pedidos "
              "completados.")
    c4.metric("Gasto por pedido", u.euros(cliente["ticket_medio"]))
    c5.metric("Cliente desde", u.fecha(cliente["fecha_alta"]),
              help=f"{u.numero(cliente['pedidos_por_mes'], 2)} pedidos al mes desde que se dio de alta.")

# --- Historial de pedidos -------------------------------------------------------------------------
st.subheader(f"Historial de pedidos ({len(sus_pedidos)})")
if sus_pedidos.empty:
    st.write("No tiene ningún pedido.")
else:
    historial = sus_pedidos.assign(
        tipo=sus_pedidos["marcado"].map({True: "Sospechoso", False: "Normal"}),
        texto_importe=sus_pedidos["importe_total"].map(u.euros),
        texto_fecha=sus_pedidos["fecha_pedido"].map(u.fecha),
    )
    grafico = alt.Chart(historial).mark_bar(size=6).encode(
        x=alt.X("fecha_pedido:T", title="Fecha del pedido",
              axis=alt.Axis(format="%m/%Y", tickCount={"interval": "month", "step": 1})),
        y=alt.Y("importe_total:Q", title="Importe del pedido", axis=alt.Axis(labelExpr=u.EJE_EUROS)),
        color=alt.Color("tipo:N", title="Pedido", scale=alt.Scale(domain=["Normal", "Sospechoso"],
                                                                   range=["#2a78d6", "#d03b3b"])),
        opacity=alt.condition(alt.datum.estado == "completado", alt.value(1.0), alt.value(0.35)),
        tooltip=[alt.Tooltip("id_pedido:N", title="Pedido"), alt.Tooltip("texto_fecha:N", title="Fecha"),
                 alt.Tooltip("texto_importe:N", title="Importe"), alt.Tooltip("estado:N", title="Estado")],
    ).properties(height=300)
    st.altair_chart(grafico, width="stretch")
    st.caption("Cada barra es un pedido. Los cancelados y devueltos salen más claros.")

    # Las columnas siguen siendo números y fechas (así se ordenan bien al pulsar la cabecera);
    # el Styler solo cambia cómo se muestran
    tabla = historial.sort_values("fecha_pedido", ascending=False)[
        ["id_pedido", "fecha_pedido", "estado", "n_lineas", "unidades_totales", "importe_total", "tipo"]]
    tabla.columns = ["Pedido", "Fecha", "Estado", "Productos distintos", "Unidades", "Importe", "¿Sospechoso?"]
    st.dataframe(tabla.style.format({"Fecha": u.fecha, "Importe": u.euros}),
                 hide_index=True, width="stretch")
