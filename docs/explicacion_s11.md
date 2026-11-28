# Explicación S11 (parte 1): limpieza técnica y app de Streamlit

Objetivo de la semana: dejar el proyecto limpio (nombres, finales de línea, versiones) y crear una
**app interactiva** que use los modelos guardados, pensada para alguien de negocio o de RR. HH.

Archivos de la semana:

| Archivo | Qué hace |
|---|---|
| `src/generar_datos.py`, `src/crear_bd.py` | Constantes renombradas a MAYÚSCULAS; `main()` vuelve a sembrar el azar al empezar |
| `.gitattributes` | Normaliza los finales de línea y marca los binarios |
| `requirements.txt` | Versiones fijas (`==`), con `streamlit` y `altair` |
| `.streamlit/config.toml` | Tema de la app (color principal azul) |
| `app/utilidades.py` | Toda la lógica compartida: datos, modelos, cálculos y formato español |
| `app/Inicio.py` | Página de inicio: qué es el proyecto, KPIs y las 4 preguntas de negocio |
| `app/pages/1_Simulador_publicidad.py` | S6: pedidos e ingresos esperados según la inversión |
| `app/pages/2_Ficha_de_cliente.py` | S7 + S9 (+ S8): segmento, probabilidad de volver, acción e historial |
| `app/pages/3_Pedidos_sospechosos.py` | S8: alertas con filtros por año y segmento |
| `tests/test_app.py` | 8 pruebas automáticas con `AppTest` |
| `docs/img/app_*.png` | Capturas de las 4 páginas |

Arrancar la app (desde la raíz del proyecto, con el `.venv` activado):

```powershell
streamlit run app/Inicio.py
```

## 1. Limpieza técnica

### 1.1 Constantes en MAYÚSCULAS (PEP 8)

PEP 8 (la guía de estilo de Python) dice que las **constantes** (valores que se fijan una vez y no
cambian) van en MAYÚSCULAS. Así, al leer `PEDIDOS_POR_EURO * inversion`, sabes que es un parámetro
fijo y no una variable que alguien ha modificado unas líneas más arriba.

En `generar_datos.py` se renombraron 26 constantes (`Pedidos_por_euro` → `PEDIDOS_POR_EURO`,
`Catalogo` → `CATALOGO`, `raiz` → `RAIZ`, `semilla` → `SEMILLA`...). También `crear_bd.py`, que tenía
el mismo problema (`raiz`, `schema` y `bd` → `RAIZ`, `RUTA_SCHEMA` y `RUTA_BD`, los mismos nombres que
ya usaban `limpieza.py` y `bd.py`). Se actualizaron las referencias del notebook 02 y de las
explicaciones de la S3-S4 y la S6. `DIARIO.md` no las mencionaba.

**Dos que se quedan en minúscula a propósito: `rng` y `fake`.** No son constantes: son objetos que
**cambian cada vez que se usan** (cada número aleatorio que se pide avanza su estado interno).

**Cómo se comprobó que nada cambia:**

1. Antes de tocar nada, se generaron los datos y se guardó el **hash SHA-256** de cada archivo. Un
   hash es una "huella" del contenido: si cambia un solo byte, el hash es completamente distinto.
2. Después del cambio se volvieron a generar y se compararon los hashes.

| Archivo | ¿Idéntico byte a byte? |
|---|---|
| Los 9 CSV de `data/raw/` (incluidos los `_verdad_*`) | ✅ Sí |
| `data/processed/informe_calidad.md` | ✅ Sí |
| `data/processed/tienda.db` | ✅ Mismo contenido (ver nota) |
| CSV de los notebooks y de Power BI, los 4 `.joblib` y las imágenes de `docs/img/` | ✅ Sí, tras ejecutar los notebooks 01-05 y `exportar_powerbi.py` |

> **Nota sobre `tienda.db`.** Sus bytes cambian según la BD ya existiera o se creara desde cero
> (SQLite reutiliza páginas libres del archivo). Por eso se comparó su **contenido** con
> `sqlite3.iterdump()`, que escribe toda la BD como SQL: el hash de ese volcado es idéntico.
> También se comprobó que el código *original* con la BD creada desde cero da el mismo hash que el
> código nuevo.

Los notebooks se ejecutaron con `nbconvert`, guardando la copia ejecutada fuera del repositorio:
así se comprobó que funcionan sin cambiar los `.ipynb` (ni sus marcas de tiempo). Sus salidas de
texto son idénticas, línea a línea, a las guardadas.

### 1.2 Un fallo encontrado por el camino: `main()` no era repetible

Al preparar la app apareció un problema real. `rng` y `Faker` se siembran **una sola vez, al
importar** `generar_datos.py`. Si `main()` se llama dos veces en el mismo proceso (justo lo que
puede hacer la app, que no se reinicia entre generaciones), la segunda llamada sigue con los
números aleatorios desde donde se quedó la primera y genera **otros datos**. Se comprobó: los hashes
de la primera y la segunda llamada eran distintos.

**Arreglo:** `main()` empieza llamando a `reiniciar_aleatoriedad()`, que vuelve a sembrar `rng` y
`Faker` y vacía la memoria de emails usados de Faker. La primera llamada no cambia (antes de `main()`
no se pide ningún número aleatorio), y ahora tres llamadas seguidas dan exactamente los mismos CSV.

### 1.3 `.gitattributes`: finales de línea

Cada sistema termina las líneas de texto de una forma: **Windows con CRLF** (`\r\n`, dos caracteres)
y **Linux/macOS con LF** (`\n`). Si no se dice nada, git guarda lo que le llega, y el repositorio
acaba mezclado. Aquí había **8 archivos guardados con CRLF y 18 con LF**. El problema: si alguien
abre el proyecto en otro sistema, o un editor cambia los finales de línea, git cree que han cambiado
**todas** las líneas del archivo, y el historial se llena de cambios que no son cambios. Lo vimos al
renombrar las constantes: un primer intento marcaba las 375 líneas de `generar_datos.py` como
modificadas por cambiar CRLF por LF sin querer.

```
* text=auto
*.pbix   binary
*.joblib binary
*.png    binary
*.db     binary
```

- `* text=auto`: git decide qué archivos son de texto y los guarda **siempre con LF** dentro del
  repositorio. Al sacarlos a la carpeta de trabajo, en Windows los convierte a CRLF (con la opción
  `core.autocrlf=true`, que es la de este equipo). Tú no notas nada; el repositorio queda uniforme.
- `binary`: estos archivos **nunca** se convierten. En un PNG o en un modelo, los bytes `0D 0A` no son
  un final de línea; si git los cambiara, el archivo quedaría corrupto. Git ya los detectaba bien por
  su contenido, pero así queda explícito y no depende de una adivinanza.

**El commit de renormalización** (`git add --renormalize .`) aplica la regla a los archivos que ya
estaban en el repositorio: pasa a LF los 8 que estaban con CRLF (README, `explicacion_s6.md`, los
notebooks 01-03, `requirements.txt`, `crear_bd.py` y `generar_datos.py`). Va en un commit aparte
porque su diff toca miles de líneas sin cambiar nada; `git diff --ignore-cr-at-eol` lo confirma
(sale vacío). Si mañana alguien busca "¿quién cambió esta línea?" con `git blame`, puede saltarse ese
commit con `git blame --ignore-rev <commit>`.

### 1.4 `requirements.txt` con versiones fijas

Antes ponía `pandas`, sin versión: `pip` instala **la última** que haya ese día. Ahora pone
`pandas==3.1.0`: exactamente la que hay en el `.venv`.

**Por qué importa, sobre todo al publicar la app** (por ejemplo, en Streamlit Community Cloud):

1. **Los modelos guardados dependen de la versión de scikit-learn.** Un `.joblib` es el objeto de
   Python "congelado" (con `pickle`). Si se carga con otra versión de scikit-learn, puede dar un
   aviso, dar resultados ligeramente distintos o directamente fallar, porque las clases internas
   cambian entre versiones. Con `scikit-learn==1.9.1` el servidor usa la misma versión con la que se
   entrenaron.
2. **Los datos se generan al arrancar.** La app genera la BD con `numpy` y `Faker`. Si una versión
   nueva cambiara cómo se generan los números aleatorios o los nombres, los datos serían otros y ya
   no saldrían 121 alertas ni 95 recuperables.
3. **Las librerías cambian.** Algo que funciona hoy puede dejar de funcionar con la versión del mes
   que viene (en Streamlit 1.67, por ejemplo, `use_container_width` ya está obsoleto). Fijar la versión
   hace que "funciona en mi ordenador" signifique también "funciona en el servidor".

**Qué se fija y qué no.** Solo las librerías que el proyecto **importa directamente** (numpy, pandas,
scipy, scikit-learn, joblib, Faker, matplotlib, seaborn, jupyter, streamlit y altair). Sus
dependencias (las librerías que necesitan ellas) las elige `pip`, compatibles con las fijadas. Un
`pip freeze` completo fijaría más de 100 paquetes, entre ellos algunos solo de Windows (`pywin32`)
que fallarían al instalar en el servidor de Streamlit, que es Linux. Para actualizar una versión: se
cambia el número, se ejecutan los notebooks y las pruebas, y si todo da lo mismo, se hace un commit.

## 2. Cómo funciona una app de Streamlit

### 2.1 Se ejecuta de arriba abajo en cada interacción

Una página de Streamlit es un **script normal de Python**. La idea clave es esta: **cada vez que el
usuario toca algo** (mueve el control, elige un cliente, marca una casilla), **Streamlit vuelve a
ejecutar el script entero, de la primera a la última línea**. Los controles devuelven su valor
actual:

```python
inversion = st.select_slider("Inversión mensual", options=opciones)  # 1.ª vez: valor inicial
resultado = u.simular(inversion, temporada_alta)                     # al moverlo: el nuevo valor
st.metric("Pedidos esperados", u.numero(resultado["pedidos"]))
```

No hay que programar "cuando cambie el control, actualiza el número": se vuelve a ejecutar todo con
el valor nuevo. Es muy sencillo de escribir, pero tiene un coste: **todo lo que hay en el script se
repite en cada clic**, también leer la base de datos o cargar un modelo. Para eso están las cachés.

### 2.2 `st.cache_data` y `st.cache_resource`

Una **caché** guarda el resultado de una función la primera vez que se llama. Las siguientes veces,
si los argumentos son los mismos, devuelve el resultado guardado sin volver a ejecutarla.

| | `st.cache_data` | `st.cache_resource` |
|---|---|---|
| Para qué | **Datos**: DataFrames, listas, números | **Recursos**: modelos, conexiones, acciones que solo deben ocurrir una vez |
| Qué devuelve | Una **copia** nueva en cada llamada | **El mismo objeto** a todos |
| Por qué | Si una página modifica su tabla (p. ej. añade una columna), no estropea la de las demás | Copiar un modelo en cada clic sería lento y no hace falta: nadie lo modifica |
| En la app | `kpis_ventas()`, `meses()`, `clientes()`, `pedidos()` | `asegurar_datos()`, `cargar_modelo()`, `modelo_ingresos()` |

**Por qué hacen falta.** Sin caché, cada clic en el simulador volvería a leer la BD, a cargar los 4
modelos y a puntuar los 7.297 pedidos con Isolation Forest. Con caché, eso se hace **una vez** (unos
segundos al abrir la app) y los clics siguientes son casi instantáneos. Las pruebas lo muestran: la
primera ejecución (que además genera los datos y lo calcula todo) tarda 1,7 s; cada página
siguiente, con la caché ya llena, entre 0,2 y 0,3 s.

La caché es **compartida por todos los usuarios** de la app mientras el servidor esté en marcha, y se
vacía al reiniciarlo (o con el menú ⋮ → *Clear cache*).

### 2.3 Estructura multipágina

```
app/
├── Inicio.py                         <- la página principal (la que se pasa a "streamlit run")
├── utilidades.py                     <- lógica compartida (no es una página)
└── pages/
    ├── 1_Simulador_publicidad.py     <- el número da el orden en el menú lateral;
    ├── 2_Ficha_de_cliente.py            el nombre, el texto ("Ficha de cliente")
    └── 3_Pedidos_sospechosos.py
```

Streamlit crea el menú lateral solo, a partir de la carpeta `pages/`. Las páginas **solo dibujan**:
todo lo que se calcula está en `utilidades.py`, así no se repite código. Por ejemplo, la ficha de
cliente y la página de pedidos sospechosos usan la misma función `pedidos()`.

## 3. Cómo se generan los datos al arrancar

Los datos no están en git (se generan), así que alguien que descargue el proyecto, o el servidor
donde se publique, no tiene `tienda.db`. Cada página empieza llamando a `preparar_pagina()`, que
llama a `asegurar_datos()`:

```python
@st.cache_resource(show_spinner=False)
def asegurar_datos() -> bool:
    if RUTA_BD.exists():
        return False
    import generar_datos
    import limpieza
    with st.spinner("Generando los datos simulados de la tienda por primera vez..."):
        generar_datos.main()
        limpieza.main()
    return True
```

- **Se importan las funciones de `src/`**, no se lanza `python src/generar_datos.py` con
  `subprocess`. Es el mismo código, sin abrir otro proceso de Python (que en el servidor podría ser
  otro intérprete, sin las librerías) y con errores normales de Python si algo falla.
- **`st.cache_resource`** hace que ocurra **una sola vez** mientras la app esté en marcha, aunque la
  llamen las 4 páginas en cada clic. Si dos personas abren la app a la vez, la segunda espera a que
  termine la primera, en lugar de generar los datos dos veces a la vez.
- **El aviso**: mientras se generan, la página muestra el mensaje con la rueda de carga (`st.spinner`).
  Tarda unos 2 segundos.
- **Si falla a medias**, se borra la BD incompleta, para que el siguiente intento empiece de cero y no
  se quede una BD vacía que la app creería válida.
- La salida de los scripts (sus `print`) se recoge en un texto en vez de imprimirse: en la consola de
  Windows, algunos caracteres como "€" pueden dar error al imprimirse.

**La app no depende de los notebooks.** Los CSV que generan los notebooks 03-05
(`segmentos_clientes.csv`, `pedidos_sospechosos.csv`, `riesgo_recompra.csv`) no se leen. La app
calcula lo mismo con `src/features.py` y los `.joblib`, igual que los notebooks:

| Página | Cálculo |
|---|---|
| Segmento | `tabla_rfm()` → `pipeline.predict()` del K-Means → nombres guardados en el `.joblib` |
| Probabilidad y acción | `tabla_recompra(fecha_corte())` → `predict_proba()` del KNN → umbral del `.joblib` → regla de los 365 días |
| Pedidos sospechosos | `tabla_pedidos()` → `-score_samples()` → umbral con el tope mensual → ranking → motivo con las medianas del `.joblib` |
| Simulador | `predict()` del modelo de pedidos guardado; los ingresos, con el mismo modelo reajustado (ver sección 5) |

`tests/test_app.py` comprueba que coincide **fila a fila** con los CSV de los notebooks: los 493
segmentos, las 474 probabilidades (diferencia 0 con 6 decimales), las acciones (95 / 92 / 287), y las
puntuaciones, rankings, marcas (121) y textos de motivo de los 7.297 pedidos.

## 4. Pruebas automáticas con `AppTest`

`streamlit.testing.v1.AppTest` ejecuta una página como lo haría Streamlit, pero sin navegador.
Permite leer lo que muestra y simular clics:

```python
app = AppTest.from_file("app/pages/2_Ficha_de_cliente.py").run()
assert not app.exception                                # se ejecuta sin errores
assert metricas(app)["Gasto total"] == "11.026,56 €"    # muestra lo esperado
app.selectbox[0].set_value(17).run()                    # elegir otro cliente
```

Las 8 pruebas (`python tests/test_app.py`, sin necesidad de pytest):

| Prueba | Qué comprueba |
|---|---|
| `test_genera_los_datos_si_no_existen` | Aparta `tienda.db`, abre la app y comprueba que la crea y que los ingresos son 883.360,54 € |
| `test_inicio` | Los 4 KPIs y las cifras de las 4 respuestas (4,2 pedidos, 566,5 €, 26,8 %, 121, 187 de 474, 95...) |
| `test_simulador` | El control no sale del rango observado; más inversión y temporada alta dan más pedidos |
| `test_ficha_cliente_199` | El cliente inicial es el 199, con el aviso del pedido 6477 (nº 2, 10.389,60 €) |
| `test_ficha_otros_clientes` | Un cliente de cada acción y uno sin compras se muestran sin errores |
| `test_pedidos_sospechosos` | 121 marcados, el nº 1 es el pedido 348, los filtros funcionan y sin años no hay error |
| `test_cifras_iguales_que_los_notebooks` | La comparación fila a fila de la sección 3 |
| `test_formato_espanol` | `883.360,54 €`, `6.541`, `39,5 %`, `07/06/2026` |

Además, se arrancó la app de verdad con `streamlit run` sin `tienda.db`: muestra el aviso, genera la
BD (con el mismo contenido que la original) y las 4 páginas cargan sin errores en el navegador. Las
capturas se hicieron con Playwright, instalado aparte, porque no es una dependencia de la app.

## 5. Decisiones que he tomado yo (por ambigüedad)

1. **"Ingresos estimados con la cifra elegida en la S6".** El modelo guardado (`regresion_pedidos.joblib`)
   solo predice **pedidos**. La cifra elegida en la S6 (566,5 € por cada 100 €) es la pendiente del
   modelo M2 de **ingresos sin los pedidos por encima del percentil 99,5**, que no se guardó. La app
   lo vuelve a ajustar igual que el notebook (mismos datos, mismo método, `LinearRegression`), así
   que da exactamente los mismos coeficientes; no cambia la lógica del modelo. El simulador muestra
   los ingresos estimados del mes con ese modelo y recuerda la cifra de 566,5 € por cada 100 €.
2. **La regla de los 365 días** (recuperable o probablemente perdido) no está en el `.joblib`, porque
   es una regla de negocio y no parte del modelo. Está como constante `RECENCIA_PERDIDO` en
   `utilidades.py`, con un comentario que dice de dónde sale.
3. **Fecha de corte para la recompra:** `fecha_corte()` de `features.py` (el día siguiente al último
   pedido, 2026-11-01). Es la misma que el notebook 05 tenía escrita a mano (`CORTE_PUNTUAR`), pero así
   no hay ninguna fecha escrita a mano en la app.
4. **Cliente que se muestra al abrir la ficha:** el recuperable con más gasto histórico, calculado (no
   escrito a mano). Es el 199, el caso encontrado en Power BI.
5. **"Pedidos" y "clientes" en los KPIs:** pedidos completados y clientes con al menos un pedido
   completado, igual que en el Power BI.
6. **La precisión de las alertas (52,1 %) en la página de inicio** se calcula con
   `_verdad_anomalias.csv`, que solo existe porque los datos son simulados. Se dice así en el texto,
   y si el archivo no existe, la frase no aparece.
7. **`select_slider` en lugar de `slider`** para la inversión: `slider` solo sabe escribir "3240 €";
   `select_slider` permite el formato español "3.240 €". Va de 10 en 10 € dentro del rango observado.
8. **Las tablas** usan un `Styler` de pandas para el formato español: los valores siguen siendo
   números y fechas, así que ordenar por una columna funciona bien (como texto, "9 €" iría detrás de
   "10.389 €").
9. **Tema azul** (`.streamlit/config.toml`): el rojo por defecto de Streamlit chocaba con el rojo de
   "pedido sospechoso". Ahora el rojo solo aparece en las alertas.
10. **`crear_bd.py`** también se renombró (no solo `generar_datos.py`) porque tenía el mismo problema
    y su arreglo es pequeño.
