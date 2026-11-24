# Medidas DAX del informe de Power BI

Medidas para el modelo en estrella que genera `python src/exportar_powerbi.py` (ver
[`powerbi_guia.md`](powerbi_guia.md) para importar los datos y crear las relaciones).

> **Separador de argumentos.** El código usa la **coma** (`,`) para separar los argumentos, que es
> la opción por defecto de Power BI. Si tu Power BI usa los **separadores locales** (Archivo →
> Opciones y configuración → Opciones → Configuración regional → "Usar separadores locales en
> DAX"), cambia cada `,` que separa argumentos por `;`. Por ejemplo, `DIVIDE([Margen bruto], [Ingresos])`
> pasaría a ser `DIVIDE([Margen bruto]; [Ingresos])`.

**Cómo crear una medida:** en el panel *Datos*, clic derecho sobre la tabla indicada → *Nueva
medida*, pega el código y pulsa Intro. Después, en *Herramientas de medición*, elige el formato.

**Criterio común:** igual que en los notebooks, los ingresos, el coste y los pedidos **solo cuentan
pedidos completados**. Un pedido cancelado o devuelto no es dinero que se quede la tienda.
`fact_ventas` tiene todos los estados; el filtro va en cada medida.

Los valores de referencia (sin ningún filtro) salen de la ejecución de `exportar_powerbi.py`. Están
en la lista de comprobación de la guía.

---

## Ventas (crearlas en `fact_ventas`)

### Ingresos
```dax
Ingresos =
CALCULATE (
    SUM ( fact_ventas[importe] ),
    fact_ventas[estado] = "completado"
)
```
Suma del importe (cantidad × precio cobrado) de las líneas de pedidos completados.
**Formato:** moneda (€), 2 decimales.

### Coste
```dax
Coste =
CALCULATE (
    SUM ( fact_ventas[coste] ),
    fact_ventas[estado] = "completado"
)
```
Coste de los productos vendidos (cantidad × coste de catálogo) en pedidos completados.
**Formato:** moneda (€), 2 decimales.

### Margen bruto
```dax
Margen bruto = [Ingresos] - [Coste]
```
Lo que queda de los ingresos después de pagar los productos (antes de publicidad y otros gastos).
**Formato:** moneda (€), 2 decimales.

### % Margen
```dax
% Margen = DIVIDE ( [Margen bruto], [Ingresos] )
```
Parte de cada euro vendido que es margen. `DIVIDE` devuelve vacío en lugar de error si no hay
ingresos. **Formato:** porcentaje, 1 decimal.

### Nº pedidos
```dax
Nº pedidos =
CALCULATE (
    DISTINCTCOUNT ( fact_ventas[id_pedido] ),
    fact_ventas[estado] = "completado"
)
```
Pedidos completados distintos. `fact_ventas` tiene una fila por **línea**, así que hay que contar
pedidos distintos, no filas. **Formato:** número entero.

### Ticket medio
```dax
Ticket medio = DIVIDE ( [Ingresos], [Nº pedidos] )
```
Importe medio de un pedido completado. **Formato:** moneda (€), 2 decimales.

### Nº clientes con compras
```dax
Nº clientes con compras =
CALCULATE (
    DISTINCTCOUNT ( fact_ventas[id_cliente] ),
    fact_ventas[estado] = "completado"
)
```
Clientes distintos con al menos un pedido completado en el periodo filtrado.
**Formato:** número entero.

### % Cancelados y devueltos
```dax
% Cancelados y devueltos =
DIVIDE (
    CALCULATE (
        DISTINCTCOUNT ( fact_ventas[id_pedido] ),
        fact_ventas[estado] IN { "cancelado", "devuelto" }
    ),
    DISTINCTCOUNT ( fact_ventas[id_pedido] )
)
```
Pedidos cancelados o devueltos sobre **todos** los pedidos (de cualquier estado). Es la única
medida de ventas que no filtra los completados, porque mide justo lo contrario.
**Formato:** porcentaje, 1 decimal.

---

## Publicidad (crearlas en `fact_campanas`)

### Inversión publicitaria
```dax
Inversión publicitaria = SUM ( fact_campanas[inversion] )
```
Inversión de todos los canales. Cada fila es un mes y un canal, con la fecha del primer día del mes.
**Formato:** moneda (€), 2 decimales.

### Ingresos por € de publicidad
```dax
Ingresos por € de publicidad = DIVIDE ( [Ingresos], [Inversión publicitaria] )
```
Euros vendidos por cada euro invertido, en el mismo periodo. **Cuidado:** no es el efecto causal de
la publicidad (ese está en la S6: 566,5 € más de ingresos al mes por cada 100 € más de publicidad). Esta medida divide
**todas** las ventas entre la inversión, incluidas las que habrían llegado igualmente.
Úsala por mes o por año, no por día: la inversión está apuntada el día 1 de cada mes.
**Formato:** moneda (€), 2 decimales.

---

## Inteligencia de tiempo (crearlas en `fact_ventas`)

Necesitan que `dim_fecha` esté **marcada como tabla de fechas** y relacionada con `fact_ventas`
(ver la guía).

### Ingresos del mes anterior
```dax
Ingresos mes anterior =
CALCULATE (
    [Ingresos],
    DATEADD ( dim_fecha[fecha], -1, MONTH )
)
```
Los ingresos del mes anterior al que se está mirando. `DATEADD` desplaza un mes las fechas del
filtro actual. **Formato:** moneda (€), 2 decimales.

### Variación % mensual
```dax
Variación % mensual =
DIVIDE (
    [Ingresos] - [Ingresos mes anterior],
    [Ingresos mes anterior]
)
```
Cuánto suben o bajan los ingresos respecto al mes anterior. Tiene sentido en un visual **por mes**
(eje o filas con `dim_fecha[anio_mes]`); en una tarjeta sin filtro de mes no significa nada.
En el primer mes con datos sale vacía (no hay mes anterior). **Formato:** porcentaje, 1 decimal.

### Ingresos acumulados del año
```dax
Ingresos acumulados del año =
TOTALYTD ( [Ingresos], dim_fecha[fecha] )
```
Ingresos desde el 1 de enero hasta la fecha del contexto (YTD, *year to date*). En una tabla por mes,
cada fila suma los meses anteriores del mismo año. **Formato:** moneda (€), 2 decimales.

---

## Clientes (crearlas en `dim_cliente`)

### Clientes recuperables
```dax
Clientes recuperables =
CALCULATE (
    COUNTROWS ( dim_cliente ),
    dim_cliente[accion] = "Recuperable"
)
```
Clientes en riesgo de no volver con menos de 365 días sin comprar: los candidatos a la campaña de
retención (S9). Es una foto con los datos hasta el 2026-10-31: no cambia con los filtros de fecha.
**Formato:** número entero.

### Gasto histórico de los recuperables
```dax
Gasto histórico recuperables =
CALCULATE (
    [Ingresos],
    dim_cliente[accion] = "Recuperable",
    REMOVEFILTERS ( dim_fecha )
)
```
Lo que han gastado en total (pedidos completados) los clientes recuperables. `REMOVEFILTERS ( dim_fecha )`
hace que sea **histórico**: ignora los filtros de fecha de la página. **Formato:** moneda (€), 2 decimales.

---

## Alertas de pedidos (crearlas en `fact_alertas`)

### Pedidos marcados
```dax
Pedidos marcados =
CALCULATE (
    COUNTROWS ( fact_alertas ),
    fact_alertas[marcado] = 1
)
```
Pedidos que Isolation Forest marca como sospechosos (puntuación por encima del umbral de la S8).
**Formato:** número entero.

### Importe de los pedidos marcados
```dax
Importe pedidos marcados =
CALCULATE (
    SUM ( fact_alertas[importe_total] ),
    fact_alertas[marcado] = 1
)
```
Importe total de los pedidos sospechosos, de cualquier estado: también interesa revisar un
pedido raro que se canceló. **Formato:** moneda (€), 2 decimales.

---

## Resumen

| Medida | Tabla | Formato |
|---|---|---|
| Ingresos | fact_ventas | Moneda € |
| Coste | fact_ventas | Moneda € |
| Margen bruto | fact_ventas | Moneda € |
| % Margen | fact_ventas | % |
| Nº pedidos | fact_ventas | Entero |
| Ticket medio | fact_ventas | Moneda € |
| Nº clientes con compras | fact_ventas | Entero |
| % Cancelados y devueltos | fact_ventas | % |
| Inversión publicitaria | fact_campanas | Moneda € |
| Ingresos por € de publicidad | fact_campanas | Moneda € |
| Ingresos mes anterior | fact_ventas | Moneda € |
| Variación % mensual | fact_ventas | % |
| Ingresos acumulados del año | fact_ventas | Moneda € |
| Clientes recuperables | dim_cliente | Entero |
| Gasto histórico recuperables | dim_cliente | Moneda € |
| Pedidos marcados | fact_alertas | Entero |
| Importe pedidos marcados | fact_alertas | Moneda € |
