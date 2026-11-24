# Guía para construir el informe de Power BI (S10)

Informe de 3 páginas: **Ventas**, **Clientes** y **Alertas de pedidos**. Se guarda en
`dashboard/tienda.pbix`, que sí se sube a git.

Medidas DAX: [`powerbi_medidas.md`](powerbi_medidas.md).

## 0. Generar los datos

Desde la raíz del proyecto, con el entorno activado (`.venv\Scripts\activate`):

```powershell
python src/generar_datos.py
python src/limpieza.py
# Los notebooks 03, 04 y 05 generan los CSV de segmentos, alertas y riesgo de recompra
cd notebooks
jupyter nbconvert --to notebook --execute --inplace 03_segmentacion.ipynb
jupyter nbconvert --to notebook --execute --inplace 04_anomalias.ipynb
jupyter nbconvert --to notebook --execute --inplace 05_recompra.ipynb
cd ..
python src/exportar_powerbi.py
```

Si falta algún CSV de los notebooks, `exportar_powerbi.py` se para y dice qué notebook ejecutar.
Al terminar, comprueba que todas las líneas de verificación empiezan por `OK`.

Se crean 6 archivos en `data/processed/powerbi/`:

| Archivo | Filas | Qué es |
|---|---:|---|
| `dim_fecha.csv` | 1096 | Un día por fila, del 2024-01-01 al 2026-12-31 (años completos) |
| `dim_cliente.csv` | 493 | Cliente, ciudad, alta, segmento (S7), probabilidad de volver y acción (S9) |
| `dim_producto.csv` | 60 | Producto, categoría, proveedor y precio y coste de catálogo |
| `fact_ventas.csv` | 11879 | Una fila por línea de pedido, todos los estados |
| `fact_alertas.csv` | 7297 | Una fila por pedido con la puntuación de Isolation Forest (S8) |
| `fact_campanas.csv` | 72 | Inversión por mes y canal (24 meses × 3 canales) |

Todos usan `;` como separador, `,` como decimal, UTF-8 con BOM y fechas `AAAA-MM-DD`.

## 1. Importar los CSV

Para cada uno de los 6 archivos:

1. **Inicio → Obtener datos → Texto/CSV** y elige el archivo.
2. En la ventana de vista previa, comprueba:
   - **Origen del archivo:** `65001: Unicode (UTF-8)`. Si ves `Mï¿½laga` en lugar de `Málaga`, cámbialo.
   - **Delimitador:** `Punto y coma`.
   - **Detección del tipo de datos:** `Basado en las primeras 200 filas`.
3. Pulsa **Transformar datos** (no *Cargar*) para revisar los tipos en Power Query.
4. Revisa el icono de tipo de cada columna con esta tabla:

| Tipo en Power Query | Columnas |
|---|---|
| **Fecha** | `fecha` (dim_fecha, fact_ventas, fact_alertas), `fecha_alta`, `fecha_mes` |
| **Número decimal** | `precio_unitario`, `importe`, `coste`, `margen`, `importe_total`, `puntuacion`, `prob_volver`, `inversion`, `precio_catalogo`, `coste_catalogo` |
| **Número entero** | todas las `id_*`, `cantidad`, `anio`, `mes_num`, `trimestre`, `dia_semana_num`, `temporada_alta`, `segmento`, `ranking`, `marcado` |
| **Texto** | `nombre_mes`, `anio_mes`, `dia_semana`, `ciudad`, `nombre_segmento`, `accion`, `nombre_producto`, `categoria`, `proveedor`, `pais_proveedor`, `estado`, `metodo_pago`, `motivo_principal`, `canal` |

5. **Inicio → Cerrar y aplicar.**

**Si un número sale mal** (por ejemplo `4689` en lugar de `46,89`, o la columna sale como texto),
Power BI no ha usado la configuración española para leerlo:

- En Power Query, clic derecho en el encabezado de la columna → **Cambiar tipo → Usar configuración
  regional...** → Tipo de datos **Número decimal**, Configuración regional **Español (España)**.
- Si pasa con todas las columnas, revisa **Archivo → Opciones y configuración → Opciones → Archivo
  actual → Configuración regional → Configuración regional para la importación: Español (España)**
  y vuelve a importar.
- Con las fechas pasa igual: deben ser `AAAA-MM-DD`. Si salen como texto, *Cambiar tipo → Fecha*.

`prob_volver` está vacía en los 19 clientes sin compras completadas, y `motivo_principal` en los
pedidos no marcados. Es correcto: Power BI las lee como vacías (*null*).

## 2. Relaciones (modelo en estrella)

Ve a la **vista de modelo** (el tercer icono de la izquierda). Power BI puede haber creado
relaciones automáticas: **borra todas** las que no estén en esta tabla. Ojo con una posible
relación entre `fact_ventas[id_pedido]` y `fact_alertas[id_pedido]`: no debe existir, porque son
dos tablas de hechos y se relacionan a través de las dimensiones.

Para crear cada relación, arrastra la columna de la dimensión sobre la de la tabla de hechos, o
usa **Inicio → Administrar relaciones → Nueva**.

| Desde (lado 1) | Hacia (lado varios) | Cardinalidad | Dirección del filtro | Activa |
|---|---|---|---|---|
| `dim_fecha[fecha]` | `fact_ventas[fecha]` | Uno a varios (1:*) | Única (dim → fact) | Sí |
| `dim_fecha[fecha]` | `fact_alertas[fecha]` | Uno a varios (1:*) | Única | Sí |
| `dim_fecha[fecha]` | `fact_campanas[fecha_mes]` | Uno a varios (1:*) | Única | Sí |
| `dim_cliente[id_cliente]` | `fact_ventas[id_cliente]` | Uno a varios (1:*) | Única | Sí |
| `dim_cliente[id_cliente]` | `fact_alertas[id_cliente]` | Uno a varios (1:*) | Única | Sí |
| `dim_producto[id_producto]` | `fact_ventas[id_producto]` | Uno a varios (1:*) | Única | Sí |

```
                          ┌──────────────┐
                          │ dim_producto │
                          └──────┬───────┘
                                 │ 1
                                 ▼ *
┌─────────────┐ 1       * ┌─────────────┐ *       1 ┌───────────┐
│ dim_cliente │─────────▶│ fact_ventas │◀─────────│ dim_fecha │
└──────┬──────┘           └─────────────┘           └──┬─────┬──┘
       │ 1                                           1 │     │ 1
       │           * ┌──────────────┐ *                │     │
       └───────────▶│ fact_alertas │◀─────────────────┘     │
                     └──────────────┘                         ▼ *
                                                     ┌───────────────┐
                                                     │ fact_campanas │
                                                     └───────────────┘

   1 ──▶ *  =  uno a varios; la flecha marca la dirección del filtro (de la dimensión a los hechos)
```

- **Dirección única** (de la dimensión a los hechos): los filtros van de la dimensión a la tabla
  de hechos, nunca al revés. Es lo más sencillo y evita ambigüedades.
- `dim_cliente[fecha_alta]` **no** se relaciona con `dim_fecha`: sería una segunda relación con la
  misma tabla y tendría que estar inactiva. Para este informe no hace falta.
- **Ocultar las claves:** en las tablas de hechos, oculta (clic derecho → *Ocultar en la vista de
  informe*) `id_cliente`, `id_producto`, `fecha` y `fecha_mes`. Así, al construir visuales, se
  usan las de las dimensiones y los filtros siempre funcionan.
- **No resumir:** selecciona `anio`, `mes_num`, `trimestre`, `segmento`, `ranking` y todas las `id_*`
  y en *Herramientas de columnas → Resumen* elige **No resumir**. Si no, Power BI las suma.

## 3. `dim_fecha` como tabla de fechas, y ordenar meses y días

**Marcar como tabla de fechas** (necesario para `DATEADD` y `TOTALYTD`):
1. Selecciona la tabla `dim_fecha` en el panel *Datos*.
2. **Herramientas de tabla → Marcar como tabla de fechas** → columna **`fecha`** → Aceptar.
   Power BI comprueba que no haya fechas repetidas ni huecos (el script ya lo ha comprobado).

**Ordenar el nombre del mes por su número** (si no, salen en orden alfabético: abril, agosto...):
1. Selecciona la columna `dim_fecha[nombre_mes]`.
2. **Herramientas de columnas → Ordenar por columna → `mes_num`**.

Haz lo mismo con `dia_semana` → ordenar por `dia_semana_num`. `anio_mes` (`2025-03`) ya se ordena
bien sola, porque es texto con el año delante.

## 4. Las 3 páginas

Diseño común: un título arriba, una fila de tarjetas con los números clave, 2–3 gráficos en el
centro y las segmentaciones en una columna a la izquierda. Usa los mismos colores en todas las
páginas (por ejemplo, azul para las ventas y naranja para la publicidad y las alertas).

### Página 1 · Ventas

**Segmentaciones (izquierda):** `dim_fecha[anio]` (botones) y `dim_producto[categoria]` (lista).

| Posición | Visual | Campos y medidas |
|---|---|---|
| Arriba, fila de tarjetas | 5 tarjetas | `Ingresos`, `Margen bruto`, `% Margen`, `Nº pedidos`, `Ticket medio` |
| Centro izquierda | Gráfico de líneas | Eje X: `dim_fecha[anio_mes]` · Y: `Ingresos` |
| Centro derecha | Gráfico de columnas apiladas | Eje X: `dim_fecha[anio_mes]` · Y: `Inversión publicitaria` · Leyenda: `fact_campanas[canal]` |
| Abajo izquierda | Barras horizontales | Eje Y: `dim_producto[categoria]` · X: `Ingresos` (ordenado de mayor a menor) |
| Abajo derecha | Tabla | `dim_fecha[anio_mes]`, `Ingresos`, `Ingresos mes anterior`, `Variación % mensual`, `Ingresos acumulados del año` |
| Tarjeta pequeña | Tarjeta | `Ingresos por € de publicidad` |

Ventas e inversión van en **dos gráficos alineados y no en uno de doble eje**, como en el EDA de la
S5: con dos escalas en el mismo gráfico es fácil que dos series "parezcan" relacionadas.

### Página 2 · Clientes

**Segmentaciones:** `dim_cliente[nombre_segmento]`, `dim_cliente[accion]` y `dim_cliente[ciudad]`.

| Posición | Visual | Campos y medidas |
|---|---|---|
| Arriba, tarjetas | 3 tarjetas | `Nº clientes con compras`, `Clientes recuperables`, `Gasto histórico recuperables` |
| Centro izquierda | Barras horizontales | Eje Y: `dim_cliente[nombre_segmento]` · X: `Ingresos` |
| Centro derecha | Barras horizontales | Eje Y: `dim_cliente[accion]` · X: recuento de `dim_cliente[id_cliente]` |
| Abajo (ancho completo) | Tabla "Campaña de retención" | `dim_cliente[id_cliente]`, `nombre_segmento`, `ciudad`, `prob_volver`, `Ingresos` · Filtro del visual: `accion` = Recuperable · Ordenada por `Ingresos` descendente |

Esta página no lleva segmentación de fecha: los segmentos y la acción son una foto con todos los
datos, y la tabla de recuperables muestra el gasto histórico de cada cliente.

### Página 3 · Alertas de pedidos

**Segmentaciones:** `dim_fecha[anio]` y `fact_alertas[marcado]` (para ver solo los marcados o todos).

| Posición | Visual | Campos y medidas |
|---|---|---|
| Arriba, tarjetas | 3 tarjetas | `Pedidos marcados`, `Importe pedidos marcados`, `% Cancelados y devueltos` |
| Centro | Gráfico de columnas | Eje X: `dim_fecha[anio_mes]` · Y: `Pedidos marcados` |
| Abajo (ancho completo) | Tabla "Pedidos a revisar" | `fact_alertas[ranking]`, `id_pedido`, `dim_fecha[fecha]`, `dim_cliente[id_cliente]`, `importe_total`, `puntuacion`, `motivo_principal` · Filtro del visual: `marcado` = 1 · Ordenada por `ranking` ascendente (el 1 es el más sospechoso) |

En la tabla, ajusta el ancho de `motivo_principal` y activa *Ajuste de texto* para que el motivo
se lea entero.

## 5. Lista de comprobación final

Con **ningún filtro** aplicado, las tarjetas deben mostrar estos valores (salen de la ejecución de
`exportar_powerbi.py`). Si alguno no coincide, revisa el tipo de la columna, la relación o el
filtro de estado de la medida.

| Página | Tarjeta / medida | Valor esperado |
|---|---|---:|
| Ventas | Ingresos | **883.360,54 €** |
| Ventas | Coste | 527.338,35 € |
| Ventas | Margen bruto | 356.022,19 € |
| Ventas | % Margen | 40,3 % |
| Ventas | Nº pedidos | **6541** |
| Ventas | Ticket medio | **135,05 €** |
| Ventas | Inversión publicitaria | 84.427,43 € |
| Ventas | Ingresos por € de publicidad | 10,46 € |
| Clientes | Nº clientes con compras | 474 |
| Clientes | Clientes recuperables | **95** |
| Clientes | Gasto histórico recuperables | 64.266,35 € |
| Alertas | Pedidos marcados | **121** |
| Alertas | Importe pedidos marcados | 128.767,03 € |
| Alertas | % Cancelados y devueltos | 10,4 % (de 7297 pedidos) |

Comprobaciones con filtros:

- **Por año** (segmentación `anio`). Ingresos: 2024 → 112.843,81 € (solo noviembre y diciembre),
  2025 → 414.196,59 €, 2026 → 356.320,14 €. Con la segmentación en 2026, `Ingresos acumulados del
  año` en la fila de 2026-10 de la tabla también debe dar 356.320,14 €.
- **Último mes** (fila 2026-10 de la tabla de la página Ventas): `Ingresos` 41.470,23 €,
  `Ingresos mes anterior` 34.381,68 € y `Variación % mensual` 20,6 %.
- **Pedidos marcados por año:** 2024 → 17, 2025 → 54, 2026 → 50 (suman 121).
- **Clientes por segmento** (recuento de `id_cliente`): Habituales 204, Fieles 127, Compra única 74,
  Perdidos 69 y Sin compras completadas 19 (493 en total).
- **Clientes por acción:** No en riesgo 287, Recuperable 95, Probablemente perdido 92 y Sin datos 19.
- **Ingresos por categoría:** el primero es Electrónica, con 317.882,40 €, y el último Libros, con
  60.878,66 €.

Los totales generales coinciden con los de los notebooks: 883.361 € y 6.541 pedidos completados
(S5), 95 recuperables (S9) y 121 pedidos marcados (S8).

## 6. Decisiones que he tomado yo (por ambigüedad)

1. **`dim_fecha` con años completos** (del 2024-01-01 al 2026-12-31). Los datos van del 2024-11-02
   (primera alta) al 2026-10-31, pero las funciones de tiempo de DAX funcionan mejor con años
   enteros. Los días sin ventas simplemente no tienen filas en los hechos.
2. **Clientes sin compras completadas:** segmento `-1` con el nombre "Sin compras completadas", como
   en el CSV de la S7. En la S9 no se puntuaron: `accion` = "Sin datos" y `prob_volver` vacía. Se
   deja vacía en lugar de poner un 0, que se confundiría con "seguro que no vuelve".
3. **`fact_alertas` incluye todos los pedidos** (7297), no solo los marcados, para poder comparar
   marcados frente a no marcados. Las medidas filtran `marcado = 1`.
4. **`coste` de `fact_ventas` = cantidad × coste de catálogo**, igual que en la S6, y
   `margen = importe − coste`.
5. **Fechas de campañas:** el mes `2025-03` pasa a `2025-03-01` para poder relacionarlo con
   `dim_fecha`. Por eso la publicidad se analiza por mes o por año, no por día.
6. **Sin nombre ni email del cliente** (minimización de datos personales). Para identificar a un
   cliente en la tabla de la campaña basta con `id_cliente`; el equipo de marketing lo cruzaría con
   su CRM.
7. **Medidas de clientes en `dim_cliente` y de alertas en `fact_alertas`**, cada una en la tabla de
   la que cuenta filas. Si prefieres tenerlas todas juntas, puedes crear una tabla vacía
   `_Medidas` y moverlas allí (*Herramientas de medición → Tabla de inicio*).
8. **Formato de los CSV pensado para Power BI en español** (`;` y `,`). Si algún día se abren con
   pandas: `pd.read_csv(ruta, sep=";", decimal=",", encoding="utf-8-sig")`.
