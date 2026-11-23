# Explicación S5: análisis exploratorio (EDA)

Este documento explica la mejora de la limpieza (Tarea 0), el módulo `src/bd.py` y el notebook
`notebooks/01_eda.ipynb`: qué hace cada parte, por qué se hizo así y qué hemos descubierto.

## 0. Mejora de la limpieza: recuperar en vez de borrar

### Qué cambió en `src/limpieza.py`

**1. Recuperación de nulos en `detalle_pedido`, en cascada.** Se borra solo cuando no queda otra:

| Paso | Si falta... | Se recupera con... | Condición para aceptarlo |
|---|---|---|---|
| 1 | `cantidad` | `total_linea / precio_unitario` | Sale un entero positivo (no se venden 2,37 unidades) |
| 2 | `precio_unitario` | `total_linea / cantidad` | Es positivo y, al multiplicarlo otra vez por la cantidad, sale `total_linea` |
| 3 | `precio_unitario` (y el paso 2 no ha servido) | El precio de catálogo del producto | El producto existe |
| 4 | `cantidad` (si faltaban las dos) | Se repite el paso 1 con el precio ya recuperado | Igual que en el paso 1 |
| 5 | — | Se eliminan solo las filas que siguen incompletas | — |

La cantidad se repite (paso 4) para cubrir el caso de que falten las dos columnas: entonces el
paso 1 no puede hacer nada, pero después del paso 3 ya hay un precio con el que calcularla.

**2. `anotar()` guarda dos números nuevos por problema:** cuántas filas se han *recuperado*
(arregladas, siguen en la BD) y cuántas se han *eliminado*.

**3. El informe tiene columnas `Recuperadas` y `Eliminadas`** en la tabla de problemas y una
sección nueva, **"Recuperados frente a eliminados"**, con el total por tabla y el % recuperado.

### Resultado: las filas no cambian

| Tabla | Antes de la Tarea 0 | Después | Diferencia |
|---|---:|---:|---:|
| clientes | 493 | 493 | 0 |
| pedidos | 7.297 | 7.297 | 0 |
| detalle_pedido | 11.879 | 11.879 | 0 |

**¿Por qué 0 filas nuevas?** La limpieza de la S4 ya recuperaba con `total_linea` las 135
cantidades nulas y los 262 precios nulos, así que ya no se eliminaba ninguna de esas filas.
Con los datos de ahora, el precio de catálogo se usa 0 veces. Es un respaldo para cuando
`total_linea` no cuadre. Se probó con un caso artificial con los tres caminos:

- precio recuperado con `total_linea`;
- precio de catálogo cuando faltan las dos columnas, y después la cantidad recalculada con ese precio;
- fila eliminada porque la cantidad no sale entera.

**¿Dónde se pierden filas de verdad?** El nuevo apartado del informe lo deja claro:

| Tabla | Casos recuperados | Casos eliminados | % recuperado |
|---|---:|---:|---:|
| clientes | 44 | 15 | 74,6 % |
| pedidos | 394 | 677 | 36,8 % |
| detalle_pedido | 849 | 1.344 | 38,7 % |

Las pérdidas de `detalle_pedido` son casi todas **líneas huérfanas** (985): pertenecen a pedidos
eliminados porque no tienen cliente o tienen la fecha nula o imposible. Eso no se puede recuperar
sin inventar datos.

### Verificaciones de la S4 (vueltas a pasar)

| Comprobación | Resultado |
|---|---|
| `generar_datos.py` y `limpieza.py` | Sin errores |
| Pedidos sin cliente / líneas sin pedido / líneas sin producto | 0 / 0 / 0 |
| Emails repetidos, fechas inválidas, `PRAGMA foreign_key_check` | 0 |
| Anomalías de `_verdad_anomalias.csv` en la BD | 79 / 79 (100 %) |
| Dos ejecuciones seguidas | Huella MD5 idéntica |

## 1. `src/bd.py`: el módulo de acceso a datos

| Elemento | Qué hace |
|---|---|
| `RAIZ`, `RUTA_BD` | Rutas calculadas desde el propio archivo, como en el resto de scripts |
| `leer_sql(consulta, params=None)` | Abre la conexión, ejecuta la consulta con `pd.read_sql_query`, devuelve un DataFrame y **cierra la conexión** |
| `ventas_por_linea()` | JOIN de 5 tablas: una fila por línea de pedido, con `importe` y las fechas ya en `datetime` |

Detalles para estudiar:

- **`closing()`**: el `with sqlite3.connect(...)` de Python **no cierra** la conexión, solo
  confirma la transacción. `contextlib.closing` sí la cierra, aunque haya un error. En Windows,
  una conexión abierta puede bloquear el archivo `.db`.
- **`params` y los `?`**: `leer_sql("... WHERE estado = ?", ["completado"])`. Es más seguro que
  meter el valor en el texto con un f-string (evita problemas de comillas y la inyección SQL).
- **El `importe` se calcula en SQL** (`d.cantidad * d.precio_unitario AS importe`), y la consulta
  usa alias cortos (`d`, `p`, `pr`, `ca`, `c`) con comentarios por bloque.
- `ventas_por_linea()` devuelve **todos** los estados. Para ventas efectivas hay que filtrar
  `estado == "completado"`.
- Si la BD no existe, lanza un error que dice qué comandos ejecutar.

## 2. El notebook, sección a sección

**Criterio común:** los ingresos solo cuentan pedidos `completado`. Un pedido cancelado o devuelto
no es dinero que se quede la tienda. La excepción es la sección 6, que mide precisamente los
estados.

| Sección | Consulta SQL | Gráfico | Por qué ese gráfico |
|---|---|---|---|
| 1. Vista general | `COUNT(*)` por tabla con `UNION ALL`; `MIN/MAX` de fechas con subconsultas | Tablas | Son pocos números: una tabla se lee mejor |
| 2. Ventas en el tiempo | `strftime('%Y-%m', fecha)` + `GROUP BY mes`; `SUM(inversion)` por mes; pedidos > 5.000 € con `HAVING` | Línea (ingresos) y barras (inversión), alineados | La línea muestra la tendencia. **Dos gráficos y no eje doble**: con dos escalas en el mismo gráfico se puede hacer que cualquier par de series "parezca" relacionado |
| 3. Productos y categorías | JOIN detalle + pedidos + productos + categorias, `GROUP BY` producto o categoría | Barras horizontales; curva de Pareto | Los nombres largos se leen en el eje Y; la curva acumulada muestra de un vistazo cuántos productos llegan al 80 % |
| 4. Pedidos | `GROUP BY p.id_pedido` con `COUNT(*)` (líneas) y `SUM(importe)` | Histograma (hasta el percentil 99) con media y mediana; barras de líneas en escala logarítmica | El histograma muestra la forma de la distribución. Se corta en el p99 para que la cola no aplaste el resto, y la escala log permite ver los pocos pedidos de 8 o más líneas |
| 5. Clientes | `LEFT JOIN` clientes → pedidos → detalle, con el filtro del estado **en el `ON`** | Histograma, barras por ciudad, dispersión | La dispersión es la forma natural de buscar grupos entre dos variables numéricas |
| 6. Estados y pago | `COUNT(*)` y `%` con una subconsulta para el total | Barras con el % encima | Comparar pocas categorías: barras mejor que tarta |
| 7. Publicidad | Dos CTE (`WITH`): campañas con `CASE WHEN` para pasar los canales a columnas, y ventas por mes; `LEFT JOIN` por mes | Mapa de calor y `regplot` | El mapa de calor resume todas las correlaciones; el `regplot` es la "foto" de la regresión de la S6 |

Tres trucos de SQL que aparecen:

- **`LEFT JOIN` con la condición en el `ON`** (sección 5). Si `p.estado = 'completado'` fuera en
  el `WHERE`, desaparecerían los clientes sin pedidos completados. En el `ON` se conservan,
  con 0 pedidos.
- **`HAVING`** (sección 2) filtra después de agrupar. `WHERE` no puede usar `SUM(...)` porque
  filtra antes.
- **`CASE WHEN` dentro de `SUM`** (sección 7) convierte filas en columnas: es un "pivot" en SQL.

Colores: un solo azul para las series de ventas y naranja para la publicidad. En el mapa de
calor, una paleta divergente (azul negativo, blanco 0, rojo positivo) con la escala fija de −1 a 1.

## 3. Qué hemos descubierto (números del notebook)

1. **Ventas:** 883.361 € en 24 meses (noviembre de 2024 a octubre de 2026), con 6.541 pedidos
   completados. Ticket medio de 135,05 € y mediano de 82,78 €.
2. **Estacionalidad:** noviembre y diciembre venden de media 49.169 €, un 43,2 % más que el resto
   de meses (34.334 €).
3. **Publicidad:** la correlación entre la inversión mensual y los ingresos es 0,80 (0,84 con los
   pedidos), y sigue siendo 0,80 sin noviembre ni diciembre. Google Ads es el canal más relacionado
   con los ingresos (0,76); Meta Ads 0,45 y email 0,39.
4. **Producto:** Electrónica genera el 36,0 % de los ingresos. No hay un Pareto fuerte: hacen falta
   33 de 60 productos (55,0 %) para llegar al 80 %.
5. **Clientes:** el 10 % que más gasta aporta el 41,9 % de los ingresos. Hay 123 clientes con
   1–3 pedidos y 60 con 30 o más.
6. **Pedidos raros:** 25 pedidos tienen de 8 a 12 líneas (lo normal es de 1 a 4 y no hay ninguno
   de 5 a 7), y el más caro llega a 11.730,42 €. Un único pedido de 10.389,60 € explica el pico
   de junio de 2026.
7. **Estados:** el 10,4 % de los pedidos no deja ingresos (5,4 % cancelados y 5,0 % devueltos).

Cómo se ha comprobado que los números son reales: un script recorre las celdas de conclusiones,
extrae cada número y comprueba que aparece en alguna salida del notebook. Resultado: todos
aparecen. Para que eso fuera posible, la matriz de correlaciones también se muestra como tabla
(antes solo estaba dentro de la imagen) y las cuotas se muestran en %.

## 4. Relación con las semanas siguientes

| Semana | Qué hemos preparado aquí |
|---|---|
| S6 · Regresión lineal | La tabla mensual de la sección 7 ya es el dataset: `inversion_total` (o por canal) → `ingresos`. Hay que tener cuidado con la estacionalidad y con los meses inflados por un solo pedido enorme (2024-11, 2026-06) |
| S7 · K-Means (RFM) | La dispersión de la sección 5 sugiere clientes de pocas compras frente a clientes que repiten mucho. La consulta de clientes es la base de la frecuencia (F) y del valor monetario (M) |
| S8 · Isolation Forest | Ya hemos visto anomalías a simple vista: pedidos de 8 o más líneas, líneas de 48–54 unidades y clientes con un gasto por pedido muy alto. El modelo tendrá que encontrarlas sin que se lo digamos |

## 5. Decisiones que he tomado yo (por ambigüedad)

1. **Ingresos = solo pedidos completados**, en todas las secciones salvo la 6.
2. **Ventas e inversión en dos gráficos alineados** en lugar de un eje doble (las dos opciones
   estaban permitidas; el eje doble induce a error con facilidad).
3. **En la sección 7, `pedidos` también cuenta solo los completados**, para que sea coherente con
   `ingresos`. Si en la S6 queremos el total, basta con quitar el `WHERE`.
4. **Histograma del importe cortado en el percentil 99**, para que se vea la forma. Los 66 pedidos
   por encima se indican en el texto.
5. **Escala logarítmica en las líneas por pedido**: sin ella, las barras de 8 a 12 líneas
   (4–7 pedidos cada una) no se verían.
6. **He añadido una tabla de pedidos de más de 5.000 €** a la sección 2, que no se pedía,
   porque explica los dos picos de ventas que no son de temporada.
7. **El notebook se escribe y ejecuta con `jupyter nbconvert`** desde la carpeta `notebooks/`. La
   ruta a `src` se calcula con `Path.cwd().parent`. Si lo abres en PyCharm o Jupyter, ábrelo desde
   esa carpeta (es lo normal).
8. **Las imágenes de `docs/img/` sí se suben a git**: son documentación, no datos. Los CSV y la
   BD siguen fuera del repositorio.
