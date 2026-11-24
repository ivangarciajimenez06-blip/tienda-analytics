# Explicación S9: ¿qué clientes volverán a comprar? (KNN)

Pregunta de negocio 4: **¿qué clientes volverán a comprar en los próximos 90 días?**

Archivos de la semana:

| Archivo | Qué hace |
|---|---|
| `src/features.py` → `tabla_recompra(fecha_corte, horizonte_dias=90)` | Una fila por cliente con 8 variables del pasado y la etiqueta `volvera` del futuro |
| `notebooks/05_recompra.ipynb` | Cortes, validación por grupos, baselines, KNN, umbral, prueba, lista de acción |
| `models/recompra_knn.joblib` | Pipeline final con las variables, el umbral, el horizonte y `datos_hasta` |
| `data/processed/riesgo_recompra.csv` | `id_cliente`, `prob_volver`, `en_riesgo`, `monetario` (no se sube a git) |
| `docs/img/recompra_*.png` | 7 gráficos |

## 1. Qué es la fuga de información

Hay **fuga de información** (*data leakage*) cuando el modelo, al entrenarse o al evaluarse, ve algo
que **no tendría en la vida real** en el momento de predecir. El resultado es un modelo que parece
muy bueno en el notebook y que falla en cuanto se usa de verdad.

Aquí hay tres formas de cometerla, y las tres se evitan:

1. **Usar el futuro.** Si "frecuencia" contara todos los pedidos hasta octubre de 2026, para un corte
   de mayo de 2026 incluiría pedidos de junio... que son justo los que la etiqueta quiere predecir.
   **Cómo se evita:** en `tabla_recompra()` las variables solo usan `fecha_pedido < corte` y la
   etiqueta solo `fecha_pedido >= corte`. El notebook lo **comprueba**: recalcula las 8 variables y
   la etiqueta con pandas, filtrando a mano, en los 7 cortes, y comprueba con un assert que coinciden.
2. **Usar los segmentos de la S7 (o los resultados de la S8).** Parecen variables inocentes ("es
   cliente Fiel"), pero se calcularon con **todos** los pedidos hasta octubre de 2026. Para un corte
   de 2025, "Fiel" ya sabe si el cliente siguió comprando después. **Cómo se evita:** no se leen en
   ningún momento.
3. **Clientes repetidos entre entrenamiento y validación.** Con varios cortes, el mismo cliente
   aparece varias veces. Si una fila suya va a validación y otra a entrenamiento, el modelo "lo
   reconoce". **Cómo se evita:** `StratifiedGroupKFold` con `id_cliente` como grupo (sección 3).

La lista real de tipos de cliente del generador (`_verdad_clientes.csv`) tampoco se usa para nada,
salvo en la sección 9 del notebook, que es solo informativa.

## 2. Cómo funcionan las fechas de corte

Una **fecha de corte** es "ponerse en la piel de la tienda ese día":

```
            pasado (variables)                 │ futuro (etiqueta)
 ──────────────────────────────────────────────┼──────────────────────►  tiempo
 alta del cliente ... pedidos ... pedidos      │ ¿algún pedido completado
                                               │  en estos 90 días?
                                          fecha de corte
```

- **Variables:** con los pedidos anteriores al corte (`recencia_dias`, `frecuencia`, `monetario`,
  `antiguedad_dias`, `pedidos_por_mes`, `ticket_medio`, `pedidos_ultimos_90d` y
  `pct_cancelados_devueltos`). Todas son de pedidos completados salvo la última, que se calcula sobre
  todos los estados.
- **Etiqueta:** `volvera = 1` si hay al menos un pedido completado en `[corte, corte + 90 días)`.

En SQL, la fecha de corte entra como **parámetro con nombre** (`:corte`), no pegada en el texto. Las
fechas se guardan como texto AAAA-MM-DD, así que `<` y `>=` comparan bien.

**Cortes usados** (cada uno 91 días después del anterior, así que las ventanas de la etiqueta no se
pisan):

| Uso | Cortes | Filas | % volvera = 1 |
|---|---|---:|---:|
| Entrenamiento | 2025-05-04, 2025-08-03, 2025-11-02, 2026-02-01 | 1142 (381 clientes) | 58,7 % |
| Prueba | 2026-05-03 | 418 | 55,5 % |
| Reentreno final | los 6 cortes con etiqueta (hasta 2026-08-02) | 2020 | — |
| Puntuar | 2026-11-01 (sin etiqueta, el futuro aún no ha pasado) | 474 | — |

Un assert comprueba que la ventana de la etiqueta de cada corte de entrenamiento termina antes del
2026-05-03. Así la prueba es de verdad "el futuro" para el modelo.

**`pedidos_por_mes`** es la frecuencia dividida por los meses desde el alta (con un mínimo de un mes,
para que un cliente con 2 pedidos en 3 días no salga con "20 pedidos al mes"). Responde a lo que se
vio en la S7: la frecuencia acumulada no distingue "mucho tiempo comprando poco" de "poco tiempo
comprando mucho".

## 3. Por qué `GroupKFold` (y no `KFold`)

En el entrenamiento, 176 clientes aparecen en los 4 cortes. Con un `KFold` normal, el **90,8 %** de
las filas de validación tenían al mismo cliente en el entrenamiento de ese pliegue. Validar así es
como estudiar con las preguntas del examen: la nota sale demasiado optimista, porque el modelo no
tiene que generalizar a clientes nuevos.

`StratifiedGroupKFold` mete todas las filas de un cliente en el mismo pliegue (0,0 % de repetidos) y,
además, mantiene un % de `volvera = 1` parecido en cada pliegue.

**Lo que salió aquí, contado tal cual:** la diferencia en la ROC-AUC fue mínima (entre −0,004 y
0,002 según k). Las filas del mismo cliente en cortes distintos no son copias: en 91 días cambian su
recencia, su frecuencia y su antigüedad. El riesgo no desaparece (con cortes más juntos sí lo
serían), así que se sigue validando por grupos.

## 4. Por qué comparar con baselines

Un modelo solo vale la pena si mejora lo que se podría hacer **sin** él. Por eso, antes de KNN:

- **Dummy (clase mayoritaria):** dice siempre "volverá". Es el suelo del accuracy: 0,555 en la prueba.
  Con un 55,5 % de clientes que vuelven, un accuracy apenas por encima de ese valor no sería ningún logro.
- **Regla de negocio:** "volverá si compró en los últimos 90 días". Es lo que haría marketing sin
  modelo. Si KNN no la supera, no compensa mantenerlo.
- **Regresión logística:** el modelo sencillo de referencia.

## 5. KNN: k, pesos, métrica y variables

Pipeline: `ColumnTransformer` (`log1p` en las 7 variables con asimetría > 1 en el entrenamiento) →
`StandardScaler` → `KNeighborsClassifier`. El escalado es imprescindible: sin él, los euros (miles)
dominarían la distancia frente al nº de pedidos (decenas).

`GridSearchCV` con la validación por grupos: k de 1 a 75 (impares), `weights` uniform/distance y
métrica euclidea/manhattan, optimizando ROC-AUC.

**Igual que en el ejercicio de Iris de clase** (accuracy 91,1 % con k = 5, mejor k = 9 con 95,6 %, k = 1
sobreajustaba y k = 50 subajustaba): con k = 1 el entrenamiento da 1,000 y la validación 0,708 (la
peor); la validación sube rápido hasta una meseta y baja poco a poco con k grande (0,833 con k = 75).
Los mejores k son mayores que en Iris porque hay más filas y las clases se solapan mucho más. Con
`weights="distance"` el entrenamiento siempre da 1: cada cliente es su propio vecino a distancia 0.

**Selección de variables** (con la regla fijada antes: el mejor, salvo que uno más sencillo esté a
menos de 0,005):

| Conjunto | k | ROC-AUC validación |
|---|---:|---:|
| RFM básico | 55 | 0,831 |
| **RFM + `pedidos_por_mes`** | **41** | **0,858** |
| Completo sin `pedidos_por_mes` | 21 | 0,847 |
| Completo (8 variables) | 21 | 0,849 |

`pedidos_por_mes` sube la ROC-AUC 0,027 sobre el RFM básico. Añadir el resto de variables no ayuda:
en KNN cada variable de más es una dimensión más en la distancia, y si aporta poco, mete ruido.
**KNN elegido:** RFM + `pedidos_por_mes`, k = 41, `weights="distance"`, distancia euclidea.

Antes de la prueba también se eligió **qué modelo usar**, con la validación cruzada: KNN 0,858 frente
a la logística 0,840 → KNN.

## 6. Cómo se eligió el umbral

**Caso de negocio:** una campaña de retención contacta a los clientes que probablemente **no**
volverán. Un cliente está **en riesgo** si `prob_volver < umbral`.

- **Precision** de "en riesgo": de los contactados, cuántos de verdad no iban a volver.
- **Recall** de "en riesgo": de los que no van a volver, a cuántos llegamos.

**Criterio fijado antes:** el umbral que maximiza el **F1 de la clase "no volverá"**, que equilibra las
dos. Se calcula con `cross_val_predict` en el entrenamiento: cada fila la predice un modelo que no la
ha visto. **Nunca con la prueba:** si se elige el umbral mirando la prueba, la prueba deja de medir
cómo funcionará el modelo con datos nuevos.

Resultado: **umbral = 0,59**. En validación cruzada da un F1 de 0,738, una precision del 71,9 % y un
recall del 75,8 %, y contacta al 43,6 % de los clientes. La curva de F1 es casi plana alrededor del
máximo, así que el umbral exacto importa poco. Con un presupuesto limitado se podría bajar para
contactar a menos clientes con más precision.

## 7. Resultados en la prueba (corte 2026-05-03, mirada una sola vez)

418 clientes, 186 no vuelven (44,5 %).

| Modelo | ROC-AUC | PR-AUC (no volverá) | Accuracy | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Dummy (mayoritaria) | 0,500 | 0,445 | 0,555 | 0,000 | 0,000 | 0,000 |
| Regla: compró en 90 días | 0,729 | 0,629 | 0,737 | 0,726 | 0,656 | 0,689 |
| Regresión logística (umbral 0,61) | 0,844 | **0,841** | 0,739 | 0,671 | **0,812** | **0,735** |
| **KNN (umbral 0,59)** | **0,845** | 0,811 | **0,758** | **0,732** | 0,720 | 0,726 |

Precision, recall y F1 son de la clase "no volverá".

**KNN supera con claridad a la regla, pero no a la regresión logística.** Empatan en ROC-AUC, y la
logística es mejor en PR-AUC y F1. Posibles motivos:

- La relación es casi "en una dirección" (más reciente y más frecuente → más probable volver). Una
  recta en escala log, que es lo que hace la logística, la capta bien. La ventaja de KNN, adaptarse
  a formas raras, aquí no se aprovecha.
- En la validación cruzada KNN parecía mejor (0,858 frente a 0,840), pero era la mejor entre muchas
  combinaciones de variables, k, pesos y métricas, y la mejor de muchas siempre sale algo inflada.

El modelo final sigue siendo KNN porque se eligió **antes** de ver la prueba; cambiarlo ahora sería
elegirlo con ella. La logística sería una alternativa igual de buena y más fácil de explicar.

## 8. Qué es la calibración

Un modelo está **calibrado** si sus probabilidades se pueden leer como porcentajes: de los clientes
a los que da un 70 %, vuelven unos 70 de cada 100. La **curva de calibración** agrupa a los clientes
por su probabilidad (aquí, 10 tramos del mismo tamaño) y compara la media predicha con la proporción
real. Si cae sobre la diagonal, está calibrado. El **Brier** es el error cuadrático medio de la
probabilidad (menor es mejor).

KNN: Brier 0,153 (logística 0,165) y una diferencia media de 0,072 entre lo predicho y lo real por
tramo. Está razonablemente calibrado, pero con 418 clientes de prueba cada tramo tiene pocos clientes;
la probabilidad sirve sobre todo para **ordenar**.

## 9. La lista de acción

El modelo se reentrena con los 6 cortes con etiqueta (2020 filas), con las **mismas** variables, k y
umbral, y puntúa a los clientes con el corte 2026-11-01:

- **187 de 474 clientes (39,5 %) están en riesgo**. Suman 139.479 € de gasto histórico (15,8 % del total).
- Los 15 más valiosos en riesgo suman 63.173 €. Hay dos grupos: clientes que llevan casi dos años sin
  comprar (recencia de 621 a 703 días), que probablemente ya se han perdido, y clientes con buena
  historia que llevan unos meses sin comprar (recencia de 140 a 305 días), cerca del umbral. Estos
  segundos son la prioridad de la campaña.

**Comprobación con la verdad** (solo informativa): probabilidad media de volver de 0,914 en los fieles,
0,669 en los ocasionales y 0,122 en los puntuales. Es lo que cabía esperar.

## 10. Si en una entrevista te preguntan "¿cómo predijiste qué clientes volverían?"

> "Lo planteé como una clasificación: para cada cliente, ¿hará al menos una compra en los próximos 90
> días? La clave fue no usar el futuro. Elegí varias fechas de corte, calculé las variables solo con
> los pedidos anteriores a cada corte y la etiqueta solo con los 90 días siguientes, y lo comprobé
> con un test que recalcula todo a mano.
>
> Apilé cuatro cortes para entrenar y dejé uno posterior para la prueba. Como el mismo cliente sale en
> varios cortes, validé con `StratifiedGroupKFold` por cliente.
>
> Antes de KNN puse tres referencias: un Dummy, una regla de negocio ('volverá si compró en los
> últimos 90 días') y una regresión logística. En KNN busqué k, pesos y métrica con validación
> cruzada. La variable que más aportó fue los pedidos por mes desde el alta.
>
> El umbral lo elegí para una campaña de retención, maximizando el F1 de 'no volverá' con
> predicciones de validación cruzada, nunca con la prueba.
>
> En la prueba, KNN tuvo una ROC-AUC de 0,845 frente a 0,729 de la regla, pero empató con la regresión
> logística, que fue incluso mejor en PR-AUC. Lo cuento tal cual: con una relación tan sencilla, un
> modelo lineal basta. El resultado es una lista de clientes en riesgo, ordenada por valor, para el
> equipo de marketing."

Preguntas que pueden venir después:

- *"¿Por qué no usaste los segmentos de la S7 como variable?"* → Se calcularon con datos posteriores
  a los cortes: sería fuga de información.
- *"¿Por qué no elegiste la logística después de ver la prueba?"* → Porque entonces la prueba ya no
  mediría nada: la habría usado para decidir.
- *"¿Qué mejorarías?"* → Más cortes (por ejemplo, mensuales) para tener más filas, y probar la
  logística como modelo final con datos nuevos.

## 11. Decisiones que he tomado yo (por ambigüedad)

1. **Clientes sin ningún pedido completado antes del corte: fuera** (entre 14 y 26 por corte; 19 en
   el corte final). No tienen recencia ni ticket medio, y la pregunta es si **volverán**. Para ellos
   haría falta una campaña de bienvenida, no de retención. Tampoco están en el CSV.
2. **`pedidos_por_mes` con un mínimo de 1 mes de antigüedad**, para que los clientes muy nuevos no
   den valores enormes. Un mes = 30,4375 días (365,25 / 12).
3. **`pct_cancelados_devueltos` en %** (0–100) sobre los pedidos de todos los estados antes del corte.
4. **`StratifiedGroupKFold` con 5 pliegues** en lugar de `GroupKFold`, para que cada pliegue tenga un
   % de `volvera = 1` parecido.
5. **`log1p` en las variables con asimetría > 1**, calculada solo con el entrenamiento (7 de 8; queda
   fuera `antiguedad_dias`).
6. **La regresión logística de referencia usa las 8 variables**, fijadas antes de la selección de
   variables de KNN.
7. **Regla para elegir el conjunto de variables y el modelo, escrita antes de ver los resultados:** el
   de más ROC-AUC de validación; entre conjuntos a menos de 0,005, el más sencillo.
8. **PR-AUC, precision, recall y F1 de la clase "no volverá"**, que es la que interesa a la campaña.
   La logística usa su propio umbral (0,61), elegido con el mismo criterio, para que la comparación
   sea justa.
9. **En el reentreno final no se vuelve a buscar k**: se mantienen los hiperparámetros y el umbral
   elegidos con el entrenamiento.
10. **Top 15 = los clientes en riesgo con más gasto histórico** (`monetario`), como pide el enunciado
    ("los más valiosos con más riesgo"). En caso de empate se ordena por `id_cliente`.
11. **El último corte con etiqueta es el 2026-08-02**, como pide el enunciado. Su ventana termina el
    2026-10-30 y los datos llegan al 2026-10-31.
