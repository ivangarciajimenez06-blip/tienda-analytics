# Diario del proyecto

## S1 · 2–8 nov
- Hecho:
  - Repositorio en GitHub con el commit inicial.
  - Entorno virtual `.venv` y `requirements.txt` con las librerías del proyecto.
  - Estructura de carpetas: `sql/`, `src/`, `notebooks/`, `models/`, `dashboard/`, `app/` y `data/` (`raw/` y `processed/`).
  - `.gitignore`: el entorno y los datos generados no se suben.
  - README inicial con las 4 preguntas de negocio y el stack.
- Aprendido:
  - Un entorno virtual es una carpeta con su propio Python y sus librerías. Cada proyecto tiene las suyas y no se mezclan.
  - Git no guarda carpetas vacías. Por eso pongo un `.gitkeep` dentro, para que la estructura llegue al repositorio.
  - En el `.gitignore` excluyo `data/raw/*` y `data/processed/*`, pero dejo pasar sus `.gitkeep`.
- Problemas y cómo los resolví:
  - `ModuleNotFoundError` con pandas: estaba usando el Python del sistema, no el del `.venv`.
  - Lo arreglé activando el entorno (`.venv\Scripts\activate`) e instalando `requirements.txt`.

## S2 · 2–8 nov
- Hecho:
  - Modelo E/R de la tienda (`sql/modelo_er.png`).
  - `sql/schema.sql` con 7 tablas y `src/crear_bd.py`, que crea la BD vacía a partir del esquema.
- Aprendido:
  - Las restricciones hacen que la BD rechace los datos malos: `PRIMARY KEY`, `REFERENCES`, `UNIQUE`, `NOT NULL` y `CHECK` (por ejemplo, `cantidad > 0` o `coste <= precio`).
  - Las fechas van como texto AAAA-MM-DD, porque SQLite no tiene tipo fecha. El `CHECK (date(...) IS NOT NULL)` rechaza las imposibles.
  - `PRAGMA foreign_keys = ON` es por conexión. Si no lo activo en cada conexión, SQLite no comprueba las claves foráneas.
  - El orden importa: primero las tablas maestras y después las que dependen de ellas. Así se cargan luego los datos, en orden de dependencias.
  - No guardo el total del pedido: se calcula en SQL con `cantidad × precio_unitario`. Un total guardado puede dejar de cuadrar. En los CSV de la S3 hay `total_linea` incoherentes, y ese campo no existe en la BD.
- Problemas y cómo los resolví: —

## S3 y S4 · 23–29 nov
- Hecho:
  - Generador con Faker y semilla 42: 7.895 pedidos y 12.645 líneas. Cada cliente tiene un tipo oculto (fiel, ocasional o puntual) que solo está en `_verdad_clientes.csv`.
  - 79 pedidos anómalos plantados (1 %): cantidades enormes, precios raros y muchas líneas. La verdad está en `_verdad_anomalias.csv`.
  - Datos sucios en los CSV de `data/raw/` y datos limpios en la BD.
  - `limpieza.py` con informe de calidad: pedidos de 7.974 a 7.297 y líneas de 13.223 a 11.879. Las 79 anomalías llegan a la BD.
- Aprendido:
  - El CSV acepta cualquier cosa; la BD, con sus restricciones, rechaza lo malo. Por eso lo sucio va a CSV y lo limpio a la BD.
  - Mejor recuperar que borrar: recupero cantidades y precios nulos con `total_linea`. Casi todo lo que se pierde son líneas huérfanas (985).
  - Un outlier de IQR es raro, no erróneo. IQR marcaba 619 líneas por cantidad porque Q1 = 1 y Q3 = 2: 4 o 5 unidades ya eran "outlier". Si los borro, la S8 no tiene nada que encontrar.
- Problemas y cómo los resolví:
  - El paso 2 no estaba terminado: solo salían 5 CSV. Completé pedidos y detalle.
  - Pandas 3 no deja meter un nulo en una columna `int64`. Usé `Int64`.
  - Algunos errores no se pueden arreglar y eliminan el pedido. Protegí las anomalías de esos errores para no perderlas.
  - El `PRAGMA foreign_keys` de `crear_bd()` no servía para la conexión de la carga. Lo vuelvo a ejecutar en `cargar_bd()`.

## S5 · 23–29 nov
- Hecho:
  - `src/bd.py` con `leer_sql()` y `ventas_por_linea()`: las consultas van en SQL y pandas solo recibe el resultado.
  - Notebook `01_eda`: 883.361 € en 24 meses con 6.541 pedidos completados.
  - Noviembre y diciembre venden un 43,2 % más. La inversión y los ingresos tienen una correlación de 0,80.
- Aprendido:
  - `closing()` cierra la conexión; el `with` de sqlite3 solo confirma la transacción.
  - Los `?` de `params` son más seguros que meter el valor en el texto.
  - En un `LEFT JOIN`, si el filtro va en el `WHERE` desaparecen los clientes sin pedidos completados. En el `ON` se quedan.
  - `HAVING` filtra después de agrupar; `WHERE`, antes.
- Problemas y cómo los resolví:
  - Un único pedido de 10.389,60 € explicaba el pico de junio de 2026. Lo encontré con una tabla de pedidos de más de 5.000 € y lo dejé apuntado para la S6.
  - Para no poner números inventados, un script comprueba que cada número de las conclusiones aparece en las salidas.

## S6 · 23–29 nov
- Hecho:
  - `tabla_mensual()` en `features.py` y notebook `02_regresion`. El modelo final (M2) está guardado con joblib.
  - Respuesta: cada 100 € de publicidad traen 4,2 pedidos más al mes (IC 95 %: 3,4 – 5,3) y 566,5 € de ingresos. Cada euro deja 2,33 € de margen bruto. Solo vale entre 1.845 y 5.209 € al mes.
- Aprendido:
  - Variable de confusión: M1 daba 5,0 pedidos por cada 100 € porque en Navidad se invierte más y también se vende más. M2 añade la temporada y baja a 4,2.
  - Sobreajuste: M3 tenía el R² de entrenamiento más alto (0,855), pero fuera de muestra era peor (MAE LOO de 22,0 frente a 19,9).
  - Pedidos frente a euros: un pedido de 10.000 € cuenta como un pedido, pero en euros cambia la pendiente un 26,6 %.
- Problemas y cómo los resolví:
  - Q3 + 3·IQR quitaba 161 pedidos y el 18,3 % de los ingresos. Elegí el percentil 99,5: quita 33 pedidos y el 8,0 %.
  - Lo comprobé con Huber, que no quita nada: 566,5 € frente a 581,3 €.
  - Las imágenes y el `.joblib` cambiaban en cada ejecución. Quité el metadato del PNG, puse semilla al `regplot` y guardé `datos_hasta` en lugar de la fecha.

## S7 · 23–29 nov
- Hecho:
  - `tabla_rfm()` en `features.py`, notebook `03_segmentacion` y pipeline guardado con joblib.
  - 4 segmentos: Fieles, Habituales, Compra única y Perdidos. Los Fieles son el 26,8 % de los clientes y el 66,4 % de los ingresos.
- Aprendido:
  - `log1p` comprime las colas largas: la asimetría de frecuencia y monetario baja de 2,71 y 2,76 a 0,33 y −0,51.
  - Elegí k = 4 con el codo, la silueta (0,439) y Davies-Bouldin (0,800, el mínimo).
  - DBSCAN encontró 1 solo grupo y 10 clientes de ruido: los clientes forman un continuo, sin zonas densas separadas.
  - No hay que elegir el modelo con la verdad. Sin log coincidía más con ella (81,4 % frente a 79,1 %), pero me quedé con el modelo elegido antes.
- Problemas y cómo los resolví:
  - 19 clientes no tenían ningún pedido completado. Los dejé fuera del K-Means y en el CSV con segmento −1.
  - El error principal: 50 ocasionales salían como Fieles porque la frecuencia es acumulada. La frecuencia relativa queda como trabajo futuro, porque la idea salió de la verdad.

## S8 · 23–29 nov
- Hecho:
  - `tabla_pedidos()` en `features.py`: una fila por pedido, con el ratio entre el precio cobrado y el de catálogo.
  - Notebook `04_anomalias` con IQR, Isolation Forest, evaluación y ablación.
  - Modelo guardado con joblib y `pedidos_sospechosos.csv` para el Power BI.
  - Resultado: con mi umbral encuentro las mismas anomalías que IQR (63 frente a 62) con 10 veces menos alertas (121 frente a 1.298). Una de cada dos alertas es real (precision 52,1 %).
- Aprendido:
  - La capacidad de revisión es un máximo, no un objetivo. Con 50 revisiones al mes marcaba 1.200 pedidos y la precision no podía pasar del 6,6 %.
  - Hay que comparar métodos con el mismo número de alertas. Con las mismas 1.298 que IQR, Isolation Forest encuentra 11 anomalías más.
  - Las variables importan más que el algoritmo. Sin los ratios de precio, la PR-AUC baja de 0,762 a 0,671 y el recall de precios bajos cae del 42,1 % al 5,3 %.
  - El accuracy no sirve con un 1 % de anomalías: no marcar nada da un 98,92 %.
- Problemas y cómo los resolví:
  - El primer umbral llenaba la capacidad y marcaba demasiados pedidos. Lo cambié por Q3 + 1,5·IQR de las puntuaciones (s ≥ 0,614): 121 pedidos, unos 5 al mes.
  - El motivo de una sola variable no explicaba las alertas por combinación. Ahora muestra las 2–3 variables más extremas.
  - Se escapan anomalías de precio alto: solo hay 8 y el 75,5 % de los árboles no ve ninguna. Lo dejo como trabajo futuro: reglas de negocio junto con el modelo.
