""" Genera los datos simulados de la tienda online
Paso 1: tablas maestras(categorias, proveedores, productos, clientes).
Paso 2: campanas, pedidos y detalle_pedido.
Los CSV se guardan en data/raw/.
"""
from pathlib import Path


import numpy as np
import pandas as pd
from faker import Faker

#Configuración
raiz= Path(__file__).resolve().parent.parent
carpeta_raw= raiz/ "data"/ "raw"
semilla= 42 #misma semilla, mismos datos cada vez
n_clientes= 500
Fecha_inicio= pd.Timestamp("2024-11-01")
Fecha_fin=pd.Timestamp("2026-10-31")
fake = Faker("es_ES") #Nombres, emails, y empresas en Español
Faker.seed(semilla)
rng=np.random.default_rng(semilla)

Catalogo ={
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
Variantes= ["Básico", "Premium"]

#Ciudades y su peso (cuánto compran cada una)
Ciudades= {"Madrid": 0.25, "Barcelona": 0.18, "Valencia": 0.10, "Sevilla": 0.08,
            "Zaragoza": 0.06, "Málaga": 0.06, "Bilbao": 0.05, "Murcia": 0.05,
            "Alicante": 0.05, "Valladolid": 0.04, "Granada": 0.04, "A Coruña": 0.04 }
Tipos_Cliente={"fiel": 0.15, "ocasional": 0.50, "puntual": 0.35}

#Campañas: canal y rango de inversión en €
Canales={"google_ads": (800,3000), "meta_ads": (500,2500), "email": (100,400)}

#Multiplicador por mes del año: noviembre y diciembre venden más
Estacionalidad= {1: 0.9, 2: 0.8, 3: 0.9, 4: 0.95, 5: 1.0, 6: 0.95,
                  7: 0.85, 8: 0.75, 9: 1.0, 10: 1.05, 11: 1.4, 12: 1.5}

#Pedidos de cada mes= base x estacionalidad + efecto de la publicidad + ruido
Pedidos_base= 150
Pedidos_por_euro= 0.05 # cada 100€ de publicidad trae unos 5 pedidos más
Ruido_pedidos=25 # desviación típica del ruido

#Cuánto "tira" cada tipo de cliente a la hora de comprar
Peso_tipo={"fiel": 4.0, "ocasional": 1.0, "puntual": 3.0}
Peso_puntual_despues= 0.03
Estados= {"completado": 0.90, "cancelado": 0.05, "devuelto": 0.05}
Metodos_pago={"tarjeta": 0.55, "paypal": 0.20, "bizum": 0.20, "transferencia": 0.05}

#Generadores
def generar_categorias()  -> pd.DataFrame:
    return pd.DataFrame({
        "id_categoria": range(1, len(Catalogo) + 1),
        "nombre": list(Catalogo.keys()),
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
        productos_base,(pmin, pmax)= Catalogo[nombre_cat]
        for base in productos_base:
            for variante in Variantes:
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
def generar_clientes(n:int= n_clientes) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (clientes, verdad): verdad guarda el tipo oculto de cada cliente. """
    dias_totales= (Fecha_fin - Fecha_inicio).days
    dias_alta= (rng.beta(1.2, 2.0, size=n) * dias_totales).astype(int)

    clientes= pd.DataFrame({
        "id_cliente": range(1, n + 1),
        "nombre": [fake.name() for _ in range(n)],
        "email": [fake.unique.free_email() for _ in range(n)],
        "ciudad": rng.choice(list(Ciudades), size=n, p=list(Ciudades.values())),
        "fecha_alta": (Fecha_inicio + pd.to_timedelta(dias_alta, unit="D")).strftime("%Y-%m-%d"),
    })
    verdad= pd.DataFrame({
        "id_cliente": clientes["id_cliente"],
        "tipo_real": rng.choice(list(Tipos_Cliente), size=n, p=list(Tipos_Cliente.values())),
    })
    return clientes, verdad
def generar_campanas() -> pd.DataFrame:
    filas= []
    for mes in pd.period_range(Fecha_inicio, Fecha_fin, freq= "M"):
        for canal, (minimo, maximo) in Canales.items():
            inversion= rng.uniform(minimo, maximo) * Estacionalidad[mes.month] ** 0.5
            filas.append({"mes": str(mes), "canal": canal, "inversion": round(inversion, 2)})
    campanas= pd.DataFrame(filas)
    campanas.insert(0, "id_campana", range(1, len(filas) + 1))
    return campanas
def generar_pedidos(clientes: pd.DataFrame, verdad:pd.DataFrame, campanas: pd.DataFrame) -> pd.DataFrame:
    alta= pd.to_datetime(clientes["fecha_alta"]).to_numpy()
    tipo= verdad["tipo_real"].to_numpy()
    peso_base= np.array([Peso_tipo[t] for t in tipo])
    inversion_mes= campanas.groupby("mes")["inversion"].sum()
    filas= []

    for mes, inversion in inversion_mes.items():
        periodo= pd.Period(mes, freq="M")
        inicio, fin= periodo.start_time, periodo.end_time.normalize()

        # 1) Cuántos pedidos hay este mes: aquí está la relación que buscará la regresión
        n= Pedidos_base * Estacionalidad[periodo.month] + Pedidos_por_euro * inversion
        n= max(int(round(n + rng.normal(0, Ruido_pedidos))), 0)

        # 2) Quién compra: solo clientes ya dados de alta, con más peso para los fieles
        activos= alta <= fin.to_datetime64()
        pesos= peso_base.copy()
        dias_desde_alta= (fin - pd.to_datetime(alta)).days.to_numpy()
        pesos[(tipo== "puntual") & (dias_desde_alta > 31 )]= Peso_puntual_despues
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
    pedidos["estado"]= rng.choice(list(Estados), size=len(pedidos), p=list(Estados.values()))
    pedidos["metodo_pago"]= rng.choice(list(Metodos_pago), size=len(pedidos), p=list(Metodos_pago.values()))
    return pedidos

#Líneas por pedido y unidades por línea en un pedido normal
Lineas_por_pedido= {1: 0.60, 2: 0.25, 3: 0.10, 4: 0.05}
Unidades_por_linea= {1: 0.60, 2: 0.25, 3: 0.10, 4: 0.03, 5: 0.02}

def generar_detalle(pedidos: pd.DataFrame, productos: pd.DataFrame) -> pd.DataFrame:
    """Crea las líneas de cada pedido: qué productos, cuántas unidades y a qué precio."""
    precio_de= productos.set_index("id_producto")["precio"]
    n_lineas= rng.choice(list(Lineas_por_pedido), size=len(pedidos), p=list(Lineas_por_pedido.values()))
    filas= []
    for id_pedido, n in zip(pedidos["id_pedido"], n_lineas):
        # replace=False: un producto no se repite dentro del mismo pedido (es la clave primaria)
        elegidos= rng.choice(productos["id_producto"], size=n, replace=False)
        cantidades= rng.choice(list(Unidades_por_linea), size=n, p=list(Unidades_por_linea.values()))
        for id_producto, cantidad in zip(elegidos, cantidades):
            filas.append({
                "id_pedido": int(id_pedido),
                "id_producto": int(id_producto),
                "cantidad": int(cantidad),
                "precio_unitario": float(precio_de[id_producto]),  # se vende al precio de catálogo
            })
    return pd.DataFrame(filas)

#Programa principal
def guardar(df: pd.DataFrame, nombre: str) -> None:
    ruta= carpeta_raw / f"{nombre}.csv"
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f" {nombre:<20} {len(df):>6} filas -> {ruta.name}")

def main() -> None:
    carpeta_raw.mkdir(parents=True, exist_ok=True)
    print("Generando datos en", carpeta_raw)

    categorias= generar_categorias()
    proveedores= generar_proveedores()
    productos= generar_productos(categorias, proveedores)
    clientes, verdad_clientes= generar_clientes()
    campanas= generar_campanas()
    pedidos= generar_pedidos(clientes, verdad_clientes, campanas)
    detalle= generar_detalle(pedidos, productos)

    guardar(categorias, "categorias")
    guardar(productos, "productos")
    guardar(clientes, "clientes")
    guardar(verdad_clientes, "_verdad_clientes")
    guardar(proveedores, "proveedores")
    guardar(campanas, "campanas")
    guardar(pedidos, "pedidos")
    guardar(detalle, "detalle_pedido")

if __name__ == "__main__":
    main()
