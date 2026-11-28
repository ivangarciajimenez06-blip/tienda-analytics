"""Pruebas automáticas de la app de Streamlit con streamlit.testing.v1.AppTest.

AppTest ejecuta cada página como lo haría Streamlit, pero sin navegador: permite comprobar que
no hay excepciones, leer lo que muestra (métricas, avisos, tablas) y simular interacciones
(mover un control, elegir un cliente...).

Ejecutar desde la raíz del proyecto (no hace falta pytest):
    python tests/test_app.py
o, si pytest está instalado:
    python -m pytest tests/test_app.py

Las cifras esperadas son las documentadas en el README y en los CSV de los notebooks.
"""
import shutil
import sys
import time
import traceback
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_APP = RAIZ / "app"
sys.path.insert(0, str(CARPETA_APP))  # para que las páginas (en app/pages/) encuentren utilidades.py

import utilidades as u  # noqa: E402

TIEMPO_MAXIMO = 300  # segundos; la primera ejecución puede tener que generar los datos


def abrir(pagina: str) -> AppTest:
    """Ejecuta una página y comprueba que no lanza ninguna excepción."""
    app = AppTest.from_file(str(CARPETA_APP / pagina), default_timeout=TIEMPO_MAXIMO).run()
    assert not app.exception, f"{pagina} lanzó una excepción: {app.exception}"
    return app


def metricas(app: AppTest) -> dict:
    """{etiqueta: valor mostrado} de todas las métricas de la página."""
    return {m.label: m.value for m in app.metric}


def texto(app: AppTest) -> str:
    """Todo el texto en markdown de la página, junto."""
    return "\n".join(m.value for m in app.markdown)


# ---------------------------------------------------------------------------------------
# 1. Sin base de datos, la app genera los datos sola
# ---------------------------------------------------------------------------------------

def test_genera_los_datos_si_no_existen():
    copia = u.RUTA_BD.with_name("tienda_copia_test.db")
    if u.RUTA_BD.exists():
        shutil.move(u.RUTA_BD, copia)  # se aparta la BD (no se borra) por si algo falla
    try:
        st.cache_resource.clear()  # que asegurar_datos() no recuerde que ya había datos
        st.cache_data.clear()
        inicio = time.perf_counter()
        app = abrir("Inicio.py")
        assert u.RUTA_BD.exists(), "La app no ha creado data/processed/tienda.db"
        assert metricas(app)["Ingresos"] == "883.360,54 €"
        print(f"    datos generados por la app en {time.perf_counter() - inicio:.0f} s")
    finally:
        if copia.exists():
            if u.RUTA_BD.exists():
                copia.unlink()  # la nueva es equivalente (los datos son reproducibles)
            else:
                shutil.move(copia, u.RUTA_BD)


# ---------------------------------------------------------------------------------------
# 2. Cada página se ejecuta sin errores y muestra lo esperado
# ---------------------------------------------------------------------------------------

def test_inicio():
    app = abrir("Inicio.py")
    assert metricas(app) == {"Ingresos": "883.360,54 €", "Pedidos": "6.541",
                             "Clientes": "474", "Ticket medio": "135,05 €"}
    contenido = texto(app)
    for frase in ["4,2 pedidos", "566,5 €", "26,8 % de los clientes", "66,4 % de los ingresos",
                  "121 pedidos", "187 de 474 clientes", "95 son", "52,1 %"]:
        assert frase in contenido, f"Falta «{frase}» en la página de inicio"
    assert any("simulados" in w.value for w in app.warning), "Falta el aviso de datos simulados"


def test_simulador():
    app = abrir("pages/1_Simulador_publicidad.py")
    opciones = [int(o.replace(".", "").replace(" €", "")) for o in app.select_slider[0].options]
    minimo, maximo = u.cargar_modelo("regresion_pedidos")["rango_inversion"]
    assert minimo <= min(opciones) and max(opciones) <= maximo, "El control sale del rango observado"
    assert any("solo vale dentro de" in w.value for w in app.warning), "Falta el aviso del rango"

    # Con más inversión, más pedidos; con temporada alta, también más
    app.select_slider[0].set_value(2000).run()
    bajo = metricas(app)["Pedidos completados esperados"]
    app.select_slider[0].set_value(5000).run()
    alto = metricas(app)["Pedidos completados esperados"]
    app.checkbox[0].check().run()
    navidad = metricas(app)["Pedidos completados esperados"]
    assert not app.exception
    assert int(bajo.replace(".", "")) < int(alto.replace(".", "")) < int(navidad.replace(".", ""))
    # Diferencia de 3.000 € -> 30 × 4,18 ≈ 125 pedidos
    assert abs(int(alto.replace(".", "")) - int(bajo.replace(".", "")) - 30 * u.efecto_100_euros()["pedidos"]) <= 1


def test_ficha_cliente_199():
    """El caso encontrado en Power BI: el recuperable con más gasto tiene un pedido sospechoso."""
    app = abrir("pages/2_Ficha_de_cliente.py")
    assert app.selectbox[0].value == 199, "El cliente inicial debería ser el recuperable con más gasto (199)"
    valores = metricas(app)
    assert valores["Segmento"] == "Habituales"
    assert valores["Acción"] == "Recuperable"
    assert valores["Gasto total"] == "11.026,56 €"
    assert len(app.error) == 1, "Debería haber un aviso de pedido sospechoso"
    aviso = app.error[0].value
    for frase in ["**6477**", "**10.389,60 €**", "nº **2**", "636,96 €"]:
        assert frase in aviso, f"Falta «{frase}» en el aviso"


def test_ficha_otros_clientes():
    """Un cliente de cada tipo de acción, y uno sin compras, se muestran sin errores."""
    clientes = u.clientes()
    app = abrir("pages/2_Ficha_de_cliente.py")
    for accion in [u.PERDIDO, u.NO_EN_RIESGO, u.SIN_COMPRAS]:
        id_cliente = clientes.index[clientes["accion"] == accion][0]
        app.selectbox[0].set_value(id_cliente).run()
        assert not app.exception, f"Error con el cliente {id_cliente} ({accion})"
        if accion == u.SIN_COMPRAS:
            assert app.info, "Falta el aviso de cliente sin compras"
        else:
            assert metricas(app)["Acción"] == accion


def test_pedidos_sospechosos():
    app = abrir("pages/3_Pedidos_sospechosos.py")
    assert metricas(app)["Pedidos marcados"] == "121"
    assert len(app.table[0].value) == 121
    assert app.table[0].value.iloc[0]["Pedido"] == 348  # el nº 1 del ranking

    # Filtros: solo 2026 y solo Fieles
    app.multiselect[0].set_value([2026]).run()
    app.multiselect[1].set_value(["Fieles"]).run()
    assert not app.exception
    pedidos = u.pedidos()
    esperado = (pedidos["marcado"] & (pedidos["fecha_pedido"].dt.year == 2026)
                & (pedidos["nombre_segmento"] == "Fieles")).sum()
    assert metricas(app)["Pedidos marcados"] == str(esperado)

    # Sin ningún año elegido: mensaje, no error
    app.multiselect[0].set_value([]).run()
    assert not app.exception and app.info


# ---------------------------------------------------------------------------------------
# 3. Las cifras de la app coinciden con los CSV de los notebooks
# ---------------------------------------------------------------------------------------

def test_cifras_iguales_que_los_notebooks():
    """La app no lee los CSV de los notebooks; aquí se comprueba que calcula exactamente lo mismo.

    Si los CSV no existen (no se han ejecutado los notebooks), se comprueban solo los totales.
    """
    carpeta = RAIZ / "data" / "processed"
    clientes, pedidos = u.clientes(), u.pedidos()

    assert clientes["accion"].value_counts().to_dict() == {
        "No en riesgo": 287, "Recuperable": 95, "Probablemente perdido": 92, u.SIN_COMPRAS: 19}
    assert int(pedidos["marcado"].sum()) == 121
    assert u.euros(u.kpis_ventas()["ingresos"]) == "883.360,54 €"

    if (carpeta / "segmentos_clientes.csv").exists():
        seg = pd.read_csv(carpeta / "segmentos_clientes.csv").set_index("id_cliente")
        assert (clientes["nombre_segmento"] == seg["nombre_segmento"].reindex(clientes.index)).all()
    if (carpeta / "riesgo_recompra.csv").exists():
        rie = pd.read_csv(carpeta / "riesgo_recompra.csv").set_index("id_cliente")
        app = clientes.loc[rie.index]
        assert (app["prob_volver"].round(6) == rie["prob_volver"]).all()
        assert (app["accion"] == rie["accion"]).all()
    if (carpeta / "pedidos_sospechosos.csv").exists():
        sos = pd.read_csv(carpeta / "pedidos_sospechosos.csv", keep_default_na=False).set_index("id_pedido")
        app = pedidos.set_index("id_pedido").loc[sos.index]
        assert (app["puntuacion"].round(6) == sos["puntuacion"]).all()
        assert (app["ranking"] == sos["ranking"]).all()
        assert (app["marcado"].astype(int) == sos["marcado"]).all()
        assert (app["motivo"] == sos["motivo_principal"]).all()


# ---------------------------------------------------------------------------------------
# 4. Seguridad: la app no muestra datos personales
# ---------------------------------------------------------------------------------------

def texto_completo(app: AppTest) -> str:
    """Todo lo que muestra la página: textos, opciones de los selectores, métricas y tablas.

    Cada elemento de la página es un mensaje protobuf (el formato con el que Streamlit envía la
    página al navegador); se pasa a texto con as_utf8=True para que "García" no salga escapado.
    """
    from google.protobuf.text_format import MessageToString
    partes = []

    def recorrer(nodo):
        if getattr(nodo, "proto", None) is not None:
            partes.append(MessageToString(nodo.proto, as_utf8=True))
        if type(nodo).__name__ in ("Dataframe", "Table"):
            partes.append(nodo.value.to_string())
        hijos = getattr(nodo, "children", None) or {}
        for hijo in (hijos.values() if isinstance(hijos, dict) else hijos):
            recorrer(hijo)

    recorrer(app._tree)
    return "\n".join(partes)


def test_sin_datos_personales():
    """Ningún nombre ni email de cliente aparece en ninguna página (solo id_cliente)."""
    personales = u.leer_sql("SELECT nombre, email FROM clientes")
    buscados = [v for v in pd.concat([personales["nombre"], personales["email"]]).dropna() if len(v) > 3]
    paginas = ["Inicio.py", "pages/1_Simulador_publicidad.py", "pages/2_Ficha_de_cliente.py",
               "pages/3_Pedidos_sospechosos.py"]
    textos = [texto_completo(abrir(p)) for p in paginas]

    # Ficha: el cliente inicial (199) y uno de cada acción
    ficha = abrir("pages/2_Ficha_de_cliente.py")
    clientes = u.clientes()
    for accion in [u.PERDIDO, u.NO_EN_RIESGO, u.SIN_COMPRAS]:
        ficha.selectbox[0].set_value(clientes.index[clientes["accion"] == accion][0]).run()
        textos.append(texto_completo(ficha))

    todo = "\n".join(textos)
    assert "Cliente 199" in todo and "883.360,54" in todo   # el recorrido sí lee el contenido
    encontrados = [v for v in buscados if v in todo]
    assert not encontrados, f"La app muestra datos personales: {len(encontrados)} (p. ej. {encontrados[0][:3]}...)"


def test_solo_modelos_permitidos():
    """cargar_modelo() rechaza cualquier nombre que no sea uno de los 5 modelos de models/."""
    for nombre in ["../data/processed/otro", "C:/Windows/algo", "recompra_knn.joblib", ""]:
        try:
            u.cargar_modelo(nombre)
        except ValueError:
            continue
        raise AssertionError(f"cargar_modelo() aceptó {nombre!r}")
    assert all(isinstance(u.cargar_modelo(n), dict) for n in u.MODELOS_PERMITIDOS)


def test_formato_espanol():
    assert u.euros(883360.54) == "883.360,54 €"
    assert u.euros(1234.5, 0) == "1.234 €"   # redondeo de Python: 1234,5 -> 1234 (al par)
    assert u.numero(6541) == "6.541"
    assert u.porcentaje(0.3945) == "39,5 %"
    assert u.fecha(pd.Timestamp("2026-06-07")) == "07/06/2026"


# ---------------------------------------------------------------------------------------
# Ejecución sin pytest
# ---------------------------------------------------------------------------------------

if __name__ == "__main__":
    pruebas = [(nombre, f) for nombre, f in list(globals().items()) if nombre.startswith("test_")]
    fallos = 0
    for nombre, prueba in pruebas:
        inicio = time.perf_counter()
        try:
            prueba()
            print(f"OK     {nombre} ({time.perf_counter() - inicio:.1f} s)")
        except Exception:
            fallos += 1
            print(f"FALLO  {nombre}")
            traceback.print_exc()
    print(f"\n{len(pruebas) - fallos} de {len(pruebas)} pruebas superadas")
    sys.exit(1 if fallos else 0)
