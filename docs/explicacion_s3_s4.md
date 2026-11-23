# Explicación S3 (paso 3) y S4: datos sucios, anomalías, limpieza y carga

Este documento explica qué se ha hecho en `src/generar_datos.py` y `src/limpieza.py`,
por qué, y cómo se ha comprobado que funciona.

## 0. Arreglo previo: el paso 2 no estaba terminado

Al ejecutar `python src/generar_datos.py` solo salían 5 CSV: faltaban `campanas`, `pedidos`
y `detalle_pedido`. El script no fallaba, pero:

- `generar_pedidos()` se cortaba después del bucle: no tenía `return`, ni `id_pedido`,
  ni `estado`, ni `metodo_pago`.
- No existía ninguna función para generar el detalle de los pedidos.
- `main()` no generaba ni guardaba esas tres tablas.

Qué se cambió (commit `fix: completar la generación...`):

- `generar_pedidos()` ahora ordena los pedidos por fecha y los numera (`id_pedido` 1, 2, 3...,
  así un número mayor significa un pedido más reciente). Después elige `estado` y `metodo_pago`
  con las probabilidades que ya estaban en `Estados` y `Metodos_pago`.
- Nueva `generar_detalle()`: cada pedido tiene de 1 a 4 líneas (lo más habitual es 1).
  Cada línea tiene de 1 a 5 unidades y se vende al precio de catálogo. Dentro de un pedido no se
  repite producto (`replace=False`), porque `(id_pedido, id_producto)` es la clave primaria.

Resultado: 7.895 pedidos y 12.645 líneas, los números que esperabas (~7.900 y ~12.600).

## 1. Orden en `main()`: limpio → anomalías → suciedad

```
datos limpios  ->  plantar_anomalias()  ->  ensuciar_clientes / pedidos / detalle  ->  CSV
```

El orden importa:

1. **Las anomalías se plantan sobre datos limpios.** Así cumplen el esquema
   (cantidad > 0, precio > 0, sin productos repetidos) y son pedidos posibles, solo raros.
2. **La suciedad va al final**, como en la realidad: el pedido raro existe de verdad y luego
   la exportación del sistema lo estropea (por ejemplo, le cambia el formato de la fecha).
3. Como todo usa el mismo generador `rng` con semilla 42 y siempre en el mismo orden,
   cada ejecución produce exactamente los mismos datos.

## 2. Funciones nuevas en `generar_datos.py`

### `plantar_anomalias(pedidos, detalle, productos)`

Elige el 1 % de los pedidos (79) y le da a cada uno un tipo de anomalía al azar:

| Tipo | Qué hace | Por qué es raro |
|---|---|---|
| `cantidad_enorme` | Una línea pasa a tener entre 20 y 60 unidades | Lo normal es de 1 a 5 |
| `precio_anomalo` | Una línea pasa a un precio de ×5–×10 o ×0,1–×0,2 el de catálogo (nunca 0, mínimo 0,01 €) | Lo normal es el precio de catálogo |
| `muchas_lineas` | Se añaden productos distintos hasta tener entre 8 y 12 líneas | Lo normal es de 1 a 4 |

Devuelve el detalle modificado y la "verdad" (`id_pedido`, `tipo_anomalia`), que se guarda en
`_verdad_anomalias.csv`. En la S8 compararemos lo que encuentre Isolation Forest con este archivo.

### `elegir_filas(candidatas, usadas)`

Elige entre el 1 % y el 3 % de las filas (el porcentaje exacto también lo decide `rng`).
Lleva la cuenta de las filas ya estropeadas (`usadas`) para que **cada fila tenga como mucho un
problema**. Así cada error se puede contar y arreglar por separado. Por ejemplo, una línea con
`cantidad` nula siempre tiene un `total_linea` correcto con el que recalcularla.

### `duplicar_filas(df, usadas)`

Añade copias exactas de algunas filas justo debajo de la original. Se llama la última en cada
tabla, así la copia también lleva la suciedad de la original y sigue siendo idéntica.

### `fecha_formato_europeo()` y `fechas_imposibles()`

- La primera convierte `2025-03-05` en `05/03/2025`: es la misma fecha y se puede recuperar.
- La segunda inventa fechas con mes 13–19 y día 32–45 (`2025-13-45`), que no se pueden recuperar.

### `ensuciar_clientes`, `ensuciar_pedidos`, `ensuciar_detalle`

| Tabla | Problemas que se introducen |
|---|---|
| clientes | email nulo, email en MAYÚSCULAS, ciudad en minúsculas, `fecha_alta` en dd/mm/aaaa, `fecha_alta` imposible, `fecha_alta` vacía, duplicados |
| pedidos | `id_cliente` nulo, `fecha_pedido` nula, `fecha_pedido` imposible, `fecha_pedido` en dd/mm/aaaa, estado mal escrito (`" Completado"`, `"DEVUELTO "`), duplicados |
| detalle_pedido | nueva columna `total_linea`, `cantidad` nula, `precio_unitario` nulo, cantidad negativa, `total_linea` incoherente (×1,1–×3), duplicados |

Detalles importantes:

- `total_linea` se calcula **antes** de estropear nada, así que es la referencia buena
  (salvo en las filas donde se estropea a propósito).
- El estado mal escrito sigue siendo el mismo estado: `"completado"` solo pasa a variantes
  de `"Completado"`, nunca a `"Cancelado"`.
- Se usa `Int64` (con I mayúscula) en `id_cliente` y `cantidad`. Es el entero de pandas que
  admite nulos. Pandas 3 no deja meter un nulo en una columna `int64` normal, y así además el
  CSV no muestra `468.0`.

### Protección de las anomalías

Hay errores que no se pueden arreglar: un pedido sin cliente, sin fecha o con fecha imposible,
o un cliente sin email. Esas filas se eliminan en la limpieza. **Esos errores no se aplican a
los pedidos anómalos ni a sus clientes.** Si no, perderíamos alrededor de un 7–8 % de las anomalías (el mismo porcentaje de pedidos que se elimina) y no
llegaríamos al 95 % que se pide. Los errores que sí se arreglan (formato de fecha, mayúsculas,
duplicados, negativos, nulos que se pueden recalcular) sí les pueden tocar.

## 3. `limpieza.py`, función a función

| Función | Qué hace |
|---|---|
| `leer_csvs()` | Lee todos los CSV de `data/raw/` menos los `_verdad_*` |
| `anotar()` | Apunta un problema (tabla, problema, casos, qué se hizo) para el informe |
| `quitar_duplicados_exactos()` | `df.duplicated()`: filas idénticas en todas las columnas |
| `quitar_claves_repetidas()` | Filas que repiten una PK o un UNIQUE (aunque no sean idénticas) |
| `normalizar_texto()` | Aplica `strip/lower/title` y cuenta cuántos valores ha cambiado |
| `convertir_fechas()` | Prueba `AAAA-MM-DD` y, si falla, `dd/mm/aaaa`, siempre con `errors="coerce"`. Lo que no encaja queda `NaT` |
| `es_vacio()` | Nulo o texto vacío |
| `limpiar_tabla_maestra()` | categorias, proveedores, productos y campanas no se ensucian, pero se revisan igual |
| `limpiar_pedidos()` | Duplicados → estado → valores permitidos → `id_cliente` nulo → fechas → `id_pedido` repetido |
| `limpiar_clientes()` | Duplicados → email y ciudad → email nulo → `fecha_alta` → id y email repetidos |
| `limpiar_detalle()` | Duplicados → negativos → nulos → `total_linea` → producto repetido en un pedido |
| `contar_outliers()` | Cuenta outliers con IQR **sin eliminar nada** |
| `eliminar_huerfanos()` | Pedidos sin cliente y líneas sin pedido o producto |
| `cargar_bd()` | `crear_bd()` + `PRAGMA foreign_keys = ON` + inserta fila a fila en orden de dependencias |
| `escribir_informe()` | Escribe `informe_calidad.md` y devuelve el texto para mostrarlo por consola |

### Qué se hace con cada problema y por qué

| Problema | Decisión | Motivo |
|---|---|---|
| Duplicados exactos | Eliminar, conservar uno | Contarían dos veces la misma venta |
| Texto mal escrito (estado, email, ciudad) | `strip()` + `lower()` (o `title()` en ciudad) | Es el mismo valor mal escrito. Si no, `"COMPLETADO"` no pasa el CHECK |
| Fecha `dd/mm/aaaa` | Convertir | La información está completa, solo cambia el formato |
| Fecha de pedido nula o imposible | Eliminar el pedido | No hay forma de saber cuándo fue |
| `fecha_alta` nula o imposible | Usar la fecha del primer pedido del cliente | El alta es como muy tarde el día de la primera compra. Es una aproximación razonable y así no perdemos al cliente ni sus pedidos |
| `id_cliente` nulo | Eliminar el pedido | No se puede adivinar de quién es |
| Email nulo | Eliminar el cliente (y luego sus pedidos, por huérfanos) | Es obligatorio y único: es lo que identifica al cliente |
| Cantidad negativa | `.abs()` | Es un signo mal exportado; `total_linea` (positivo) lo confirma |
| `cantidad` o `precio_unitario` nulo | Recalcular con `total_linea` | `total = cantidad × precio`, así que si falta uno se despeja. La cantidad solo se acepta si sale un entero positivo |
| `total_linea` incoherente | Se conservan cantidad y precio, y se descarta `total_linea` | `total_linea` es un campo calculado de la exportación y no existe en la BD. Si no cuadra, el error más probable está en él |
| Huérfanos | Eliminar | La BD los rechazaría por las claves foráneas |

### Por qué NO se eliminan los outliers

Un outlier de IQR es un valor **raro**, no un valor **erróneo**. Un pedido de 40 unidades o con
12 productos puede ser una empresa que compra al por mayor... o un fraude. Precisamente eso
queremos averiguar en la S8 con Isolation Forest. Si los borráramos ahora con IQR:

1. El modelo no tendría nada que encontrar.
2. No podríamos evaluarlo con `_verdad_anomalias.csv`.
3. Perderíamos ventas reales del análisis de negocio.

Por eso la limpieza solo corrige lo que **incumple las reglas** (formatos, nulos, negativos,
duplicados, claves) y los outliers solo se cuentan en el informe. Además, IQR marca muchos
falsos positivos: 619 líneas con cantidad "outlier" porque 4 o 5 unidades ya superan
Q3 + 1,5·IQR (Q1 = 1 y Q3 = 2), y eso no es raro de verdad.

### Por qué los datos sucios van a CSV y los limpios a la BD

- **CSV = la exportación en bruto**, como nos llegaría de un sistema real. Un CSV no tiene reglas
  y acepta cualquier cosa: fechas imposibles, texto donde va un número, duplicados...
  Es justo lo que necesitamos para simular el problema.
- **BD = la fuente de verdad limpia.** El esquema tiene PK, FK, CHECK y UNIQUE que **rechazan**
  los datos malos. Si intentáramos meter los sucios, la BD los rechazaría, que es lo que queremos
  que haga.
- Separarlos permite repetir la limpieza cuando queramos sin perder el original, y comparar
  antes y después (el informe de calidad).

### Carga fila a fila

`cargar_bd()` inserta las filas una a una dentro de una única transacción. Si una falla, muestra
la tabla, el número de fila, los valores y el motivo que da SQLite, deshace todo (`rollback`)
y termina con código 1. Así se probó, cambiando a propósito una cantidad a 0:

```
ERROR al cargar la tabla 'detalle_pedido' (fila 6 de los datos limpios):
  Fila: {'id_pedido': 4, 'id_producto': 7, 'cantidad': 0, 'precio_unitario': 66.34}
  Motivo: CHECK constraint failed: cantidad > 0
```

`PRAGMA foreign_keys = ON` se vuelve a ejecutar en `cargar_bd()` aunque ya esté en
`schema.sql`, porque en SQLite este ajuste es **por conexión**: el de `crear_bd()` no sirve
para la conexión nueva.

## 4. Resultados

### Informe de calidad (resumen)

| Tabla | Antes | Después |
|---|---:|---:|
| categorias | 6 | 6 |
| proveedores | 8 | 8 |
| clientes | 508 | 493 |
| productos | 60 | 60 |
| pedidos | 7.974 | 7.297 |
| detalle_pedido | 13.223 | 11.879 |
| campanas | 72 | 72 |

El informe completo está en `data/processed/informe_calidad.md`.

### Verificación

| Comprobación | Resultado |
|---|---|
| `generar_datos.py` y `limpieza.py` sin errores | ✅ |
| Pedidos sin cliente | 0 ✅ |
| Líneas sin pedido / sin producto | 0 / 0 ✅ |
| Emails repetidos | 0 ✅ |
| Fechas inválidas (`date(x) IS NOT x`) en pedidos y clientes | 0 / 0 ✅ |
| `PRAGMA foreign_key_check` | 0 ✅ |
| Estados distintos | completado, cancelado, devuelto ✅ |
| Anomalías de `_verdad_anomalias.csv` en la BD (con sus líneas) | 79 / 79 = 100 % ✅ (mínimo 95 %) |
| Dos ejecuciones seguidas | Misma huella MD5 de todos los CSV, el informe y las tablas ✅ |

Consultas usadas (para repetirlas tú):

```sql
SELECT COUNT(*) FROM pedidos p LEFT JOIN clientes c USING (id_cliente) WHERE c.id_cliente IS NULL;
SELECT COUNT(*) FROM detalle_pedido d LEFT JOIN pedidos p USING (id_pedido) WHERE p.id_pedido IS NULL;
SELECT COUNT(*) FROM detalle_pedido d LEFT JOIN productos p USING (id_producto) WHERE p.id_producto IS NULL;
SELECT email, COUNT(*) FROM clientes GROUP BY email HAVING COUNT(*) > 1;
SELECT COUNT(*) FROM pedidos  WHERE date(fecha_pedido) IS NOT fecha_pedido;
SELECT COUNT(*) FROM clientes WHERE date(fecha_alta)   IS NOT fecha_alta;
```

(`date(x) IS NOT x` detecta tanto fechas imposibles como formatos distintos de AAAA-MM-DD.)

## 5. Decisiones que he tomado yo (por ambigüedad)

1. **Completar el paso 2.** No estaba hecho (ver sección 0). Diseñé el detalle con 1–4 líneas
   y 1–5 unidades para que salieran los números que esperabas.
2. **Las tablas maestras (categorias, proveedores, productos, campanas) no se ensucian.** Tienen
   tan pocas filas (6–72) que un 1 % sería menos de una fila. Además, estropear un producto
   rompería cientos de líneas. La limpieza las revisa igualmente.
3. **"Texto vacío" y nulo son lo mismo en un CSV** (los dos se escriben como `,,`), así que el
   informe los cuenta juntos.
4. **Una fila, un problema** (`elegir_filas` con `usadas`), para que cada error se pueda recuperar
   y contar por separado.
5. **Anomalías protegidas** de los errores irrecuperables (ver sección 2).
6. **`fecha_alta` perdida → fecha del primer pedido**, en lugar de eliminar al cliente.
7. **`total_linea` incoherente → se confía en cantidad y precio** y la fila se conserva.
8. **Los pedidos que se quedan sin líneas solo se cuentan** (en esta ejecución hay 0).
9. **Duplicados de clave no exactos** (mismo `id_pedido` o mismo email con datos distintos):
   se conserva la primera fila. En estos datos hay 0, pero la comprobación queda por si acaso.
10. **Nombres en mayúsculas**: en `limpieza.py` uso `RAIZ`, `RUTA_BD`... como pide la regla.
    `crear_bd.py` y `generar_datos.py` usan `raiz` en minúscula y no los he cambiado para no
    tocar código que ya funciona.
11. **`schema.sql` no se ha modificado.**
