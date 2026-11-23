# Explicación S7: segmentación de clientes (RFM + K-Means)

**Pregunta de negocio 2:** ¿qué tipos de clientes hay?

**Respuesta corta:** hay **4 tipos de clientes**:

| Segmento | Clientes | % clientes | % ingresos | Recencia (mediana) | Pedidos (mediana) | Gasto (mediana) |
|---|---:|---:|---:|---:|---:|---:|
| **Fieles** | 127 | 26,8 % | 66,4 % | 14 días | 28 | 3.737,7 € |
| **Habituales** | 204 | 43,0 % | 24,2 % | 42 días | 7 | 878,4 € |
| **Compra única** | 74 | 15,6 % | 1,1 % | 292 días | 1 | 109,3 € |
| **Perdidos** | 69 | 14,6 % | 8,3 % | 580 días | 4 | 550,7 € |

Un cuarto de los clientes (los Fieles) genera dos tercios de los ingresos. Lo que separa a los
segmentos es **cuántas veces compran y cuándo fue la última vez**, no cuánto gastan por pedido.

Archivos nuevos o cambiados:

| Archivo | Qué es |
|---|---|
| `src/features.py` | `tabla_rfm()`, `fecha_corte()` y `clientes_sin_compras()`. `tabla_mensual()` no cambia |
| `notebooks/03_segmentacion.ipynb` | Transformaciones, elección de k, perfiles, gráficos, comparación de algoritmos, sensibilidad y evaluación |
| `models/segmentacion_kmeans.joblib` | El pipeline final, los nombres de las variables y de los segmentos, `fecha_corte` y `datos_hasta` |
| `data/processed/segmentos_clientes.csv` | `id_cliente`, `segmento`, `nombre_segmento` para el Power BI de la S10 (no se sube a git, como el resto de `data/`) |
| `docs/img/segmentacion_*.png` | 7 gráficos |

## 1. Qué es RFM

RFM resume a cada cliente con tres números:

- **R · Recencia:** días desde su último pedido completado. **Menos es mejor** (compró hace poco).
- **F · Frecuencia:** número de pedidos completados.
- **M · Monetario:** gasto total en pedidos completados (€).

Es el método clásico de marketing porque responde a tres preguntas de negocio: ¿sigue activo?,
¿repite?, ¿cuánto vale? Además, `tabla_rfm()` calcula `antiguedad_dias` (días desde el alta) y
`ticket_medio` (gasto ÷ pedidos), que se usan para describir los segmentos.

### `tabla_rfm()`: la consulta SQL

Tres CTE (`WITH`), como en la S6:

1. **`corte`**: la fecha de corte, `date(MAX(fecha_pedido), '+1 day')`.
2. **`pedido_completado`**: importe de cada pedido completado, con su cliente y su fecha.
3. **`por_cliente`**: `MAX(fecha_pedido)` (último pedido), `COUNT(*)` (F) y `SUM(importe)` (M).

Al final se une con `clientes` y se calculan los días con `julianday()`, que convierte una fecha en
un número de días; restando dos se obtienen los días entre ellas.

**Fecha de corte = 2026-11-01**, el día siguiente al último pedido de la BD (2026-10-31). Es el
"hoy" del análisis. Se usa el día siguiente para que quien compró el último día tenga recencia 1 y no
0. **No se usa la fecha real de hoy**: los datos son de un periodo cerrado, y con `date('now')` la
recencia de todos crecería cada día y el resultado no sería reproducible. La fecha se guarda en
`tabla.attrs["fecha_corte"]` y en el `.joblib`.

**Clientes sin ningún pedido completado: 19** (15 sin pedidos y 4 con solo pedidos cancelados o
devueltos). **Se excluyen del K-Means** porque no tienen recencia ni gasto: habría que inventarles
valores (recencia "infinita", gasto 0), y formarían un grupo artificial que distorsionaría las
distancias. Se tratan aparte: `clientes_sin_compras()` los devuelve, y en el CSV aparecen con
`segmento = -1` y `nombre_segmento = "Sin compras completadas"`, para que el Power BI tenga a los 493.

## 2. Por qué log y estandarización

K-Means agrupa por **distancias** (euclídeas). Dos cosas lo estropean:

1. **Asimetría.** Frecuencia (asimetría de 2,71) y monetario (2,76) tienen una cola larga: la
   mayoría de los clientes tiene pocos pedidos y unos pocos tienen muchísimos (hasta 115 pedidos y
   16.635,9 €). Esos pocos quedan tan lejos que K-Means "gasta" grupos en ellos.
   **`np.log1p(x) = log(1 + x)`** comprime la cola (10 → 2,4; 100 → 4,6; 10.000 → 9,2) y no falla
   con 0. Después del log, la asimetría baja a 0,33 y −0,51.
2. **Escala.** Recencia va hasta 703 días y monetario hasta 16.635,9 €. Sin igualar escalas, las
   diferencias en euros serían enormes comparadas con las de días y pedidos, y el gasto decidiría
   solo. **`StandardScaler`** deja cada variable con media 0 y desviación 1. Es lo mismo que en
   Iris, donde había que escalar las medidas antes de K-Means o KNN.

**El orden importa:** primero log y después estandarización. Estandarizar no quita la asimetría:
solo cambia las unidades. La sección 7 del notebook lo demuestra.

### El pipeline

```
ColumnTransformer(FunctionTransformer(np.log1p) sobre frecuencia y monetario; recencia sin tocar)
  → StandardScaler → KMeans(n_clusters=4, n_init=10, random_state=42)
```

El `FunctionTransformer(log1p)` va dentro de un `ColumnTransformer` porque el log solo se aplica a
frecuencia y monetario, como pedía el enunciado. Se usa `np.log1p` directamente, y no una función
propia del notebook, porque una función definida en el notebook no se puede cargar desde otro
programa (`joblib` guarda solo su nombre, y fuera del notebook no existe).

### ¿Añadir la antigüedad?

No. Con `antiguedad_dias`, la silueta empeora para casi todos los k (con k = 4: 0,372 frente a 0,439)
y Davies-Bouldin también (0,899 frente a 0,800). Solo mejora en k = 8. La antigüedad está repartida
de forma bastante uniforme y "diluye" las distancias de las variables que sí separan.

## 3. Cómo leer el codo, la silueta y Davies-Bouldin

| Métrica | Qué mide | Cómo se lee | En estos datos |
|---|---|---|---|
| **Inercia (codo)** | Suma de distancias² de cada cliente a su centroide | Siempre baja al añadir grupos. Se busca el "codo": el k a partir del cual baja poco | Cae un 35,6 % de 2 a 3, un 29,4 % de 3 a 4 y un 22,3 % de 4 a 5. Codo en 3–4 |
| **Silueta media** | Para cada cliente: (b − a) / máx(a, b), con a = distancia media a su grupo y b = distancia media al grupo vecino | De −1 a 1. Cerca de 1: grupos compactos y separados. Cerca de 0: grupos que se tocan. Negativo: cliente en el grupo equivocado | 0,458 (k = 2), 0,428 (k = 3), **0,439 (k = 4)**, 0,396 (k = 5) |
| **Davies-Bouldin** | Media, para cada grupo, de (dispersión propia + dispersión del vecino) ÷ distancia entre centros | ≥ 0, **más bajo es mejor** | Mínimo en **k = 4 (0,800)** |

**Elegido: k = 4.** Davies-Bouldin es mínimo en 4, la silueta de 4 está casi a la altura de la de
2 y por encima de la de 3, y el codo está en 3–4. Para el negocio, k = 2 solo diría "buenos y
malos" clientes; k = 4 da cuatro grupos con acciones distintas, y el más pequeño tiene 69 clientes.
**No se forzó k = 3** (los 3 tipos del generador): k se eligió sin mirar la verdad.

Una silueta de 0,44 es "estructura razonable", no "grupos clarísimos". Tiene sentido: en el PCA se
ve que los clientes forman un continuo, sin huecos entre los grupos.

## 4. Los segmentos y sus nombres

Los nombres se ponen con reglas escritas en el código (`nombrar_segmentos`), a partir de las
medianas, no a mano ni mirando la verdad:

1. El de mayor gasto mediano → **Fieles**.
2. De los demás, el de compra más reciente → **Habituales**.
3. De los dos restantes, el de menos pedidos → **Compra única**; el otro → **Perdidos**.

| Segmento | Quiénes son | Acciones |
|---|---|---|
| **Fieles** | Compran mucho (28 pedidos) y hace poco (14 días) | Programa de fidelización; aviso si uno lleva meses sin comprar |
| **Habituales** | Activos (42 días) pero con menos pedidos (7) | Venta cruzada y cupón por volumen para subir la frecuencia |
| **Compra única** | 1 pedido pequeño (65,6 € de ticket) hace 292 días | Email de "segunda compra" con descuento pequeño; encuesta |
| **Perdidos** | Compraron varias veces (4), pero hace 580 días | Reactivación solo de los que más gastaron; dejar de insistir si no responden |

El ticket medio es casi igual en Fieles, Habituales y Perdidos (126,7–133,9 €): la diferencia es de
frecuencia y recencia.

## 5. Qué es PCA y qué significa la varianza explicada

**PCA (análisis de componentes principales)** busca nuevas direcciones (componentes) que sean
combinaciones de las variables originales y recojan la mayor variación posible: la primera, la
máxima; la segunda, la máxima de lo que queda. Sirve para **dibujar en 2D** datos de más dimensiones.

La **varianza explicada** dice cuánta información se conserva. Aquí: **componente 1 = 73,9 %**,
**componente 2 = 23,1 %**, en total **97,0 %**. El dibujo en 2D es casi fiel a los datos en 3D.

- **Componente 1** ≈ frecuencia (0,63) + monetario (0,63) − recencia (0,45): el **valor del
  cliente**. A la derecha, Fieles; a la izquierda, Compra única.
- **Componente 2** ≈ recencia (0,89): arriba, los que hace mucho que no compran (Perdidos).

PCA **no** se usa para agrupar: K-Means trabaja con las 3 variables. PCA solo sirve para el gráfico.

## 6. K-Means frente a jerárquico y DBSCAN

| Método | Grupos | Ruido | Silueta | ARI con K-Means |
|---|---:|---:|---:|---:|
| **K-Means** | 4 | 0 | **0,439** | 1 |
| Jerárquico (ward) | 4 | 0 | 0,412 | 0,481 |
| DBSCAN (eps = 0,554, min_samples = 6) | 1 | 10 (2,1 %) | no calculable | 0,012 |

- **Jerárquico (ward):** une en cada paso los dos grupos que menos aumentan la varianza interna. El
  dendrograma muestra los mayores saltos entre 2 y 3 grupos (uniones a 36,7, 23,5 y 14,9). Cortado
  en 4, junta a los Fieles con 75 Habituales y parte en tres a Compra única.
- **DBSCAN:** `min_samples = 6` (2 × nº de variables, la regla habitual). eps sale del **gráfico de
  k-distancias**: para cada cliente, la distancia a su 6.º vecino, ordenadas de menor a mayor. Donde
  la curva se dispara empiezan los puntos aislados. El codo (el punto más alejado de la recta entre
  el primero y el último, con los ejes normalizados) da **eps = 0,554**. Resultado: **1 solo grupo y
  10 clientes de ruido**. Con eps = 0,416 salen 7 grupos, pero con el 13,3 % de ruido.

**Por qué K-Means aquí:** los clientes forman un continuo sin zonas densas separadas por huecos, que
es lo que DBSCAN necesita. No hay formas raras (para eso sirve DBSCAN) ni una jerarquía clara (para
eso sirve el jerárquico). K-Means tiene la mejor silueta, grupos fáciles de explicar y `predict` para
clientes nuevos (`AgglomerativeClustering` no lo tiene). Como en el ejercicio de clase: K-Means
encaja con grupos "redondeados"; aquí los grupos son trozos de un continuo, y K-Means los corta de
forma estable. DBSCAN sí aporta algo: sus 10 puntos de ruido son clientes atípicos (S8).

## 7. Qué mide el Adjusted Rand Index (ARI)

Compara dos agrupaciones de los mismos clientes, **sin importar el número o el nombre de cada
grupo**. Mira cada pareja de clientes: ¿las dos agrupaciones coinciden en ponerlos juntos o
separados? Y corrige por lo que coincidiría por puro azar.

- **1** = las dos agrupaciones son idénticas (aunque los grupos se llamen distinto).
- **0** = coinciden lo mismo que dos agrupaciones al azar.
- Puede ser algo negativo (peor que el azar).

Se usa dos veces: para comparar métodos entre sí (sección 6) y para comparar con la verdad (sección 9).

## 8. Sensibilidad: sin log

Mismo K-Means con k = 4, sin `log1p`:

- Los segmentos cambian mucho (ARI 0,503 con el modelo con log).
- Aparece un grupo de **solo 10 clientes** (87,5 pedidos y 11.959,6 € de mediana, 13,5 % de los
  ingresos), y los 127 Fieles se reparten en 3 grupos.
- **Por qué domina el volumen de compra:** sin log, el cliente más extremo está a 6,13 desviaciones
  típicas en monetario y a 5,89 en frecuencia (2,67 en recencia). K-Means minimiza distancias²: le
  compensa dedicar un grupo a esos pocos clientes. Con log, los máximos bajan a 2,16 y 2,65.
- Los segmentos explican el 76,9 % de la varianza de monetario sin log, frente al 49,6 % con log.
- La silueta sin log es más alta (0,577), pero **no es comparable** con la de 0,439: cada una se mide
  en su propio espacio de variables.

## 9. Evaluación con la verdad (solo porque los datos son simulados)

El generador dio a cada cliente un tipo oculto. **Solo la sección 9 del notebook lo lee** (comprobado
con una búsqueda en el notebook y en `src/`). Los 474 clientes analizados son 237 ocasionales, 150
puntuales y 87 fieles.

| | Coincidencia (tipo mayoritario de cada segmento) | ARI con la verdad |
|---|---:|---:|
| **K-Means con log (final)** | **79,1 %** | **0,405** |
| K-Means sin log | 81,4 % | 0,490 |

- **Fieles** → fiel (74 de 127). **Habituales** → ocasional (173 de 204). **Compra única** → puntual
  (59 de 74). **Perdidos** → puntual (**69 de 69**).
- Los puntuales salen en dos segmentos: los de 1 pedido (Compra única) y los que compraron varias
  veces en su primer mes (Perdidos: 4 pedidos de mediana en ese mes y 0 después).

**Errores (99 de 474) y por qué:**

1. **50 ocasionales en Fieles.** Clientes antiguos (678 días de antigüedad) que han acumulado 20,5
   pedidos a un ritmo de 0,74 al mes, frente a 2,19 de los fieles de verdad. **La frecuencia de RFM
   es acumulada**: no distingue "mucho tiempo comprando poco" de "poco tiempo comprando mucho".
2. **12 fieles en Habituales.** Lo contrario: recientes (141,5 días), con un ritmo alto (1,58 al mes),
   pero aún con pocos pedidos acumulados (10).
3. **19 puntuales en Habituales.** Compraron en su primer mes (3 pedidos) y luego 1 vez más, y esa
   compra suelta les da una recencia de 161 días que parece de cliente activo. Son más recientes que
   los Perdidos (242 días de antigüedad frente a 593), pero no recién llegados: solo 1 puntual se dio
   de alta en los últimos 90 días. **La hipótesis de "puntuales dados de alta hace poco" se cumple
   solo en parte**: pesa más la compra suelta tardía.
4. **14 ocasionales en Compra única:** con 2 pedidos, en RFM no se distinguen de un puntual.

**Sin log coincide algo más con la verdad**, pero el modelo se eligió antes y sin ella, y así se
queda. En una empresa real esta sección no existe: solo se puede validar con métricas internas, con
la estabilidad y viendo si las acciones por segmento funcionan.

## 10. Si en una entrevista te preguntan "¿cómo segmentaste a los clientes?"

> "Calculé para cada cliente su RFM en SQL: días desde su último pedido, número de pedidos y gasto
> total, con una fecha de corte fija para que fuera reproducible. Frecuencia y gasto tenían mucha
> asimetría, así que les apliqué un logaritmo y después estandaricé las tres variables, porque
> K-Means trabaja con distancias. Todo va en un pipeline de scikit-learn. Para elegir k miré el
> codo, la silueta y Davies-Bouldin de 2 a 10. Me quedé con 4, que tiene el mejor Davies-Bouldin y
> casi la mejor silueta, y además da grupos accionables: fieles, que son el 27 % de los clientes y el
> 66 % de los ingresos; habituales; clientes de una sola compra, y clientes perdidos. Lo comparé con
> un clustering jerárquico y con DBSCAN. DBSCAN solo encontraba un grupo, lo que confirma que los
> clientes son un continuo y que tiene sentido cortarlo con K-Means. También comprobé que sin el
> logaritmo un puñado de clientes enormes se llevaba un grupo entero. Como los datos eran simulados,
> al final pude compararlo con el tipo real de cada cliente: coincide en un 79 %. El error principal
> es que la frecuencia es acumulada y algunos clientes antiguos de compra ocasional parecen fieles.
> Como mejora usaría el ritmo de compra, pedidos por mes, en lugar del total."

## 11. Decisiones que he tomado yo (por ambigüedad)

1. **Fecha de corte = día siguiente al último pedido de cualquier estado** (2026-10-31 → 2026-11-01).
2. **Clientes sin pedidos completados fuera del K-Means** (19), pero dentro del CSV con
   `segmento = -1` ("Sin compras completadas"), para que el Power BI tenga a todos.
3. **`antiguedad_dias` y `ticket_medio` en `tabla_rfm()` pero no en el modelo:** la antigüedad
   empeora la separación, y el ticket ya está dentro de M ÷ F.
4. **Recencia sin log,** como pedía el enunciado (asimetría de 1,29, la menor de las tres).
5. **El log va en un `ColumnTransformer`** con `np.log1p`, para que el `.joblib` se cargue fuera del
   notebook (sección 2).
6. **k = 4** con las métricas y el negocio, sin mirar la verdad.
7. **Nombres por reglas** escritas en código a partir de las medianas, con `assert` que comprueban
   que encajan con el perfil.
8. **Jerárquico cortado en el mismo k = 4,** para compararlo con K-Means en igualdad de condiciones.
9. **eps de DBSCAN con un método automático** (el punto de la curva más alejado de la recta entre el
   primero y el último, con ejes normalizados) en lugar de elegirlo a ojo. Se muestra cómo cambia con
   otros eps.
10. **Silueta de DBSCAN sin los puntos de ruido;** con 1 solo grupo no se puede calcular.
11. **Modelo final con log, aunque sin log coincide algo más con la verdad.** Cambiarlo por eso sería
    usar la verdad para elegir, que está prohibido. Queda como lección: el problema de fondo es la
    frecuencia acumulada.
12. **En el `.joblib`, `datos_hasta` = 2026-10-31** (último día con pedidos) y además `fecha_corte`
    (2026-11-01), que hace falta para calcular la recencia de clientes nuevos con el mismo criterio.
13. **El dendrograma en un solo color** (azul por debajo del corte y gris por encima): los colores de
    los segmentos se reservan para K-Means, y así no parece que los grupos del jerárquico sean los
    mismos.
14. **En la evaluación, el análisis de errores añade los pedidos del primer mes tras el alta**
    (consulta SQL solo en la sección 9). Es lo que permite ver que el problema es la frecuencia
    acumulada.

## 12. Verificaciones

| Comprobación | Resultado |
|---|---|
| `generar_datos.py`, `limpieza.py` y los notebooks 01, 02 y 03 de cero con `nbconvert --execute --inplace` | Sin errores |
| `_verdad_clientes.csv` en el código | Solo en la sección 9 del notebook 03 (y en `generar_datos.py`, que lo escribe) |
| Números de las celdas de conclusión | Todos aparecen en las salidas (comprobado con un script que los extrae y los busca) |
| Hash de los 7 `segmentacion_*.png`, el `.joblib` y el CSV en dos ejecuciones | Idéntico |
| `tabla_mensual()` (los dos criterios) | Idéntica a antes de la S7, `attrs` incluidos |
| El `.joblib` se carga en otro proceso y asigna los mismos segmentos | Sí (`assert` en el notebook) |
