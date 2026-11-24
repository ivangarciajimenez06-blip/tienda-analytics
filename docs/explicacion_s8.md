# Explicación S8: detección de pedidos anómalos (Isolation Forest)

**Pregunta de negocio 3:** ¿qué pedidos son sospechosos?

**Respuesta corta:** los pedidos con **muchas unidades de un mismo producto**, con **muchas líneas** o
con un **precio lejos del de catálogo**. Isolation Forest da a cada pedido una puntuación de sospecha y
un motivo en palabras. Con la capacidad del equipo (50 revisiones al mes) se marcan **1.200 pedidos**
(16,45 %), ordenados de más a menos sospechoso. **De los 50 primeros, 43 son anomalías reales.**

| | IQR (una variable cada vez) | Isolation Forest (umbral de capacidad) |
|---|---:|---:|
| Pedidos marcados | 1.298 | 1.200 |
| Anomalías encontradas (de 79) | 62 | **73** |
| Precision | 4,8 % | **6,1 %** |
| Recall | 78,5 % | **92,4 %** |
| F1 | 0,090 | **0,114** |
| ROC-AUC / PR-AUC | — (no da puntuación) | **0,968 / 0,762** |
| Precision@50 | — | **86,0 %** |

Archivos nuevos o cambiados:

| Archivo | Qué es |
|---|---|
| `src/features.py` | `tabla_pedidos()`. `tabla_mensual()` y `tabla_rfm()` no cambian (comprobado: mismo resultado exacto) |
| `notebooks/04_anomalias.ipynb` | IQR, Isolation Forest, umbral, motivo de cada alerta, gráficos, estabilidad, evaluación y ablación |
| `models/anomalias_iforest.joblib` | El pipeline, las variables, el umbral, la referencia para el motivo y `datos_hasta` |
| `data/processed/pedidos_sospechosos.csv` | `id_pedido`, `puntuacion`, `ranking`, `marcado`, `motivo_principal` para el Power BI de la S10 (no se sube a git, como el resto de `data/`) |
| `docs/img/anomalias_*.png` | 8 gráficos |

## 1. Las variables: `tabla_pedidos()`

Una fila por pedido (**todos los estados**: un pedido cancelado también puede ser un intento de fraude).
La consulta SQL tiene dos CTE:

1. **`linea`**: cada línea con su importe y su **ratio de precio** = `precio_unitario / precio de catálogo`.
   Un ratio de 1 es "vendido al precio de catálogo"; 5 es cinco veces más caro y 0,1 es un 90 % más
   barato. Al dividir, el ratio no depende de si el producto es caro o barato: un auricular de 200 € y
   un libro de 10 € se comparan en la misma escala.
2. **`por_pedido`**: `SUM` del importe y de las unidades, `COUNT(*)` de líneas, `MAX` de la cantidad, y
   **el máximo y el mínimo del ratio**. No la media: basta **una** línea con un precio raro para que el
   pedido sea sospechoso, y con la media esa línea se diluiría entre las normales.

Al final se calcula `importe_por_unidad = importe_total / unidades_totales` y se añaden `estado`,
`metodo_pago`, `fecha_pedido` e `id_cliente` para mostrar (no entran en el modelo).

Lo que se ve en los datos (sección 0 del notebook): todas las variables tienen cola larga a la derecha
(asimetría de 3,05 a 44,91). Los ratios valen 1 en casi todos los pedidos: **solo 27 (0,37 %)** tienen
alguna línea a un precio distinto del de catálogo (8 por encima y 19 por debajo).

## 2. Por qué no basta con IQR

IQR marca un pedido si **alguna** variable supera Q3 + 1,5·IQR. Marca **1.298 pedidos (17,8 %)**, y
tiene tres problemas:

1. **Si Q1 y Q3 están juntos, el límite es demasiado bajo.** En líneas y en unidades por línea, Q1 = 1 y
   Q3 = 2, así que el límite es 3,5: un pedido de 4 líneas ya es "outlier" (380 pedidos). El 95,2 % de
   los marcados no se sale del percentil 99 en líneas ni en unidades por línea y tiene el precio de
   catálogo.
2. **Solo mira hacia arriba.** Ninguno de los 19 pedidos con precio por debajo del catálogo se marca por
   el ratio.
3. **Cada variable por separado.** No ve combinaciones: 4 líneas de productos caros es más raro que 4
   líneas baratas, pero para IQR son iguales.

## 3. Cómo funciona Isolation Forest

### La idea

Un árbol de aislamiento elige **una variable al azar** y **un corte al azar** entre su mínimo y su máximo.
Repite con cada trozo hasta que cada punto queda solo. Un punto raro está lejos de los demás, así que un
corte al azar lo separa pronto: **las anomalías se aíslan con pocos cortes**. Un punto normal está
rodeado de otros parecidos y necesita muchos.

Un árbol es muy aleatorio, así que se hacen muchos (aquí 300) y se promedia el número de cortes de cada
punto: **h(x)**. Cada árbol se entrena con 256 pedidos al azar, el valor habitual.

### La conexión con el ejercicio de clase (puntos A–E)

En clase hicimos árboles a mano con 5 puntos y calculamos:

```
s(x, n) = 2 ^ ( -E[h(x)] / c(n) )        c(n) = 2·H(n-1) - 2(n-1)/n,   H(i) ≈ ln(i) + 0,5772
```

- **c(n)** es el número medio de cortes para aislar un punto cualquiera en un árbol de n puntos. Sirve
  para normalizar: con 5 puntos, 2 cortes es poco; con 256, 2 cortes es poquísimo.
- h(x) mucho menor que c(n) → **s cerca de 1** → anomalía. h(x) ≈ c(n) → **s ≈ 0,5** → normal.
- **Umbral de clase: s > 0,5.**

El notebook repite el ejercicio con 5 puntos (A–D juntos entre 1 y 2,5, y E en 9) y calcula s a mano
recorriendo los 300 árboles de scikit-learn:

| Punto | x | h(x) medio | s | ¿Anomalía? |
|---|---:|---:|---:|---|
| A | 1,0 | 2,630 | 0,4569 | No |
| B | 1,5 | 3,333 | 0,3705 | No |
| C | 2,0 | 3,403 | 0,3629 | No |
| D | 2,5 | 2,870 | 0,4253 | No |
| **E** | **9,0** | **1,207** | **0,6981** | **Sí** |

Con c(5) = 2,327. E se aísla con la mitad de cortes que un punto cualquiera. (Los valores de A–E son un
ejemplo con la misma forma que el de clase. Si en clase usaste otros, se cambian en la celda.)

Un detalle que en clase no aparecía: los árboles de scikit-learn se paran a una profundidad de log2(n).
Si en una hoja quedan varios puntos juntos, a su h(x) se le suma c(puntos de la hoja), que estima los
cortes que faltarían.

### La relación con scikit-learn

El notebook comprueba con `assert` que s calculada a mano coincide con scikit-learn:

| scikit-learn | Es... | Cómo se lee |
|---|---|---|
| `score_samples(X)` | **−s** | Cambia el signo: "más bajo = más raro" (convenio de sklearn) |
| `decision_function(X)` | −s − `offset_` | Con `contamination="auto"`, `offset_` = −0,5, así que es 0,5 − s: negativo ⇔ s > 0,5 |
| `predict(X)` | −1 si s > 0,5 | El umbral de 0,5 de clase |

En el notebook, la **puntuación = −`score_samples`**, es decir, la s de clase: más alta = más sospechoso.

### El pipeline

```
ColumnTransformer(log1p en importe, líneas, unidades, máx. por línea e importe por unidad;
                  log en los dos ratios de precio)
  → StandardScaler → IsolationForest(n_estimators=300, random_state=42)
```

- **Por qué el log.** Los cortes son al azar entre el mínimo y el máximo. Sin log, en una variable como
  las unidades (de 1 a 59) casi todos los cortes caen en la zona vacía de la cola y casi ninguno separa
  1, 2 o 5 unidades. Con `log1p` el rango se reparte mejor.
- **Por qué `log` (sin +1) en los ratios.** Un ratio es una multiplicación: ×10 y ×0,1 son igual de raros.
  En escala normal, ×0,1 está a 0,9 de 1 y ×10 está a 9, así que casi ningún corte caería entre 0,1 y 1.
  Con el log, log(10) = 2,3 y log(0,1) = −2,3: **simétricos**. El ratio es siempre > 0 (el esquema obliga
  a precio > 0), así que `log` no falla.
- **El `StandardScaler` no hace falta.** Cada corte mira una sola variable, entre su mínimo y su máximo:
  cambiar la escala mueve los cortes en la misma proporción y los árboles separan los mismos pedidos.
  Comprobado: **la diferencia de puntuación con y sin él es 0**. Se deja porque no cambia nada y prepara
  los datos para el PCA, que sí lo necesita. (K-Means y KNN, en cambio, usan distancias y sí lo necesitan.)

## 4. El umbral: un criterio de negocio

El modelo ordena los pedidos, pero **no dice dónde cortar**. Y el histograma de puntuaciones no tiene
ningún hueco entre normales y raros: la cola baja de forma gradual. El corte lo tiene que poner el negocio.

**Criterio:** el equipo puede revisar **50 pedidos al mes**. Llegan 304,0 pedidos al mes de media, así que
se puede revisar el 50 / 304,0 = **16,45 %**. El umbral es la puntuación que deja por encima ese
porcentaje: **s ≥ 0,529 → 1.200 pedidos**.

| Umbral | Pedidos marcados | Al mes (media) | Meses por encima de 50 |
|---|---:|---:|---:|
| **Capacidad (elegido)**: s ≥ 0,529 | 1.200 (16,45 %) | 50,0 | 11 de 24 |
| `contamination="auto"`: s > 0,5 | 1.710 (23,43 %) | 71,2 | 24 de 24 |

**Por qué el de capacidad:**

- El automático da más alertas de las que se pueden revisar **todos los meses**. Las que sobran se quedan
  sin mirar, y sin ningún criterio.
- El 0,5 sale de la teoría (h(x) = c(n)). El de capacidad responde a la pregunta real: "¿qué miramos con
  el tiempo que tenemos?".
- **No se usa el 1 % que plantó el generador**: en una empresa real ese número no se conoce.

**Ojo:** con un umbral fijo, las alertas siguen al volumen de pedidos: de 26 a 74 al mes. En 11 meses se
pasa de 50 (el máximo, 74, en 2024-11). Esos meses se revisa por orden de `ranking` hasta llegar a 50.

## 5. Cómo se explica cada alerta

Isolation Forest da una puntuación, pero no dice por qué. Para cada pedido se busca su **variable más
extrema**:

1. Con las variables ya transformadas (log), como las ve el modelo.
2. **Desviación robusta** = (valor − mediana) / (1,4826 · MAD), con MAD = mediana de |valor − mediana|.
   Es una puntuación z con la mediana en lugar de la media: los pedidos raros no deforman la referencia.
3. Si la MAD es 0 (más de la mitad de los pedidos tiene 1 línea o el precio de catálogo), se usa
   1,2533 · la desviación media absoluta: la versión habitual de la "puntuación z modificada" para ese caso.
4. **Motivo principal** = la variable con la mayor desviación, escrita en palabras.

Ejemplos reales del top 15:

| Ranking | Pedido | Puntuación | Motivo principal |
|---:|---:|---:|---|
| 1 | 348 | 0,752 | Importe alto: 11.730 € (mediana 84 €) |
| 3 | 2791 | 0,733 | Muchas unidades: 59 (mediana 2) |
| 12 | 3245 | 0,721 | Muchas líneas: 10 (mediana 1) |

Alguien de negocio no ve "puntuación 0,73": ve "**59 unidades cuando lo normal son 2**". En el CSV, el
motivo solo se rellena en los pedidos marcados.

**Su límite:** el motivo muestra una sola variable. En algunos pedidos lo raro es la combinación: por
ejemplo, el puesto 35 sale como "Muchas líneas: 4", cuando lo raro es tener a la vez 4 líneas, 10
unidades y 1.472 €.

## 6. Estabilidad

Con 5 semillas más (1 a 5) y el mismo criterio de umbral:

- Entre el **92,5 % y el 95,8 %** de los marcados coinciden con la semilla 42 (Jaccard medio 0,895).
- Del **top 50** coinciden **46 o 47**.
- Correlación de Spearman entre puntuaciones: de 0,979 a 0,992.
- 1.076 pedidos se marcan con las 6 semillas y 1.314 con alguna.

**Qué significa:** las alertas de arriba del ranking son fiables. Las que están justo en el umbral entran
o salen según el azar, pero tienen puntuaciones casi iguales a las de los pedidos que se quedan fuera:
da casi igual revisar unas u otras.

## 7. Evaluación: precision, recall, F1, ROC-AUC y PR-AUC

> Es la única parte que usa `_verdad_anomalias.csv` (secciones 7 y 8 del notebook). Hay 79 anomalías de
> 7.297 pedidos (1,08 %): 25 de cantidad enorme, 27 de muchas líneas, 19 de precio bajo y 8 de precio alto.
> El generador solo dice "precio anómalo": se separa en alto o bajo con el ratio del propio pedido.

### Por qué el accuracy no sirve

**Accuracy** = % de pedidos bien clasificados. Un "modelo" que **no marca nada** acierta el 98,92 %,
porque el 98,92 % de los pedidos son normales, y no encuentra ni una anomalía. Tiene más accuracy que IQR
(82,8 %) y que Isolation Forest (84,5 %). Con un 1 % de anomalías, el accuracy premia ignorarlas.

### Las métricas que sí sirven, con estos datos

Matriz de confusión de Isolation Forest con el umbral de capacidad:

| | Predicho normal | Predicho anomalía |
|---|---:|---:|
| **Normal de verdad** | 6.091 | 1.127 (falsos positivos) |
| **Anomalía de verdad** | 6 (se escapan) | **73** |

- **Precision** = de los marcados, cuántos son anomalías: 73 / 1.200 = **6,1 %**. "Si reviso un pedido
  marcado, ¿qué probabilidad hay de que sea un problema?"
- **Recall** = de las anomalías, cuántas se marcan: 73 / 79 = **92,4 %**. "¿Cuántos problemas se me
  escapan?"
- **F1** = media armónica de las dos: **0,114**. Solo es alta si las dos lo son.
- **ROC-AUC = 0,968:** si se coge al azar una anomalía y un pedido normal, el 96,8 % de las veces la
  anomalía tiene más puntuación. No depende del umbral. El azar da 0,5.
- **PR-AUC (average precision) = 0,762:** el área bajo la curva precision–recall. Con clases tan
  desequilibradas es más exigente que la ROC-AUC, porque **el azar no da 0,5, sino 0,011** (la proporción
  de anomalías).

**¿Por qué una precision tan baja?** Porque la capacidad (1.200) es mucho mayor que el número de anomalías
(79). Aunque las 79 estuvieran arriba del todo, la precision máxima sería 79 / 1.200 = **6,6 %**. Lo que
mide bien al modelo es el **orden**: **precision@50 = 86,0 %** (43 de los 50 primeros son anomalías) y
los **34 primeros son todos anomalías**.

### Recall por tipo de anomalía

| Tipo | IQR | Isolation Forest | Por qué |
|---|---:|---:|---|
| Cantidad enorme (25) | 100 % | **100 %** | 47 unidades de mediana frente a 2. Ranking mediano 14 |
| Muchas líneas (27) | 100 % | **100 %** | 10 líneas de mediana frente a 1. Ranking mediano 43 |
| Precio bajo (19) | 10,5 % | **89,5 %** | El ratio mínimo (×0,16) y el importe por unidad (13,04 € frente a 39,66 €). IQR no mira hacia abajo |
| Precio alto (8) | **100 %** | 50 % | Ver abajo |

**Por qué se escapan los precios altos:** solo 8 de 7.297 pedidos tienen un precio por encima del
catálogo, y cada árbol ve 256 pedidos al azar: **el 75,5 % de los árboles no ve ninguno**. En esos árboles
el ratio vale 1 siempre y no se puede cortar por él (solo el 25,7 % de los árboles corta alguna vez por
`ratio_precio_max`). Además, las 4 que se escapan tienen el sobreprecio en una sola línea de 2 o 3: el
importe (89,64–306,84 €) y el importe por unidad (32,03–61,37 €) son normales. IQR las encuentra todas
solo porque su límite es 1: cualquier precio por encima del catálogo cuenta como outlier.

### Los falsos positivos más altos

Sí son pedidos raros, aunque no se plantaran: pedidos de 4 líneas y 1.232–1.472 € (solo 18–23 pedidos
tienen ese importe o más) y pedidos de 5 unidades del producto más caro (1.082–1.086 €). Un equipo de
revisión querría mirarlos igualmente: la mediana de un pedido es 83,90 €.

## 8. Qué enseña la ablación

Se quitan los dos ratios de precio y se repite todo (análisis **a posteriori**: no sirve para elegir el
modelo, solo para entenderlo):

| Modelo | Recall | F1 | ROC-AUC | PR-AUC | Precision@50 | Recall precio bajo |
|---|---:|---:|---:|---:|---:|---:|
| Completo (7 variables) | 92,4 % | 0,114 | 0,968 | **0,762** | 86 % | **89,5 %** |
| Sin ratios (5 variables) | 83,5 % | 0,103 | 0,928 | 0,671 | 82 % | 52,6 % |

**Lecciones:**

1. **El algoritmo no inventa información.** Un precio raro solo se detecta bien si una variable compara el
   precio con el catálogo. Sin ella, el modelo solo ve el efecto indirecto en el importe por unidad. Una
   división en SQL aporta más que cualquier ajuste de hiperparámetros.
2. **Pero una variable buena que casi nunca cambia es difícil de usar para Isolation Forest.** Con y sin
   ratios, el recall de precios altos se queda en 50 %.
3. **Trabajo futuro (no aplicado):** una regla simple "precio ≠ catálogo → revisar" (solo 27 pedidos) junto
   al modelo cubriría los precios altos. La idea sale de la evaluación con la verdad, así que no se ha
   cambiado el modelo, igual que en la S7.

## 9. Si en una entrevista te preguntan "¿cómo detectaste pedidos sospechosos?"

> "Primero construí en SQL una tabla con una fila por pedido: importe, líneas, unidades, la cantidad más
> alta de una línea, el importe por unidad y, sobre todo, el ratio entre el precio cobrado y el de
> catálogo, con su máximo y su mínimo, porque basta una línea rara. Vi que IQR, variable a variable,
> marcaba un 18 % de los pedidos: con datos tan concentrados, 4 líneas ya eran 'outlier', y además no veía
> los precios por debajo del catálogo. Así que usé Isolation Forest, que aísla los puntos con cortes
> aleatorios: los raros se aíslan con pocos cortes. Apliqué logaritmos para que los cortes se repartieran
> bien y para que un precio ×10 y uno ×0,1 fueran igual de raros. Para el umbral no usé el 0,5 por
> defecto, que marcaba más pedidos de los que se podían revisar: lo calculé con la capacidad del equipo,
> 50 revisiones al mes. A cada alerta le añadí un motivo en palabras, la variable más extrema en
> desviaciones robustas, y comprobé que con otras semillas se marcaban casi los mismos pedidos. Como los
> datos eran simulados, al final pude evaluarlo: recall del 92 % frente al 79 % de IQR con menos alertas,
> PR-AUC de 0,76, y de los 50 pedidos más sospechosos, 43 eran anomalías reales. Se le escapaba la mitad
> de los sobreprecios, y la ablación mostró que la variable del ratio de precio era la que más aportaba.
> Lo que aprendí es que el umbral es una decisión de negocio, que con un 1 % de anomalías el accuracy no
> sirve, y que las variables importan más que el algoritmo."

## 10. Decisiones que he tomado yo (por ambigüedad)

1. **Todos los estados en `tabla_pedidos()`**, como pedía el enunciado: un pedido cancelado o devuelto
   también puede ser sospechoso.
2. **IQR solo por arriba (Q3 + 1,5·IQR)** sobre las 7 variables del modelo, como pedía el enunciado. Que no
   vea los precios bajos es parte de la lección.
3. **`log` (no `log1p`) en los ratios** para que ×10 y ×0,1 sean simétricos.
4. **`StandardScaler` dentro del pipeline** aunque no cambie nada, para el PCA (comprobado: diferencia 0).
5. **Capacidad = 50 / media de pedidos al mes** (todos los estados), con un único umbral para todo el
   periodo. En los meses de más ventas hay más de 50 alertas y se revisa por ranking.
6. **Desviación robusta con MAD y, si la MAD es 0, con 1,2533 · la desviación media absoluta.**
7. **El motivo solo se rellena en los pedidos marcados** del CSV: en un pedido normal, "su variable más
   rara" no es el motivo de nada.
8. **`marcado` como 0/1** en el CSV, y **`ranking` sin empates** (con la misma puntuación, el `id_pedido`
   más bajo va primero).
9. **Precio alto o bajo** se distingue en la evaluación con el ratio del pedido, porque el generador solo
   guarda "precio_anomalo".
10. **Estabilidad con las semillas 1 a 5**, con el mismo % de pedidos marcados que el modelo final.
11. **Los valores de A–E son un ejemplo**: no tenía los números exactos del ejercicio de clase.
12. **El modelo y el CSV se guardan antes de la evaluación** (sección "6b"), para dejar claro que no
    dependen de la verdad.
