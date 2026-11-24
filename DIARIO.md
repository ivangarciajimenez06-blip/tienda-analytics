# Diario del proyecto

## S1 · 9–15 nov
- Hecho:
- Aprendido:
- Problemas y cómo los resolví:

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
