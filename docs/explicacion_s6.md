# Explicación S6: regresión, publicidad y ventas

**Pregunta de negocio 1:** ¿cuánto se vende por cada euro invertido en publicidad?

**Respuesta corta:**

- **Pedidos:** cada 100 € más de publicidad traen **4,2 pedidos completados más al mes**
  (intervalo del 95 %: 3,4 – 5,3), descontando el efecto de noviembre y diciembre.
- **Margen:** en la estimación conservadora, cada € deja **2,01 € de margen bruto**
  (IC 95 %: 1,61 – 2,70 €).
- **Límite:** solo es válido entre 1.845 € y 5.209 € de inversión al mes, el rango que hemos observado.

Archivos nuevos:

| Archivo | Qué es |
|---|---|
| `src/features.py` | `tabla_mensual()` (24 filas, una por mes) y `umbral_pedidos_extremos()` |
| `notebooks/02_regresion.ipynb` | Regresión a mano, modelos, validación, bootstrap, diagnóstico y rentabilidad |
| `models/regresion_pedidos.joblib` | El modelo final (M2) en un diccionario con sus variables y la fecha de entrenamiento |
| `docs/img/regresion_*.png` | Bootstrap, diagnóstico y efecto de los pedidos extremos |

## 1. El dataset: `tabla_mensual()`

La consulta SQL está hecha con tres CTE (`WITH`):

1. **`importe_pedido`**: importe (`cantidad × precio_unitario`) y coste (`cantidad × coste` del
   producto) de cada pedido completado.
2. **`ventas_mes`**: agrupa por mes y cuenta los pedidos y suma ingresos y coste. Con
   `CASE WHEN importe > :umbral` calcula también los ingresos y el margen **sin** los pedidos
   extremos, y cuántos extremos hay.
3. **`inversion_mes`**: la inversión por canal pasada a columnas, como en la S5.

Al final se unen por mes y se calculan `mes_del_anio`, `temporada_alta` (1 en noviembre y
diciembre) y `margen_bruto = ingresos − coste_productos`. El umbral se pasa como parámetro con
nombre (`:umbral`), nunca pegado en el texto de la consulta.

### Por qué Q3 + 3·IQR para los pedidos extremos

- **IQR = Q3 − Q1:** es la anchura del 50 % central de los importes. Depende de los pedidos
  normales y no de los raros (al revés que la media o la desviación típica, que un solo pedido
  de 11.730 € desplaza).
- **¿Por qué 3 y no 1,5?** El 1,5 de los diagramas de caja marca "valores atípicos" y, con una
  cola larga como la de los importes, señalaría cientos de pedidos normales. El 3 es el criterio
  de Tukey para "atípicos **extremos**".
- **Sobre todos los pedidos completados:** el umbral se calcula una sola vez y es el mismo para
  todos los meses.
- **Valores de este dataset:** Q1 = 44,08 €, Q3 = 165,84 €, IQR = 121,76 € →
  **umbral = 165,84 + 3 × 121,76 = 531,12 €**. Lo devuelve `umbral_pedidos_extremos()` y se guarda
  en `tabla.attrs["umbral_extremos"]`.
- Los cuartiles se calculan en pandas porque SQLite no tiene función de percentiles. El resto es SQL.

**Ojo (para revisar):** el umbral marca **161 pedidos (2,5 %), que suman el 18,3 % de los
ingresos**, no solo los 2 pedidos gigantes del EDA. El importe por pedido tiene una cola larga
natural: tres productos Premium ya pasan de 531 €. Así que "sin extremos" significa "sin los
pedidos más grandes", no solo "sin anomalías".

## 2. Regresión a mano

Con n_pedidos (y) e inversión (x) de los 24 meses:

| Paso | Valor |
|---|---|
| x̄ (inversión media) | 3.517,81 € |
| ȳ (pedidos medios) | 272,54 |
| Σ(x − x̄)(y − ȳ) | 1.043.567,61 |
| Σ(x − x̄)² | 20.788.527,34 |
| β₁ = cociente de las dos sumas | **0,050199** pedidos por € |
| β₀ = ȳ − β₁·x̄ | 95,95 pedidos |

`LinearRegression` da lo mismo: la diferencia en β₁ es de 6,94·10⁻¹⁸, muy por debajo de 1e-9.
El notebook lo comprueba con un `assert`.

## 3. Las métricas, con ejemplos de estos datos

Todas las métricas se calculan sobre predicciones **fuera de muestra** (meses que el modelo no ha
visto). Los ejemplos son del modelo final M2 con Leave-One-Out:

| Métrica | Qué es | En M2 | Cómo leerlo |
|---|---|---|---|
| **MAE** (error absoluto medio) | Media de \|real − predicho\| | 19,9 pedidos | De media, el modelo se equivoca en unos 20 pedidos al mes, sobre una media de 272,5 (≈ 7 %) |
| **RMSE** (raíz del error cuadrático medio) | Eleva los errores al cuadrado antes de promediar, así que los errores grandes pesan más | 24,5 pedidos | Siempre es ≥ MAE. Si fuera mucho mayor que el MAE, habría algunos meses con errores muy grandes |
| **R²** | Qué parte de la variación entre meses explica el modelo (1 = todo, 0 = lo mismo que predecir siempre la media) | 0,808 | Explica el 81 % de por qué unos meses tienen más pedidos que otros. **Fuera de muestra puede ser negativo** si el modelo es peor que la media |

El **R² de entrenamiento** (0,850 en M2) siempre es optimista, porque evalúa el modelo con los
mismos datos con los que ha aprendido. Su utilidad es compararlo con el R² fuera de muestra: si la
diferencia es grande, hay **sobreajuste**.

## 4. Por qué validación temporal y Leave-One-Out

Con 24 meses, un único train/test aleatorio del 80/20 deja 5 meses de prueba, y el resultado
depende de la suerte de qué 5 meses toquen. Por eso se usan dos evaluaciones:

- **Validación temporal (18 + 6):** se entrena con 2024-11 … 2026-04 y se predicen los 6 últimos
  meses. Simula el uso real: con el pasado se predice el futuro, sin "mirar" datos posteriores.
- **Leave-One-Out:** 24 modelos, cada uno sin un mes, que predicen ese mes. Así hay una predicción
  honesta para **cada** mes y las métricas no dependen de un reparto concreto.
  `cross_val_predict(..., cv=LeaveOneOut())` hace exactamente eso.

## 5. Los modelos

| Modelo | Variables | R² train | MAE temporal | MAE LOO | R² LOO |
|---|---|---:|---:|---:|---:|
| M1 · n_pedidos | inversión | 0,699 | 23,6 | 27,9 | 0,637 |
| **M2 · n_pedidos** | inversión + temporada | 0,850 | 22,5 | **19,9** | **0,808** |
| M3 · n_pedidos | 3 canales + temporada | 0,855 | 22,0 | 22,0 | 0,766 |
| M2 · ingresos | inversión + temporada | 0,755 | 5.072,7 € | 4.104,2 € | 0,654 |
| M2 · ingresos sin extremos | inversión + temporada | 0,834 | 2.825,0 € | 2.680,1 € | 0,767 |
| M2 · margen bruto | inversión + temporada | 0,734 | 1.977,3 € | 1.801,0 € | 0,612 |
| M2 · margen sin extremos | inversión + temporada | 0,823 | 1.219,2 € | 1.085,5 € | 0,758 |

- **M1 exagera el efecto (5,0 pedidos por cada 100 €).** En noviembre y diciembre se invierte más
  y también se vende más por la temporada, y M1 atribuye todo a la publicidad. Es una variable
  omitida que confunde el resultado.
- **M2 separa los dos efectos:** 4,2 pedidos por cada 100 €, y +62,1 pedidos en temporada alta.
- **M3 se sobreajusta:** tiene el R² de entrenamiento más alto, pero empeora fuera de muestra
  (MAE LOO de 22,0 frente a 19,9). El coeficiente del email (7,6 por cada 100 €) parece el mejor,
  pero esa inversión es pequeña (de 100 a 400 €) y varía poco, así que su coeficiente es muy
  inestable. Con 24 datos, cada variable que se añade "cuesta" fiabilidad.

**Modelo elegido: M2 para `n_pedidos`.** Es el mejor fuera de muestra, se explica en una frase
y no depende de unos pocos pedidos enormes.

## 6. Qué es el bootstrap

No podemos repetir los 24 meses de la tienda, así que los **remuestreamos**: se sacan 24 meses al
azar **con reemplazo** de los 24 que tenemos, se entrena M2 y se guarda el coeficiente. Se repite
1.000 veces (semilla 42) y se miran los percentiles 2,5 y 97,5.

- **Resultado:** coeficiente de 0,0418, con intervalo del 95 % de [0,0341; 0,0525], es decir, de
  3,4 a 5,3 pedidos por cada 100 €.
- **En sencillo:** "lo más probable es 4,2, y es razonable cualquier valor entre 3,4 y 5,3".
- Ninguno de los 1.000 remuestreos da un efecto ≤ 0: que la publicidad ayuda está claro; el número
  exacto, no tanto.

## 7. Cómo leer los gráficos de residuos

Residuo = real − predicho.

| Gráfico | Qué tiene que pasar | Qué vemos en M2 |
|---|---|---|
| Predicho frente a real | Puntos cerca de la diagonal | Siguen la diagonal |
| Residuos frente a predicho | Una nube sin forma alrededor de 0 | Así es (desviación típica de 22,1 pedidos) |
| Residuos por mes | Ningún mes muy por encima del resto, ni rachas | Los 3 meses con más pedidos extremos no destacan (correlación de −0,04) |

Señales de alarma:
- una **curva** (la relación no es una recta);
- un **embudo** (el error crece con el tamaño);
- **rachas** de residuos del mismo signo seguidos en el tiempo (falta alguna variable temporal).

¿Por qué los pedidos extremos no destacan en `n_pedidos`? Porque un pedido de 10.000 € cuenta
como **un** pedido. Donde sí pesan es en los euros.

## 8. El efecto de los pedidos extremos

| | Por cada 100 € de publicidad | MAE LOO | R² LOO |
|---|---:|---:|---:|
| Ingresos (todos los pedidos) | 669,7 € | 4.104 € | 0,654 |
| Ingresos sin extremos | 491,4 € | 2.680 € | 0,767 |

Los pedidos extremos son el 2,5 % de los pedidos, pero **cambian la pendiente un 26,6 %**. Sin
ellos el modelo además predice mucho mejor. Su tamaño no depende de la publicidad, así que, si se
dejan dentro, una parte de su valor se atribuye por casualidad a la inversión.

## 9. Rentabilidad

Se modela el **margen bruto directamente**, en lugar de multiplicar los ingresos por un margen medio.
El margen de cada mes depende de qué se vende (Electrónica Premium frente a libros), y
`tabla_mensual()` ya calcula el coste real de cada mes. Así no hay que suponer un margen fijo.

| Estimación | Margen bruto por € de publicidad | IC 95 % |
|---|---:|---:|
| Con todos los pedidos | 2,82 € | 2,00 – 4,24 € |
| **Sin pedidos extremos (conservadora)** | **2,01 €** | **1,61 – 2,70 €** |

**¿Compensa invertir más?** Sí: incluso en el peor extremo del intervalo conservador, cada € vuelve
como más de 1 € de margen. Pero con tres precauciones:

1. Solo es válido entre **1.845 € y 5.209 €** al mes. Una recta no puede ver rendimientos
   decrecientes: el euro número 10.000 casi seguro rinde menos que el 3.000.
2. El margen bruto no descuenta envíos, devoluciones ni costes fijos.
3. Es una relación observada, no un experimento. Para estar seguros de que es causa, habría que
   variar la inversión a propósito durante unos meses.

## 10. Validación del método (posible solo porque los datos son simulados)

El generador usa `Pedidos_por_euro = 0.05`.

> Nota: en el código la constante se llama `Pedidos_por_euro`, no `PEDIDOS_POR_EURO`. No la he
> renombrado para no tocar el generador.

Ese 0,05 se aplica a todos los pedidos generados, y nosotros contamos solo los completados que
sobreviven a la limpieza. Por eso el valor esperado es **0,05 × 0,924 × 0,896 = 0,0414**. M2
estima **0,0418**, dentro del intervalo [0,0341; 0,0525]. M1 (0,0502) parecía acertar con el 0,05,
pero por casualidad: sobreestima el efecto real de los pedidos completados porque mezcla la
temporada. **En una empresa real este valor no se conoce:** por eso es tan importante la
validación fuera de muestra y el intervalo de confianza.

## 11. Si en una entrevista te preguntan "¿cuánto aporta cada euro de publicidad?"

> "Con 24 meses de datos ajusté una regresión lineal de los pedidos mensuales sobre la inversión,
> controlando la temporada de Navidad, porque se invierte más justo cuando más se vende y, sin
> controlarla, el efecto salía inflado. El resultado es que cada 100 € traen unos 4,2 pedidos más al
> mes, con un intervalo del 95 % por bootstrap de 3,4 a 5,3. Lo validé fuera de muestra con
> Leave-One-Out y con una validación temporal: el error medio es de unos 20 pedidos al mes, un 7 %.
> En margen, cada euro deja unos 2 € de margen bruto en la estimación conservadora, quitando los
> pedidos excepcionalmente grandes, que movían la pendiente un 27 %. Así que compensa invertir,
> pero solo puedo afirmarlo en el rango observado, de unos 1.800 a 5.200 € al mes, y es una
> correlación: para confirmar que es causa propondría un experimento variando la inversión."

## 12. Decisiones que he tomado yo (por ambigüedad)

1. **Margen modelado directamente** (no ingresos × margen medio). Motivo en la sección 9.
2. **He añadido `margen_sin_extremos`** a `tabla_mensual()`. No se pedía, pero la sección 6 mostró
   que los extremos inflan la pendiente, así que la respuesta de rentabilidad necesitaba una
   versión conservadora.
3. **El valor esperado de la validación se ajusta** por limpieza y por pedidos completados (sección
   10). Para la proporción de pedidos que sobreviven a la limpieza se lee `data/raw/pedidos.csv`
   (no es un archivo `_verdad_`).
4. **En la validación temporal, los 6 meses de prueba (2026-05 a 2026-10) no incluyen temporada
   alta.** Es lo que toca con el reparto 18 + 6 pedido; LOO sí la cubre.
5. **Residuos por mes:** como todos los meses tienen algún pedido extremo (de 2 a 14), se marcan
   los 3 meses con más.
6. **El `.joblib` sí se sube a git** (es pequeño y es el "entregable" del modelo). Lleva la
   `fecha_entrenamiento`, así que cambia cada vez que se ejecuta el notebook.
7. **Rectas de la sección 6 dibujadas para temporada baja** (`temporada_alta = 0`): M2 tiene dos
   rectas paralelas (baja y alta) y con una por modelo el gráfico se lee mejor.
