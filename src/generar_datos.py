""" Genera los datos simulados de la tienda online
Paso 1: tablas maestras(categorias, proveedores, productos, clientes).
Paso 2: campanas, pedidos y detalle_pedido.
Paso 3: anomalías (guardadas en _verdad_anomalias.csv) y suciedad en los CSV.
Los CSV se guardan en data/raw/.
"""
from pathlib import Path


import numpy as np
import pandas as pd
from faker import Faker

#Configuración
RAIZ= Path(__file__).resolve().parent.parent
CARPETA_RAW= RAIZ/ "data"/ "raw"
SEMILLA= 42 #misma semilla, mismos datos cada vez
N_CLIENTES= 500
FECHA_INICIO= pd.Timestamp("2024-11-01")
FECHA_FIN=pd.Timestamp("2026-10-31")
fake = Faker("es_ES") #Nombres, emails, y empresas en Español
Faker.seed(SEMILLA)
rng=np.random.default_rng(SEMILLA)

CATALOGO ={
"Electrónica": (["Auriculares inalámbricos", "Altavoz Bluetooth", "Smartwatch",
                     "Cargador rápido", "Ratón inalámbrico"], (15, 250)),
    "Hogar": (["Lámpara de escritorio", "Juego de sartenes", "Cafetera",
               "Set de toallas", "Organizador de armario"], (10, 120)),
    "Deporte": (["Esterilla de yoga", "Mancuernas", "Botella térmica",
                 "Banda elástica", "Mochila deportiva"], (8, 90)),
    "Moda": (["Sudadera", "Zapatillas urbanas", "Gorra",
              "Cinturón de piel", "Bufanda"], (12, 110)),
    "Libros": (["Novela negra", "Libro de cocina", "Guía de viajes",
                "Cómic", "Libro de programación"], (8, 45)),
    "Belleza": (["Crema hidratante", "Perfume", "Kit de maquillaje",
                 "Champú sólido", "Sérum facial"], (6, 80)),
}
VARIANTES= ["Básico", "Premium"]

#Ciudades y su peso (cuánto compran cada una)
CIUDADES= {"Madrid": 0.25, "Barcelona": 0.18, "Valencia": 0.10, "Sevilla": 0.08,
            "Zaragoza": 0.06, "Málaga": 0.06, "Bilbao": 0.05, "Murcia": 0.05,
            "Alicante": 0.05, "Valladolid": 0.04, "Granada": 0.04, "A Coruña": 0.04 }
TIPOS_CLIENTE={"fiel": 0.15, "ocasional": 0.50, "puntual": 0.35}

#Campañas: canal y rango de inversión en €
CANALES={"google_ads": (800,3000), "meta_ads": (500,2500), "email": (100,400)}

#Multiplicador por mes del año: noviembre y diciembre venden más
ESTACIONALIDAD= {1: 0.9, 2: 0.8, 3: 0.9, 4: 0.95, 5: 1.0, 6: 0.95,
                  7: 0.85, 8: 0.75, 9: 1.0, 10: 1.05, 11: 1.4, 12: 1.5}

#Pedidos de cada mes= base x estacionalidad + efecto de la publicidad + ruido
PEDIDOS_BASE= 150
PEDIDOS_POR_EURO= 0.05 # cada 100€ de publicidad trae unos 5 pedidos más
RUIDO_PEDIDOS=25 # desviación típica del ruido

#Cuánto "tira" cada tipo de cliente a la hora de comprar
PESO_TIPO={"fiel": 4.0, "ocasional": 1.0, "puntual": 3.0}
PESO_PUNTUAL_DESPUES= 0.03
ESTADOS= {"completado": 0.90, "cancelado": 0.05, "devuelto": 0.05}
METODOS_PAGO={"tarjeta": 0.55, "paypal": 0.20, "bizum": 0.20, "transferencia": 0.05}

#Generadores
def generar_categorias()  -> pd.DataFrame:
    return pd.DataFrame({
        "id_categoria": range(1, len(CATALOGO) + 1),
        "nombre": list(CATALOGO.keys()),
    })
def generar_proveedores(n:int = 8) -> pd.DataFrame:
    paises= rng.choice(["España", "Portugal", "Francia", "China"], size=n,
                        p=[0.6, 0.15, 0.1, 0.15])
    return pd.DataFrame({
        "id_proveedor": range(1, n + 1),
        "nombre": [fake.unique.company() for _ in range(n)],
        "email": [fake.unique.email() for _ in range(n)],
        "pais": paises,
    })
def generar_productos(categorias: pd.DataFrame, proveedores: pd.DataFrame) -> pd.DataFrame:
    filas=[]
    for id_cat, nombre_cat in zip(categorias["id_categoria"], categorias["nombre"]):
        productos_base,(pmin, pmax)= CATALOGO[nombre_cat]
        for base in productos_base:
            for variante in VARIANTES:
                precio= rng.uniform(pmin, pmax /2)
                if variante =="Premium":
                    precio *= rng.uniform(1.6, 2.0) # el premium es más caro
                margen= rng.uniform(0.25, 0.55) #entre un 25-55% de margen
                filas.append({
                    "nombre": f"{base} {variante}",
                    "id_categoria": id_cat,
                    "id_proveedor": int(rng.choice(proveedores["id_proveedor"])),
                    "precio": round(precio, 2),
                    "coste": round(precio * (1 - margen), 2),
                })
    prductos= pd.DataFrame(filas)
    prductos.insert(0, "id_producto", range(1, len(filas) + 1))
    return prductos
def generar_clientes(n:int= N_CLIENTES) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (clientes, verdad): verdad guarda el tipo oculto de cada cliente. """
    dias_totales= (FECHA_FIN - FECHA_INICIO).days
    dias_alta= (rng.beta(1.2, 2.0, size=n) * dias_totales).astype(int)

    clientes= pd.DataFrame({
        "id_cliente": range(1, n + 1),
        "nombre": [fake.name() for _ in range(n)],
        "email": [fake.unique.free_email() for _ in range(n)],
        "ciudad": rng.choice(list(CIUDADES), size=n, p=list(CIUDADES.values())),
        "fecha_alta": (FECHA_INICIO + pd.to_timedelta(dias_alta, unit="D")).strftime("%Y-%m-%d"),
    })
    verdad= pd.DataFrame({
        "id_cliente": clientes["id_cliente"],
        "tipo_real": rng.choice(list(TIPOS_CLIENTE), size=n, p=list(TIPOS_CLIENTE.values())),
    })
    return clientes, verdad
def generar_campanas() -> pd.DataFrame:
    filas= []
    for mes in pd.period_range(FECHA_INICIO, FECHA_FIN, freq= "M"):
        for canal, (minimo, maximo) in CANALES.items():
            inversion= rng.uniform(minimo, maximo) * ESTACIONALIDAD[mes.month] ** 0.5
            filas.append({"mes": str(mes), "canal": canal, "inversion": round(inversion, 2)})
    campanas= pd.DataFrame(filas)
    campanas.insert(0, "id_campana", range(1, len(filas) + 1))
    return campanas
def generar_pedidos(clientes: pd.DataFrame, verdad:pd.DataFrame, campanas: pd.DataFrame) -> pd.DataFrame:
    alta= pd.to_datetime(clientes["fecha_alta"]).to_numpy()
    tipo= verdad["tipo_real"].to_numpy()
    peso_base= np.array([PESO_TIPO[t] for t in tipo])
    inversion_mes= campanas.groupby("mes")["inversion"].sum()
    filas= []

    for mes, inversion in inversion_mes.items():
        periodo= pd.Period(mes, freq="M")
        inicio, fin= periodo.start_time, periodo.end_time.normalize()

        # 1) Cuántos pedidos hay este mes: aquí está la relación que buscará la regresión
        n= PEDIDOS_BASE * ESTACIONALIDAD[periodo.month] + PEDIDOS_POR_EURO * inversion
        n= max(int(round(n + rng.normal(0, RUIDO_PEDIDOS))), 0)

        # 2) Quién compra: solo clientes ya dados de alta, con más peso para los fieles
        activos= alta <= fin.to_datetime64()
        pesos= peso_base.copy()
        dias_desde_alta= (fin - pd.to_datetime(alta)).days.to_numpy()
        pesos[(tipo== "puntual") & (dias_desde_alta > 31 )]= PESO_PUNTUAL_DESPUES
        pesos[~activos]= 0
        compradores= rng.choice(clientes["id_cliente"], size=n, p=pesos/ pesos.sum())

        #3) Qué día: aleatorio dentro del mes, nunca antes del alta del cliente
        dias= rng.integers(0, (fin-inicio).days +1, size=n)
        for id_cliente, dia in zip(compradores, dias):
            fecha= max(inicio + pd.Timedelta(days= int(dia)), pd.Timestamp(alta[id_cliente -1]))
            filas.append({"id_cliente": int(id_cliente), "fecha_pedido": fecha.strftime("%Y-%m-%d")})

    # 4) Ordenar por fecha y numerar: así id_pedido crece con el tiempo, como en una tienda real
    pedidos= pd.DataFrame(filas).sort_values("fecha_pedido", kind="stable").reset_index(drop=True)
    pedidos.insert(0, "id_pedido", range(1, len(pedidos) + 1))
    pedidos["estado"]= rng.choice(list(ESTADOS), size=len(pedidos), p=list(ESTADOS.values()))
    pedidos["metodo_pago"]= rng.choice(list(METODOS_PAGO), size=len(pedidos), p=list(METODOS_PAGO.values()))
    return pedidos

#Líneas por pedido y unidades por línea en un pedido normal
LINEAS_POR_PEDIDO= {1: 0.60, 2: 0.25, 3: 0.10, 4: 0.05}
UNIDADES_POR_LINEA= {1: 0.60, 2: 0.25, 3: 0.10, 4: 0.03, 5: 0.02}

def generar_detalle(pedidos: pd.DataFrame, productos: pd.DataFrame) -> pd.DataFrame:
    """Crea las líneas de cada pedido: qué productos, cuántas unidades y a qué precio."""
    precio_de= productos.set_index("id_producto")["precio"]
    n_lineas= rng.choice(list(LINEAS_POR_PEDIDO), size=len(pedidos), p=list(LINEAS_POR_PEDIDO.values()))
    filas= []
    for id_pedido, n in zip(pedidos["id_pedido"], n_lineas):
        # replace=False: un producto no se repite dentro del mismo pedido (es la clave primaria)
        elegidos= rng.choice(productos["id_producto"], size=n, replace=False)
        cantidades= rng.choice(list(UNIDADES_POR_LINEA), size=n, p=list(UNIDADES_POR_LINEA.values()))
        for id_producto, cantidad in zip(elegidos, cantidades):
            filas.append({
                "id_pedido": int(id_pedido),
                "id_producto": int(id_producto),
                "cantidad": int(cantidad),
                "precio_unitario": float(precio_de[id_producto]),  # se vende al precio de catálogo
            })
    return pd.DataFrame(filas)

# ---------------------------------------------------------------
# Paso 3a: anomalías (pedidos válidos pero raros, para Isolation Forest)
# ---------------------------------------------------------------
PORCENTAJE_ANOMALIAS= 0.01
TIPOS_ANOMALIA= ["cantidad_enorme", "precio_anomalo", "muchas_lineas"]

def plantar_anomalias(pedidos: pd.DataFrame, detalle: pd.DataFrame,
                      productos: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Modifica ~1 % de los pedidos para que sean raros y devuelve (detalle, verdad).

    Todas las anomalías cumplen el esquema (cantidad > 0, precio > 0, sin productos
    repetidos en un pedido): son pedidos posibles, no errores de formato.
    """
    detalle= detalle.copy()
    precio_de= productos.set_index("id_producto")["precio"]
    n= round(len(pedidos) * PORCENTAJE_ANOMALIAS)
    elegidos= rng.choice(pedidos["id_pedido"], size=n, replace=False)
    tipos= rng.choice(TIPOS_ANOMALIA, size=n)
    nuevas_lineas= []

    for id_pedido, tipo in zip(elegidos, tipos):
        lineas= detalle.index[detalle["id_pedido"] == id_pedido]
        linea= rng.choice(lineas)  # la línea que se vuelve rara
        if tipo == "cantidad_enorme":
            # Un pedido normal lleva 1-5 unidades por línea
            detalle.loc[linea, "cantidad"]= int(rng.integers(20, 61))
        elif tipo == "precio_anomalo":
            # Precio x5-x10 o x0,1-x0,2 respecto al de catálogo (nunca 0)
            if rng.random() < 0.5:
                factor= rng.uniform(5, 10)
            else:
                factor= rng.uniform(0.1, 0.2)
            precio= precio_de[detalle.loc[linea, "id_producto"]]
            detalle.loc[linea, "precio_unitario"]= max(round(precio * factor, 2), 0.01)
        else:  # muchas_lineas: un pedido normal lleva 1-4 líneas
            ya_tiene= set(detalle.loc[lineas, "id_producto"])
            disponibles= [p for p in productos["id_producto"] if p not in ya_tiene]
            extra= int(rng.integers(8, 13)) - len(lineas)
            for id_producto in rng.choice(disponibles, size=extra, replace=False):
                nuevas_lineas.append({
                    "id_pedido": int(id_pedido),
                    "id_producto": int(id_producto),
                    "cantidad": int(rng.choice(list(UNIDADES_POR_LINEA), p=list(UNIDADES_POR_LINEA.values()))),
                    "precio_unitario": float(precio_de[id_producto]),
                })

    # Las líneas nuevas se colocan junto a las de su pedido
    detalle= (pd.concat([detalle, pd.DataFrame(nuevas_lineas)], ignore_index=True)
                .sort_values("id_pedido", kind="stable").reset_index(drop=True))
    verdad= (pd.DataFrame({"id_pedido": elegidos.astype(int), "tipo_anomalia": tipos})
               .sort_values("id_pedido").reset_index(drop=True))
    return detalle, verdad

# ---------------------------------------------------------------
# Paso 3b: suciedad (errores típicos de un sistema mal mantenido)
# ---------------------------------------------------------------
# Cada tipo de problema afecta a entre el 1 % y el 3 % de las filas.
SUCIEDAD_MIN, SUCIEDAD_MAX= 0.01, 0.03

def elegir_filas(candidatas, usadas: set) -> list:
    """Elige entre el 1 % y el 3 % de las filas candidatas que aún no tengan otro problema.

    Usar filas distintas para cada problema hace que cada error se pueda contar
    y arreglar por separado en la limpieza.
    """
    libres= [i for i in candidatas if i not in usadas]
    n= round(len(candidatas) * rng.uniform(SUCIEDAD_MIN, SUCIEDAD_MAX))
    elegidas= sorted(rng.choice(libres, size=n, replace=False).tolist())
    usadas.update(elegidas)
    return elegidas

def duplicar_filas(df: pd.DataFrame, usadas: set) -> pd.DataFrame:
    """Añade copias exactas de algunas filas, justo debajo de la original."""
    copias= elegir_filas(df.index, usadas)
    return pd.concat([df, df.loc[copias]]).sort_index(kind="stable").reset_index(drop=True)

def fecha_formato_europeo(fechas: pd.Series) -> pd.Series:
    """'2025-03-05' -> '05/03/2025' (la misma fecha, otro formato)."""
    return pd.to_datetime(fechas).dt.strftime("%d/%m/%Y")

def fechas_imposibles(n: int) -> list[str]:
    """Fechas con mes y día que no existen, como '2025-13-45'."""
    return [f"{rng.integers(2024, 2027)}-{rng.integers(13, 20)}-{rng.integers(32, 46)}" for _ in range(n)]

def ensuciar_clientes(clientes: pd.DataFrame, protegidos: set) -> pd.DataFrame:
    """protegidos: clientes con pedidos anómalos; no reciben errores irrecuperables."""
    df= clientes.copy()
    usadas= set()
    no_protegidas= df.index[~df["id_cliente"].isin(protegidos)]

    filas= elegir_filas(no_protegidas, usadas)
    df.loc[filas, "email"]= None                                   # nulo en obligatoria
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "email"]= df.loc[filas, "email"].str.upper()     # email en mayúsculas
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "ciudad"]= df.loc[filas, "ciudad"].str.lower()   # ciudad en minúsculas
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "fecha_alta"]= fecha_formato_europeo(df.loc[filas, "fecha_alta"])
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "fecha_alta"]= fechas_imposibles(len(filas))
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "fecha_alta"]= ""                                # texto vacío

    return duplicar_filas(df, usadas)

VARIANTES_ESTADO= {"completado": [" Completado", "COMPLETADO", "completado "],
                   "cancelado": [" Cancelado", "CANCELADO"],
                   "devuelto": ["DEVUELTO ", " Devuelto"]}

def ensuciar_pedidos(pedidos: pd.DataFrame, protegidos: set) -> pd.DataFrame:
    """protegidos: pedidos anómalos; no reciben errores irrecuperables."""
    df= pedidos.copy()
    # Int64 (con mayúscula) es el entero de pandas que admite nulos; pandas 3 no deja
    # meter un nulo en una columna int64 normal, y así tampoco se escribe "468.0" en el CSV
    df["id_cliente"]= df["id_cliente"].astype("Int64")
    usadas= set()
    no_protegidas= df.index[~df["id_pedido"].isin(protegidos)]

    filas= elegir_filas(no_protegidas, usadas)
    df.loc[filas, "id_cliente"]= pd.NA                             # nulo en obligatoria
    filas= elegir_filas(no_protegidas, usadas)
    df.loc[filas, "fecha_pedido"]= None                            # nulo en obligatoria
    filas= elegir_filas(no_protegidas, usadas)
    df.loc[filas, "fecha_pedido"]= fechas_imposibles(len(filas))
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "fecha_pedido"]= fecha_formato_europeo(df.loc[filas, "fecha_pedido"])
    filas= elegir_filas(df.index, usadas)
    # El estado mal escrito sigue siendo el mismo estado (solo cambian mayúsculas y espacios)
    df.loc[filas, "estado"]= [rng.choice(VARIANTES_ESTADO[e]) for e in df.loc[filas, "estado"]]

    return duplicar_filas(df, usadas)

def ensuciar_detalle(detalle: pd.DataFrame) -> pd.DataFrame:
    """Añade total_linea (como en una exportación real) y estropea algunas filas."""
    df= detalle.copy()
    # total_linea se calcula ANTES de estropear nada: es el valor "bueno" de referencia
    df["total_linea"]= (df["cantidad"] * df["precio_unitario"]).round(2)
    df["cantidad"]= df["cantidad"].astype("Int64")  # entero que admite nulos (ver ensuciar_pedidos)
    usadas= set()

    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "cantidad"]= pd.NA                               # nulo en obligatoria
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "precio_unitario"]= None                         # nulo en obligatoria
    filas= elegir_filas(df.index, usadas)
    df.loc[filas, "cantidad"]= -df.loc[filas, "cantidad"]          # cantidad negativa
    filas= elegir_filas(df.index, usadas)
    # total_linea incoherente: no coincide con cantidad x precio_unitario
    df.loc[filas, "total_linea"]= (df.loc[filas, "total_linea"] * rng.uniform(1.1, 3.0, size=len(filas))).round(2)

    return duplicar_filas(df, usadas)

#Programa principal
def guardar(df: pd.DataFrame, nombre: str) -> None:
    ruta= CARPETA_RAW / f"{nombre}.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f" {nombre:<20} {len(df):>6} filas -> {ruta.name}")

def main() -> None:
    CARPETA_RAW.mkdir(parents=True, exist_ok=True)
    print("Generando datos en", CARPETA_RAW)

    categorias= generar_categorias()
    proveedores= generar_proveedores()
    productos= generar_productos(categorias, proveedores)
    clientes, verdad_clientes= generar_clientes()
    campanas= generar_campanas()
    pedidos= generar_pedidos(clientes, verdad_clientes, campanas)
    detalle= generar_detalle(pedidos, productos)

    # Orden importante: 1) datos limpios, 2) anomalías, 3) suciedad.
    # Las anomalías se plantan sobre datos limpios y la suciedad va al final,
    # igual que en la vida real: el pedido raro existe y luego la exportación lo estropea.
    detalle, verdad_anomalias= plantar_anomalias(pedidos, detalle, productos)
    pedidos_anomalos= set(verdad_anomalias["id_pedido"])
    clientes_anomalos= set(pedidos.loc[pedidos["id_pedido"].isin(pedidos_anomalos), "id_cliente"])
    clientes= ensuciar_clientes(clientes, clientes_anomalos)
    pedidos= ensuciar_pedidos(pedidos, pedidos_anomalos)
    detalle= ensuciar_detalle(detalle)

    guardar(categorias, "categorias")
    guardar(productos, "productos")
    guardar(clientes, "clientes")
    guardar(verdad_clientes, "_verdad_clientes")
    guardar(proveedores, "proveedores")
    guardar(campanas, "campanas")
    guardar(pedidos, "pedidos")
    guardar(detalle, "detalle_pedido")
    guardar(verdad_anomalias, "_verdad_anomalias")

if __name__ == "__main__":
    main()
