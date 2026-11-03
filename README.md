# Tienda Analytics

Sistema de analítica para una tienda online: base de datos relacional,
limpieza de datos, modelos de Machine Learning y cuadro de mando.

> Proyecto en desarrollo · Datos simulados con Faker

## Preguntas de negocio

1. ¿Cuánto se vende por cada euro invertido en publicidad? → Regresión lineal
2. ¿Qué tipos de clientes hay? → K-Means (segmentación RFM)
3. ¿Qué pedidos son sospechosos? → Isolation Forest
4. ¿Qué clientes volverán a comprar en los próximos 90 días? → KNN

## Stack

Python · SQLite · pandas · scikit-learn · seaborn · Power BI · Streamlit

## Estructura

| Carpeta | Contenido |
|---|---|
| `sql/` | Esquema de la base de datos |
| `src/` | Scripts de generación, limpieza y features |
| `notebooks/` | Análisis y modelos |
| `models/` | Modelos entrenados |
| `dashboard/` | Informe de Power BI |
| `app/` | Aplicación Streamlit |

## Cómo ejecutarlo

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt