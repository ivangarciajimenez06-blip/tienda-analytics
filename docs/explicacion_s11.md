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
| `tests/test_app.py` | 10 pruebas automáticas con `AppTest` |
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
| Simulador | `predict()` de los dos modelos guardados de la S6: pedidos (`regresion_pedidos.joblib`) e ingresos (`regresion_ingresos.joblib`) |

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

Las 10 pruebas (`python tests/test_app.py`, sin necesidad de pytest):

| Prueba | Qué comprueba |
|---|---|
| `test_genera_los_datos_si_no_existen` | Aparta `tienda.db`, abre la app y comprueba que la crea y que los ingresos son 883.360,54 € |
| `test_inicio` | Los 4 KPIs y las cifras de las 4 respuestas (4,2 pedidos, 566,5 €, 26,8 %, 121, 187 de 474, 95...) |
| `test_simulador` | El control no sale del rango observado; más inversión y temporada alta dan más pedidos |
| `test_ficha_cliente_199` | El cliente inicial es el 199, con el aviso del pedido 6477 (nº 2, 10.389,60 €) |
| `test_ficha_otros_clientes` | Un cliente de cada acción y uno sin compras se muestran sin errores |
| `test_pedidos_sospechosos` | 121 marcados, el nº 1 es el pedido 348, los filtros funcionan y sin años no hay error |
| `test_cifras_iguales_que_los_notebooks` | La comparación fila a fila de la sección 3 |
| `test_sin_datos_personales` | Ninguna página muestra nombres ni emails de clientes (ver 6.2) |
| `test_solo_modelos_permitidos` | `cargar_modelo()` rechaza nombres fuera de la lista (ver 6.4) |
| `test_formato_espanol` | `883.360,54 €`, `6.541`, `39,5 %`, `07/06/2026` |

Además, se arrancó la app de verdad con `streamlit run` sin `tienda.db`: muestra el aviso, genera la
BD (con el mismo contenido que la original) y las 4 páginas cargan sin errores en el navegador. Las
capturas se hicieron con Playwright, instalado aparte, porque no es una dependencia de la app.

## 5. Decisiones que he tomado yo (por ambigüedad)

1. **"Ingresos estimados con la cifra elegida en la S6".** La cifra elegida en la S6 (566,5 € por
   cada 100 €) es la pendiente del modelo M2 de **ingresos sin los pedidos por encima del percentil
   99,5**. Al principio solo estaba guardado el modelo de pedidos y la app reajustaba el de ingresos.
   Ahora el notebook 02 lo guarda en `models/regresion_ingresos.joblib`, con el mismo formato que
   `regresion_pedidos.joblib` (`modelo`, `variables`, `datos_hasta`... y sin la fecha de ejecución,
   para que sea determinista: mismo hash SHA-256 en dos ejecuciones). La app lo **carga**, ya no
   ajusta nada. Comprobado: el efecto por cada 100 € y 10 simulaciones (5 inversiones × temporada sí
   o no) dan las mismas cifras que antes, a todos los decimales.
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
11. **Tabla de alertas con `st.table`, no con `st.dataframe`.** El motivo llega a ~130 caracteres. En
    `st.dataframe` (Streamlit 1.67) el texto de una celda **nunca se parte en varias líneas**: se probó
    `TextColumn(width="large")`, filas más altas (`row_height`) y saltos de línea dentro del texto, y
    en los tres casos el motivo salía cortado. `st.table` es una tabla HTML normal y sí lo parte. Va
    dentro de un `st.container(height=460)` para que las 121 filas se desplacen en vertical sin
    alargar la página. Se pierde ordenar haciendo clic en las columnas, pero la tabla ya sale
    ordenada por ranking. Comprobado en Chrome: a 1.400 px de ancho la tabla cabe entera, sin
    desplazamiento horizontal. En ventanas muy estrechas (unos 1.000 px con la barra lateral
    abierta) sobran unos 50 px. El importe lleva un espacio de no separación antes del "€" para
    que no se parta en dos líneas.
12. **`anomalias_iforest.joblib` se guarda siempre con los mismos bytes.** Al re-ejecutar el
    notebook 04, el archivo salía con otro hash que el del repositorio, aunque el contenido era el
    mismo: puntuaciones idénticas en todos los pedidos, mismos árboles, mismo umbral y mismos valores
    en `referencia_motivo`.
    - **Causa:** las claves de los diccionarios `mediana` y `escala` de `referencia_motivo` salían
      del índice de pandas (`serie.to_dict()`). Pickle guarda una cadena **una sola vez** si es *el
      mismo objeto* en memoria y, si no, la repite. Según cómo pandas comparte o copia ese índice,
      los 7 nombres de variable se guardaban una vez o dos: mismo contenido, distintos bytes.
    - **Arreglo:** las claves son ahora las cadenas de la lista `VARIABLES`
      (`{v: float(serie.round(10)[v]) for v in VARIABLES}`), la misma lista que ya va en el paquete
      como `"variables"`. Así pickle siempre las escribe una vez y luego solo las referencia, haga
      lo que haga pandas por dentro.
    - **Comprobado:** mismo hash SHA-256 en dos ejecuciones completas del notebook. Comparado con la
      versión anterior: `referencia_motivo` y las demás claves son iguales, y las puntuaciones son
      idénticas. Como el archivo cambia de bytes una vez (es la nueva forma de guardarlo), se subió
      en un commit propio. Las salidas de los notebooks 01 y 03, que solo cambiaban en las marcas de
      tiempo, no se subieron.
13. **Motivo sin frases repetidas.** En un pedido de **una sola línea**, el precio más alto y el más
    bajo respecto al catálogo (`ratio_precio_max` y `ratio_precio_min`) son el mismo, y el motivo
    decía dos veces lo mismo: "Precio por debajo del catálogo (×0,18) · Precio por debajo del
    catálogo (×0,18) · ...". Ahora se aplica la misma regla que ya existía para las unidades: si los
    dos ratios valen lo mismo, se muestra uno y entra la siguiente variable más extrema (si cumple
    la regla de la 3.ª variable, desviación de 2 o más). Se cambió en el notebook 04 y en la copia de
    la función de `app/utilidades.py`.
    - **Cambian 8 de los 121 motivos.** En 5 entra una 3.ª variable (por ejemplo, el pedido 6706:
      "Precio por encima del catálogo (×8,64) · Importe por unidad alto: 573 € · Importe alto:
      1.146 €"). En 3, la siguiente variable no es tan extrema y el motivo se queda en 2.
    - **No cambia nada más:** comparado con el CSV anterior, `id_pedido`, `puntuacion`, `ranking` y
      `marcado` son idénticos en los 7.000+ pedidos; solo cambia `motivo_principal`. Ya no hay
      ningún motivo con una frase repetida, y la app da los mismos 121 motivos que el CSV.
    - Se volvieron a generar `pedidos_sospechosos.csv` (notebook 04) y los CSV de Power BI
      (`src/exportar_powerbi.py`): sus 6 comprobaciones dan OK y solo cambia `fact_alertas.csv`, en
      esas 8 filas. El reparto del notebook pasa de 64 motivos con 2 variables y 57 con 3 a **67 y
      54**; se actualizó el texto del notebook y `docs/explicacion_s8.md`. El `.pbix` no se ha
      tocado: al pulsar *Actualizar* en Power BI, leerá los motivos nuevos.

## 6. Seguridad (antes de publicar la app)

Revisión hecha antes de publicar la app. Resumen:

| Punto | Resultado | Medida |
|---|---|---|
| Secretos en el repositorio y en el historial | ✅ Ninguno | Bloque de seguridad en `.gitignore` |
| Rutas personales | ✅ Corregida la del notebook 05 (sigue en el historial) | Avisos con ruta relativa (ver 6.1) |
| Datos personales en la app | ✅ Ninguno: solo `id_cliente` | Prueba automática |
| SQL | ✅ Todos los valores van como parámetros | — |
| Carga de modelos | ✅ Solo 5 nombres fijos de `models/` | Lista cerrada en `cargar_modelo()` + prueba |
| Errores en el navegador | ✅ Sin trazas internas | `showErrorDetails = "none"` |
| Dependencias (`pip-audit`) | ✅ Ninguna vulnerabilidad (`requirements.txt` y `.venv`) | `pip` 26.3 y `tornado==6.6.1` (ver 6.6) |
| Email de los commits | ⚠️ Dirección personal en los ya subidos | Los siguientes, con la noreply de GitHub (ver 6.7) |

### 6.1 Secretos y rutas personales

Se buscó con `git grep` (archivos actuales) y con `git log --all -p` (**todo el historial**, todas las
ramas, también lo que se borró después) cualquier cosa con forma de secreto: `password`, `secret`,
`token`, `api_key`, claves privadas (`BEGIN ... PRIVATE KEY`) y formatos conocidos de claves (`ghp_`,
`github_pat_`, `sk-...`, `AKIA...`). También emails, IPs y archivos sensibles que se hubieran subido
alguna vez (`.env`, `.db`, `.csv`, `.pem`...).

- **Secretos: ninguno.** Hubo coincidencias, pero todas eran **falsos positivos**: imágenes PNG
  guardadas en base64 dentro de los notebooks, que por azar contienen trozos como `sk-` o `AKIA`.
- **Ningún archivo sensible** se ha subido nunca (ni la BD, ni los CSV, ni `.env`), y ningún archivo
  se ha borrado del historial.
- **Una ruta personal:** una salida guardada del notebook 05 (un aviso de scikit-learn) incluía la
  ruta completa del `.venv`, con la carpeta del usuario de Windows. No es un secreto, pero dice cómo
  está organizado el equipo.

  **Corrección:** Python escribe los avisos (*warnings*) con `warnings.formatwarning`, que empieza
  por la ruta absoluta del archivo que los lanza. En la primera celda del notebook 05 se sustituye
  por una función `formato_aviso()` que muestra la ruta **relativa a la raíz del proyecto** (o solo
  el nombre del archivo, si está fuera). El aviso queda así:

  ```text
  .venv/Lib/site-packages/sklearn/model_selection/_split.py:86: UserWarning: The groups parameter is ignored by KFold
  ```

  El notebook se volvió a ejecutar entero con `nbconvert`, y la única salida de texto que cambia es
  esa línea; los CSV, el modelo y las imágenes que genera son idénticos. Después se buscaron rutas
  absolutas (`C:\`, `/Users/`, `/home/`, la carpeta del usuario, `AppData`) en **todos** los
  archivos del repositorio (notebooks, `docs/`, README, código): no queda ninguna.

  **El historial no se ha reescrito** (decisión tomada): la ruta sigue en los commits anteriores, y
  quien mire el historial en GitHub la puede ver. Solo desaparece de la versión actual.

**`.gitignore`:** se añadió al final un bloque explícito con `.env`, `.streamlit/secrets.toml` y
`*.local.*`. Las dos primeras ya estaban en la plantilla de Python, pero perdidas entre más de 200
líneas; ahora queda claro, en un solo sitio, qué no debe subirse nunca. Comprobado con
`git check-ignore`. Si algún día la app necesita una clave, va en `.streamlit/secrets.toml` y se lee
con `st.secrets`, nunca escrita en el código.

### 6.2 Datos personales

La base de datos tiene nombre y email de cada cliente (simulados con Faker, pero con forma real). La
app **no los lee nunca**: la única consulta a `clientes` pide `id_cliente, ciudad, fecha_alta`
(minimización de datos: no se carga lo que no se va a usar). En el código, "email" solo aparece como
canal de publicidad.

Para no depender de leer el código, `test_sin_datos_personales` abre las 4 páginas (y la ficha de 4
clientes distintos), recoge **todo** lo que muestran (textos, métricas, las 493 opciones del selector
de clientes y el contenido de las tablas) y comprueba que no aparece ninguno de los 493 nombres ni de
los emails de la BD. Se comprobó también que la prueba no pasa "en vacío": sí lee el interior de las
tablas y detectaría un nombre si apareciera. Las 4 capturas de `docs/img/app_*.png` se revisaron a
mano: solo aparecen números de cliente ("Cliente 199 · Murcia · Habituales").

### 6.3 SQL: siempre con parámetros

**Inyección SQL:** si un valor que viene de fuera se pega dentro del texto de la consulta, ese valor
puede cambiar la consulta. Con `f"... WHERE id_cliente = {valor}"`, un "valor" como `1 OR 1=1` haría
que la consulta devolviera todos los clientes. Con parámetros (`WHERE id_cliente = ?` o `:corte`), la
base de datos recibe el valor **aparte** y lo trata siempre como un dato, nunca como SQL.

Se revisaron todas las consultas de `src/` y `app/`, incluidas las f-strings (con el analizador de
Python `ast`, que encuentra también las de varias líneas):

- **Todos los valores van como parámetros**: `:umbral` (`tabla_mensual`), `:corte`, `:horizonte` y
  `:dias_mes` (`tabla_recompra`), y `?` en la carga de `limpieza.py`.
- Las dos f-strings de `features.py` (`CONSULTA_TABLA_MENSUAL` y `CONSULTA_RFM`) solo unen **trozos
  fijos de SQL** escritos en el propio código (`CONSULTA_IMPORTE_POR_PEDIDO`, `CONSULTA_FECHA_CORTE`).
- `limpieza.py` monta `INSERT INTO {tabla} ({columnas}) VALUES (?, ?, ...)`: interpola **nombres** de
  tabla y columna, que en SQL no se pueden pasar como parámetro. Salen de la lista fija `ORDEN_CARGA`
  y de las columnas de los CSV que genera el propio proyecto. Los **valores** sí van con `?`.
- **En la app, ningún valor del usuario llega a SQL.** El cliente elegido, el año y el segmento se
  filtran con pandas sobre tablas ya cargadas.

### 6.4 Modelos: por qué cargar un `.joblib` desconocido es peligroso

Un `.joblib` (como un `.pkl`) no es un archivo de "datos" como un CSV: guarda objetos de Python con
`pickle`, y para reconstruirlos, **`joblib.load()` puede ejecutar el código que el archivo le
indique**. El formato lo permite a propósito (así se reconstruyen objetos complejos), y un archivo
preparado puede usarlo para ejecutar cualquier cosa en el servidor: borrar archivos, leer
`secrets.toml` o instalar un programa. Y ocurre **al cargarlo**, antes de llamar a `predict()`. La
documentación de Python y la de scikit-learn lo dicen: *nunca cargues un pickle de una fuente en la
que no confíes*.

Por eso la app:

- **No tiene ninguna forma de subir archivos** (no usa `st.file_uploader`) ni lee rutas de la URL.
- Solo carga los `.joblib` de `models/`, que están en el repositorio y se generaron con los notebooks.
- `cargar_modelo(nombre)` solo acepta los 5 nombres de `MODELOS_PERMITIDOS`. Antes aceptaba cualquier
  texto, así que un `"../otra/carpeta/x"` habría cargado otro archivo si algún día alguien le pasara un
  valor del usuario. `test_solo_modelos_permitidos` comprueba que rechaza otros nombres.

Si algún día hubiera que aceptar modelos de fuera, habría que usar un formato que no ejecuta código
(por ejemplo, ONNX o `skops`, que inspecciona el archivo antes de cargarlo).

### 6.5 Errores: no enseñar trazas internas

Cuando una app de Streamlit falla, por defecto muestra en el navegador la **traza completa** (*traceback*):
el tipo de error, el mensaje, los archivos y las líneas del código interno. Al programar es muy útil,
pero en una app publicada da pistas a un atacante (rutas, librerías, cómo está hecho el código) y
confunde a un usuario de negocio.

En `.streamlit/config.toml`:

```toml
[client]
showErrorDetails = "none"
```

> **Ojo: no vale `false`.** En Streamlit 1.67 `false` está obsoleto y equivale a `"stacktrace"`, que
> **sigue mostrando la traza**. Se comprobó con una página de prueba que lanzaba un error, en Chrome:
> con `false` se veían la traza y el tipo de error; con `"none"`, solo un mensaje genérico.

La traza completa sigue saliendo en la **consola** donde corre `streamlit run`, que es donde la tiene
que mirar quien mantiene la app.

**Para ver los errores completos en local**, sin tocar el archivo (así no se sube por error):

```powershell
streamlit run app/Inicio.py --client.showErrorDetails=full
```

La opción de la línea de comandos tiene prioridad sobre `config.toml`. Un `~/.streamlit/config.toml`
global **no** sirve, porque el del proyecto tiene prioridad sobre él.

### 6.6 Dependencias: `pip-audit`

`pip-audit` compara las versiones instaladas con una base de datos pública de vulnerabilidades
conocidas. Se instaló **solo en el `.venv`** (no está en `requirements.txt`: es una herramienta de
revisión, no la necesita la app).

Primera revisión:

- **`pip-audit -r requirements.txt`** (lo que se instalaría al publicar): **ninguna vulnerabilidad**.
- **`pip-audit`** (todo el `.venv`): **13 avisos en 2 paquetes**, ninguno de los fijados en `requirements.txt`:

| Paquete | Versión | Avisos | Versión corregida | ¿Afecta a la app publicada? |
|---|---|---|---|---|
| `pip` | 25.2 | 6 distintos (12 líneas, algunos repetidos): al instalar un paquete malicioso, podría escribir archivos fuera de la carpeta de instalación | **26.2** o superior (la última es 26.3) | No: es el instalador del entorno local |
| `tornado` | 6.6 | 1: el arreglo de una redirección abierta de la 6.6.0 se podía saltar con URLs que empiezan por 3 o más barras | **6.6.1** | No: lo usa Jupyter, no Streamlit (Streamlit 1.67 usa `uvicorn`) |

`requirements.txt` salía limpio porque `tornado` no estaba fijado (es una dependencia de Jupyter) y una
instalación nueva ya elegía la 6.6.1. Pero un `.venv` antiguo, como este, se quedaba con la 6.6.

**Corrección aplicada:**

- En el `.venv`: `python -m pip install --upgrade "pip>=26.2" "tornado==6.6.1"` (queda `pip` 26.3).
- En `requirements.txt`: `tornado==6.6.1`, con un comentario. Así nadie instala la 6.6, ni siquiera
  con un entorno que ya la tenía. `pip` **no** va en `requirements.txt`: es el instalador, no una
  dependencia del proyecto.
- **Compatibilidad con `streamlit==1.67.0`:** Streamlit 1.67 no depende de `tornado` (funciona sobre
  `uvicorn` y `starlette`), así que no hay conflicto posible. Lo piden los paquetes de Jupyter
  (`ipykernel` pide `>=6.5.7`, y los demás piden versiones más antiguas), y la 6.6.1 cumple todos.
  `pip check`: *No broken requirements found*. Una instalación en limpio de `requirements.txt`
  (`pip install --dry-run --ignore-installed`) resuelve `streamlit` 1.67.0, `jupyter` 1.1.1 y
  `tornado` 6.6.1.

**Después:** `pip-audit -r requirements.txt` y `pip-audit` (todo el `.venv`): **No known
vulnerabilities found** en los dos.

### 6.7 Email de los commits

`git log` muestra como autor una **dirección personal (Gmail)** en todos los commits hechos hasta
ahora (63 de ellos ya en `origin/main`). El repositorio es **público**, así que esa dirección ya es visible
para cualquiera. El commit inicial, hecho desde la web de GitHub, tiene como *committer* la dirección
genérica de GitHub, pero como autor también la personal. Los trailers `Co-Authored-By` de los commits
hechos con Claude Code usan una dirección genérica de Anthropic.

**Decisión:** los commits **ya subidos no se cambian**. Habría que reescribir el historial y forzar
el push, y aun así no se borrarían las copias que ya existan (clones, forks, cachés).

**Los commits futuros usarán la dirección noreply de GitHub** (del tipo
`número+usuario@users.noreply.github.com`), que configura el autor del proyecto:

1. En GitHub: *Settings → Emails* → **"Keep my email addresses private"**. Ahí aparece la dirección
   noreply. Conviene activar también **"Block command line pushes that expose my email"**, para que
   GitHub rechace cualquier push que todavía lleve la dirección personal.
2. En el proyecto: `git config user.email "<la dirección noreply>"`. Afecta solo a los commits
   nuevos.

GitHub asocia la dirección noreply a la misma cuenta, así que los commits nuevos siguen apareciendo
con el usuario y el avatar de siempre.

### 6.8 Otras observaciones

- Al arrancar en local, `streamlit run` escucha en todas las interfaces de red e imprime una "Network
  URL": cualquiera en la misma red wifi puede abrir la app. Con datos simulados no es grave. Para
  limitarla a tu ordenador: `streamlit run app/Inicio.py --server.address localhost`.
- Publicar la app también instalaría Jupyter, porque está en `requirements.txt`. Funciona, pero añade
  paquetes que la app no usa. Si se quisiera reducir, se podría separar en `requirements.txt` (app) y
  `requirements-dev.txt` (notebooks, `pip-audit`).
