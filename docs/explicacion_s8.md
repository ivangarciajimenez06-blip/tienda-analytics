# Explicación S8: detección de pedidos anómalos (Isolation Forest)

**Pregunta de negocio 3:** ¿qué pedidos son sospechosos?

**Respuesta corta:** los pedidos con **muchas unidades de un mismo producto**, con **muchas líneas** o
con una **combinación rara de tamaño e importe**. Los precios lejos del de catálogo se detectan peor.
Isolation Forest da a cada pedido una puntuación de sospecha y un motivo con sus 2–3 variables más
extremas. El umbral sale de la forma de las puntuaciones (Q3 + 1,5·IQR) y marca **121 pedidos (unos 5
al mes)**, muy por debajo del tope de 50 revisiones al mes. **Una de cada dos alertas es una anomalía
real** (precision 52,1 %).

| | IQR (una variable cada vez) | Isolation Forest, top 1.298 (mismo nº de alertas que IQR) | Isolation Forest, umbral elegido |
|---|---:|---:|---:|
| Pedidos marcados | 1.298 | 1.298 | **121** |
| Anomalías encontradas (de 79) | 62 | 73 | 63 |
| Precision | 4,8 % | 5,6 % | **52,1 %** |
| Recall | 78,5 % | **92,4 %** | 79,7 % |
| F1 | 0,090 | 0,106 | **0,630** |

Con la puntuación continua (no depende del umbral): **ROC-AUC = 0,968**, **PR-AUC = 0,762** (azar = 0,011)
y **precision@50 = 86,0 %**.

Archivos nuevos o cambiados:

| Archivo | Qué es |
|---|---|
| `src/features.py` | `tabla_pedidos()`. `tabla_mensual()` y `tabla_rfm()` no cambian (comprobado: mismo resultado exacto) |
| `notebooks/04_anomalias.ipynb` | IQR, Isolation Forest, umbral, motivo de cada alerta, gráficos, estabilidad, evaluación y ablación |
| `models/anomalias_iforest.joblib` | El pipeline, las variables, el umbral y su criterio, el tope mensual, la referencia para el motivo y `datos_hasta` |
| `data/processed/pedidos_sospechosos.csv` | `id_pedido`, `puntuacion`, `ranking`, `marcado`, `motivo_principal` para el Power BI de la S10 (no se sube a git, como el resto de `data/`) |
| `docs/img/anomalias_*.png` | 9 gráficos |

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

En clase hicimos 4 árboles a mano con A(1, 2), B(2, 3), C(3, 4), D(4, 5) y E(10, 10), y calculamos:

```
s(x, n) = 2 ^ ( -E[h(x)] / c(n) )        c(n) = 2·H(n-1) - 2(n-1)/n,   H(i) ≈ ln(i) + 0,5772
```

- **h(x)** es la profundidad de x (cortes hasta que queda solo) y **E[h(x)]** su media en los árboles.
- **c(n)** es el número medio de cortes para aislar un punto cualquiera en un árbol de n puntos. Sirve
  para normalizar: con 5 puntos, 2 cortes es poco; con 256, 2 cortes es poquísimo.
- h(x) mucho menor que c(n) → **s cerca de 1** → anomalía. h(x) ≈ c(n) → **s ≈ 0,5** → normal.
- **Umbral de clase: s > 0,5.**

El notebook lo calcula con la fórmula y comprueba los valores de clase con `assert`:

| Punto | Profundidad en los 4 árboles | E[h(x)] | E[h] / c(5) | s | ¿Anomalía? |
|---|---|---:|---:|---:|---|
| **E** | 1, 1, 1 y 2 | **1,25** | 0,537 | **0,689** | **Sí** |
| A–D | — | de 2,5 a 3,5 | de 1,074 a 1,504 | de 0,475 a 0,353 | No |

Con c(5) ≈ 2,327. E se aísla con poco más de la mitad de cortes que un punto cualquiera. Con 2,5 cortes
sale s = 0,4749 (redondeado, 0,47), dentro del rango 0,35–0,48 de clase.

Después se repite con scikit-learn (300 árboles al azar, mismos 5 puntos): E necesita 1,413 cortes y
puntúa 0,656; A–D, entre 0,371 y 0,481. Los números cambian porque los árboles son otros y son muchos
más, pero la conclusión es la misma: solo E pasa de 0,5.

Un detalle que en clase no aparecía: los árboles de scikit-learn se paran a una profundidad de log2(n).
Si en una hoja quedan varios puntos juntos, a su h(x) se le suma c(puntos de la hoja), que estima los
cortes que faltarían. Con eso, el notebook recalcula s a mano recorriendo los 300 árboles y comprueba
que coincide con scikit-learn.

### La relación con scikit-learn

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

## 4. El umbral: de la forma de las puntuaciones, con un tope de negocio

El modelo ordena los pedidos, pero **no dice dónde cortar**. El equipo puede revisar como mucho **50
pedidos al mes** (1.200 en 24 meses, el 16,45 % de los pedidos). **Eso es un tope, no un objetivo.** Si se
llenara siempre, la mayoría de las revisiones serían pedidos normales: con 1.200 alertas, aunque las 79
anomalías estuvieran arriba del todo, la precision no podría pasar de 79 / 1.200 = 6,6 %.

Por eso el umbral se busca en la **curva de puntuaciones ordenadas** (de mayor a menor), sin usar la
verdad, y después se aplica el tope: si un mes superara 50, solo se marcarían sus 50 más sospechosos.

| Criterio | Umbral s | Pedidos con s ≥ umbral | Marcados con el tope | Meses que llegan al tope |
|---|---:|---:|---:|---:|
| Codo de toda la curva | 0,511 | 1.463 | 1.151 | 18 |
| Codo dentro del tope (los 1.200 primeros) | 0,591 | 188 | 188 | 0 |
| **Q3 + 1,5·IQR de las puntuaciones (elegido)** | **0,614** | **121** | **121** | **0** |
| Q3 + 3·IQR de las puntuaciones | 0,732 | 3 | 3 | 0 |
| `contamination="auto"` (s > 0,5) | 0,500 | 1.710 | 1.178 | 22 |
| Llenar el tope | 0,529 | 1.200 | 1.077 | 12 |

- **El codo** es el punto de la curva más alejado de la recta que une el primero y el último: donde la
  curva deja de bajar deprisa (pocos pedidos muy raros) y se aplana (muchos parecidos). Se normalizan los
  dos ejes a 0–1 para que no dependa de las unidades.
- **Q3 + k·IQR** es la regla de Tukey de la sección 2, pero aplicada a la puntuación, que ya combina las 7
  variables.

**Por qué Q3 + 1,5·IQR:**

1. **Los criterios que llenan el tope no sirven.** El codo de toda la curva, `contamination="auto"` y
   "llenar el tope" agotan la capacidad casi todos los meses. El codo de toda la curva lo marca la forma
   de los miles de pedidos normales (la parte plana), no la de los raros.
2. **Q3 + 3·IQR es demasiado estricto:** marca 3 pedidos y deja fuera al 4.º y al 5.º, que puntúan 0,732 y
   0,731, prácticamente igual. Separa pedidos casi idénticos.
3. **Q3 + 1,5·IQR y el codo dentro del tope coinciden en el orden de magnitud** (121 y 188). Entre los
   dos se elige Q3 + 1,5·IQR porque no depende de ninguna elección arbitraria. El codo sí depende de qué
   trozo de curva se mire: con toda la curva sale 1.463 y con los 1.200 primeros, 188.
4. **Es estable:** con otras 5 semillas, su propio Q3 + 1,5·IQR marca entre 109 y 121 pedidos.

**Resultado:** 121 pedidos, 5,0 al mes de media (entre 1 y 10). **El tope no se alcanza ningún mes** y
queda libre el 89,9 % de la capacidad: si sobra tiempo, el equipo puede seguir bajando por el `ranking`.

## 5. Cómo se explica cada alerta

Isolation Forest da una puntuación, pero no dice por qué. Para cada pedido se buscan sus **variables más
extremas**:

1. Con las variables ya transformadas (log), como las ve el modelo.
2. **Desviación robusta** = (valor − mediana) / (1,4826 · MAD), con MAD = mediana de |valor − mediana|.
   Es una puntuación z con la mediana en lugar de la media: los pedidos raros no deforman la referencia.
3. Si la MAD es 0 (más de la mitad de los pedidos tiene 1 línea o el precio de catálogo), se usa
   1,2533 · la desviación media absoluta: la versión habitual de la "puntuación z modificada" para ese caso.
4. **Motivo principal** = las **2 o 3 variables con mayor desviación**, de más a menos extrema y escritas
   en palabras. Siempre se muestran 2; la 3.ª solo si también es extrema (desviación ≥ 2). Si "unidades
   totales" y "unidades en una línea" valen lo mismo, se muestra solo una.

Con una sola variable no se entendían las alertas **por combinación**. Por ejemplo, el puesto 35 salía como
"Muchas líneas: 4", y hay 380 pedidos con 4 líneas. Ahora sale "Muchas líneas: 4 · Importe alto: 1.472 €
(mediana 84 €) · Importe por unidad alto: 147 € (mediana 40 €)": lo raro es tener las tres cosas a la vez.

Ejemplos reales:

| Ranking | Pedido | Puntuación | Motivo principal |
|---:|---:|---:|---|
| 1 | 348 | 0,752 | Importe alto: 11.730 € (mediana 84 €) · Muchas unidades: 54 (mediana 2) · Importe por unidad alto: 217 € (mediana 40 €) |
| 4 | 4745 | 0,732 | Muchas unidades: 58 (mediana 2) · Importe por unidad bajo: 9 € (mediana 40 €) |
| 12 | 3245 | 0,721 | Muchas líneas: 10 (mediana 1) · Muchas unidades: 24 (mediana 2) · Importe alto: 1.813 € (mediana 84 €) |

De los 121 marcados, 64 tienen 2 variables en el motivo y 57 tienen 3. En el CSV, el motivo solo se
rellena en los pedidos marcados.

## 6. Estabilidad

Con 5 semillas más (1 a 5), marcando el mismo número de pedidos (121):

- Entre el **92,6 % y el 95,9 %** de los marcados coinciden con la semilla 42 (Jaccard medio 0,897).
- Del **top 50** coinciden **46 o 47**.
- Correlación de Spearman entre puntuaciones: de 0,979 a 0,992.
- 109 pedidos se marcan con las 6 semillas y 137 con alguna.
- Con su propio umbral Q3 + 1,5·IQR (de 0,613 a 0,619), cada semilla marca entre 109 y 121 pedidos.

**Qué significa:** las alertas de arriba del ranking son fiables y el criterio del umbral no depende de la
suerte. Las que están justo en el umbral entran o salen según la semilla, pero tienen puntuaciones casi
iguales a las de los pedidos que se quedan fuera.

## 7. Evaluación: precision, recall, F1, ROC-AUC y PR-AUC

> Es la única parte que usa `_verdad_anomalias.csv` (secciones 7 y 8 del notebook). Hay 79 anomalías de
> 7.297 pedidos (1,08 %): 25 de cantidad enorme, 27 de muchas líneas, 19 de precio bajo y 8 de precio alto.
> El generador solo dice "precio anómalo": se separa en alto o bajo con el ratio del propio pedido.

### Por qué el accuracy no sirve

**Accuracy** = % de pedidos bien clasificados. Un "modelo" que **no marca nada** acierta el 98,92 %,
porque el 98,92 % de los pedidos son normales, y no encuentra ni una anomalía. Con el umbral elegido, el
accuracy es del 99,0 %: casi lo mismo, aunque encuentra 63 anomalías. Con un 1 % de anomalías, el
accuracy premia ignorarlas.

### Las métricas que sí sirven, con estos datos

Matriz de confusión de Isolation Forest con el umbral elegido:

| | Predicho normal | Predicho anomalía |
|---|---:|---:|
| **Normal de verdad** | 7.160 | 58 (falsos positivos) |
| **Anomalía de verdad** | 16 (se escapan) | **63** |

- **Precision** = de los marcados, cuántos son anomalías: 63 / 121 = **52,1 %**. "Si reviso un pedido
  marcado, ¿qué probabilidad hay de que sea un problema?"
- **Recall** = de las anomalías, cuántas se marcan: 63 / 79 = **79,7 %**. "¿Cuántos problemas se me
  escapan?"
- **F1** = media armónica de las dos: **0,630**. Solo es alta si las dos lo son.
- **ROC-AUC = 0,968:** si se coge al azar una anomalía y un pedido normal, el 96,8 % de las veces la
  anomalía tiene más puntuación. No depende del umbral. El azar da 0,5.
- **PR-AUC (average precision) = 0,762:** el área bajo la curva precision–recall. Con clases tan
  desequilibradas es más exigente que la ROC-AUC, porque **el azar no da 0,5, sino 0,011** (la proporción
  de anomalías).
- **Precision@50 = 86,0 %:** de los 50 primeros del ranking, 43 son anomalías. Los 34 primeros lo son
  todos.

### La comparación justa con IQR

IQR marca 1.298 pedidos y el umbral elegido 121. Comparar sus precision y recall directamente mezcla
"qué método es mejor" con "cuántas alertas da cada uno". Por eso se compara IQR con **los 1.298 pedidos de
más puntuación de Isolation Forest**: mismo trabajo de revisión, distinto método.

| Con 1.298 alertas | IQR | Isolation Forest |
|---|---:|---:|
| Anomalías encontradas | 62 | **73** |
| Precision | 4,8 % | **5,6 %** |
| Recall | 78,5 % | **92,4 %** |
| F1 | 0,090 | **0,106** |

Con las mismas alertas, el modelo encuentra 11 anomalías más. Y con el umbral elegido encuentra casi las
mismas que IQR (63 frente a 62) **con 10 veces menos alertas**.

### Recall por tipo de anomalía

| Tipo | IQR (1.298) | IForest top 1.298 | IForest umbral (121) | Por qué |
|---|---:|---:|---:|---|
| Cantidad enorme (25) | 100 % | 100 % | **100 %** | 47 unidades de mediana frente a 2. Ranking mediano 14 |
| Muchas líneas (27) | 100 % | 100 % | **100 %** | 10 líneas de mediana frente a 1. Ranking mediano 43 |
| Precio bajo (19) | 10,5 % | 89,5 % | 42,1 % | Ranking mediano 146: casi todas entre los 1.298 primeros, pero no entre los 121 |
| Precio alto (8) | **100 %** | 50 % | 37,5 % | Ranking mediano 1.008,5 |

Las 16 anomalías que se escapan con el umbral elegido **son todas de precio** (11 bajas y 5 altas), con
puntuaciones de 0,433 a 0,611, justo por debajo de 0,614. **Por qué:**

1. **El ratio es una variable casi constante.** Cada árbol ve 256 pedidos al azar. Solo 8 de 7.297 tienen
   el precio por encima del catálogo, así que **el 75,5 % de los árboles no ve ninguno** (por debajo, 19
   pedidos: el 51,3 %). En esos árboles el ratio vale 1 siempre y no se puede cortar por él. Solo el 25,7 %
   de los árboles corta alguna vez por `ratio_precio_max`, y el 33,3 % por `ratio_precio_min`.
2. **Las otras variables no las delatan.** Son pedidos de 2 líneas (mediana) con el precio raro en una
   sola: el importe por unidad (44,8 € y 23,2 € de mediana) es normal.
3. **IQR encuentra todos los precios altos** solo porque su límite es 1: cualquier precio por encima del
   catálogo cuenta como outlier. Pero no ve los bajos, porque solo mira hacia arriba.

### Los falsos positivos más altos

Sí son pedidos raros, aunque no se plantaran: pedidos de 4 líneas y 1.232–1.472 € (solo 18–23 pedidos
tienen ese importe o más) y pedidos de 5 unidades del producto más caro (1.082–1.086 €). Un equipo de
revisión querría mirarlos igualmente: la mediana de un pedido es 83,90 €.

## 8. Qué enseña la ablación

Se quitan los dos ratios de precio y se repite todo, marcando el mismo número de pedidos (análisis
**a posteriori**: no sirve para elegir el modelo, solo para entenderlo):

| Modelo (121 marcados) | Precision | Recall | F1 | ROC-AUC | PR-AUC | Precision@50 | Recall precio bajo |
|---|---:|---:|---:|---:|---:|---:|---:|
| Completo (7 variables) | **52,1 %** | **79,7 %** | **0,630** | **0,968** | **0,762** | **86 %** | **42,1 %** |
| Sin ratios (5 variables) | 45,5 % | 69,6 % | 0,550 | 0,928 | 0,671 | 82 % | 5,3 % |

Con 1.298 marcados, el recall de precios bajos cae del 89,5 % al 52,6 %, y su ranking mediano pasa del
146 al 1.102.

**Lecciones:**

1. **El algoritmo no inventa información.** Un precio raro solo se detecta bien si una variable compara el
   precio con el catálogo. Sin ella, el modelo solo ve el efecto indirecto en el importe por unidad. Una
   división en SQL aporta más que cualquier ajuste de hiperparámetros.
2. **Pero una variable buena que casi nunca cambia es difícil de usar para Isolation Forest.** Los precios
   altos bajan del 37,5 % al 25 % sin ratios, pero con ellos tampoco se encuentran bien.

## 9. Trabajo futuro: un enfoque híbrido (no aplicado)

Usar **reglas de negocio junto con el modelo**. Por ejemplo, "precio pagado > precio de catálogo →
revisar" (y lo mismo por debajo, con un margen para los redondeos). Una regla así:

- **cubre justo lo que el modelo hace peor:** las 16 anomalías que se escapan son todas de precio;
- **apenas añade trabajo:** solo 27 pedidos (0,37 %) tienen un precio distinto del de catálogo;
- **se explica sola:** "se cobró 8 veces el precio de catálogo" no necesita ningún modelo.

El modelo seguiría encargándose de lo que una regla no ve: combinaciones raras de tamaño, importe y
líneas.

**Por qué no se ha aplicado:** la idea surgió al analizar los errores con la verdad (secciones 7 y 8). El
modelo, las variables y el umbral se eligieron sin ella; si se cambiaran ahora por lo que se ha visto en
la evaluación, se estarían eligiendo con la verdad y las métricas dejarían de ser honestas. Para
aplicarlo bien habría que validarlo con datos nuevos. Es la misma decisión que en la S7 con la
frecuencia relativa.

## 10. Si en una entrevista te preguntan "¿cómo detectaste pedidos sospechosos?"

> "Primero construí en SQL una tabla con una fila por pedido: importe, líneas, unidades, la cantidad más
> alta de una línea, el importe por unidad y, sobre todo, el ratio entre el precio cobrado y el de
> catálogo, con su máximo y su mínimo, porque basta una línea rara. Vi que IQR, variable a variable,
> marcaba un 18 % de los pedidos: con datos tan concentrados, 4 líneas ya eran 'outlier', y además no veía
> los precios por debajo del catálogo. Así que usé Isolation Forest, que aísla los puntos con cortes
> aleatorios: los raros se aíslan con pocos cortes. Apliqué logaritmos para que los cortes se repartieran
> bien y para que un precio ×10 y uno ×0,1 fueran igual de raros. Para el umbral, el equipo podía revisar
> 50 pedidos al mes, pero lo traté como un tope, no como un objetivo: llenarlo daba más de 1.000 alertas,
> casi todas normales. Comparé el codo de la curva de puntuaciones con la regla Q3 + 1,5·IQR sobre la
> puntuación y me quedé con esta: 121 pedidos, unos 5 al mes. A cada alerta le añadí un motivo con sus
> 2 o 3 variables más extremas, porque muchas son raras por la combinación, y comprobé que con otras
> semillas se marcaban casi los mismos pedidos. Como los datos eran simulados, al final pude evaluarlo:
> una de cada dos alertas era real, con un recall del 80 %. Comparado con IQR con el mismo número de
> alertas, encontraba 73 anomalías frente a 62. Se le escapaban sobre todo los precios raros, y la
> ablación mostró que el ratio de precio era la variable que más aportaba. Como mejora propondría
> combinar el modelo con reglas de negocio para los precios. Lo que aprendí es que el umbral es una
> decisión de negocio, que con un 1 % de anomalías el accuracy no sirve y que las variables importan más
> que el algoritmo."

## 11. Decisiones que he tomado yo (por ambigüedad)

1. **Todos los estados en `tabla_pedidos()`**, como pedía el enunciado: un pedido cancelado o devuelto
   también puede ser sospechoso.
2. **IQR solo por arriba (Q3 + 1,5·IQR)** sobre las 7 variables del modelo, como pedía el enunciado. Que no
   vea los precios bajos es parte de la lección.
3. **`log` (no `log1p`) en los ratios** para que ×10 y ×0,1 sean simétricos.
4. **`StandardScaler` dentro del pipeline** aunque no cambie nada, para el PCA (comprobado: diferencia 0).
5. **Umbral = Q3 + 1,5·IQR de las puntuaciones**, con el tope de 50 al mes aplicado por mes (los 50 de
   más puntuación). El "codo dentro del tope" mira solo los 1.200 primeros (50 al mes × 24 meses).
6. **Desviación robusta con MAD y, si la MAD es 0, con 1,2533 · la desviación media absoluta.**
7. **Motivo con 2 variables siempre y una 3.ª si su desviación es ≥ 2**; sin repetir "unidades totales" y
   "unidades en una línea" cuando valen lo mismo.
8. **El motivo solo se rellena en los pedidos marcados** del CSV: en un pedido normal, "sus variables más
   raras" no son el motivo de nada.
9. **`marcado` como 0/1** en el CSV, y **`ranking` sin empates** (con la misma puntuación, el `id_pedido`
   más bajo va primero).
10. **Precio alto o bajo** se distingue en la evaluación con el ratio del pedido, porque el generador solo
    guarda "precio_anomalo".
11. **Estabilidad con las semillas 1 a 5**, con el mismo número de pedidos marcados que el modelo final.
12. **Ablación con el mismo número de marcados** que el modelo completo (121) y que IQR (1.298), para que
    la diferencia venga solo de las variables.
13. **Ejemplo de clase:** de A–D solo tenía el rango de profundidades (2,5–3,5), así que el notebook calcula
    s en los dos extremos del rango.
14. **El modelo y el CSV se guardan antes de la evaluación** (sección "6b"), para dejar claro que no
    dependen de la verdad.
