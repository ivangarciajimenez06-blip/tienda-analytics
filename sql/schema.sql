-- =========================================================
-- Tienda Analytics · Esquema de la base de datos (SQLite)
-- =========================================================
-- Ejecutar con: python src/crear_bd.py
-- Las fechas se guardan como TEXT en formato ISO (AAAA-MM-DD)
-- porque SQLite no tiene un tipo fecha propio.

PRAGMA foreign_keys = ON;

-- Borrar en orden inverso a las dependencias (primero las hijas)
DROP TABLE IF EXISTS detalle_pedido;
DROP TABLE IF EXISTS pedidos;
DROP TABLE IF EXISTS productos;
DROP TABLE IF EXISTS clientes;
DROP TABLE IF EXISTS categorias;
DROP TABLE IF EXISTS proveedores;
DROP TABLE IF EXISTS campanas;

-- ---------- Tablas maestras (no dependen de nadie) ----------

CREATE TABLE categorias (
    id_categoria INTEGER PRIMARY KEY,
    nombre       TEXT    NOT NULL UNIQUE
);

CREATE TABLE proveedores (
    id_proveedor INTEGER PRIMARY KEY,
    nombre       TEXT    NOT NULL,
    email        TEXT,
    pais         TEXT    NOT NULL DEFAULT 'España'
);

CREATE TABLE clientes (
    id_cliente INTEGER PRIMARY KEY,
    nombre     TEXT    NOT NULL,
    email      TEXT    NOT NULL UNIQUE,
    ciudad     TEXT,
    fecha_alta TEXT    NOT NULL CHECK (date(fecha_alta) IS NOT NULL)
);

-- ---------- Tablas que dependen de otras ----------

CREATE TABLE productos (
    id_producto  INTEGER PRIMARY KEY,
    nombre       TEXT    NOT NULL,
    id_categoria INTEGER NOT NULL REFERENCES categorias (id_categoria),
    id_proveedor INTEGER NOT NULL REFERENCES proveedores (id_proveedor),
    precio       REAL    NOT NULL CHECK (precio > 0),
    coste        REAL    NOT NULL CHECK (coste > 0),
    CHECK (coste <= precio)
);

CREATE TABLE pedidos (
    id_pedido    INTEGER PRIMARY KEY,
    id_cliente   INTEGER NOT NULL REFERENCES clientes (id_cliente),
    fecha_pedido TEXT    NOT NULL CHECK (date(fecha_pedido) IS NOT NULL),
    estado       TEXT    NOT NULL DEFAULT 'completado'
                         CHECK (estado IN ('completado', 'cancelado', 'devuelto')),
    metodo_pago  TEXT    NOT NULL
                         CHECK (metodo_pago IN ('tarjeta', 'paypal', 'bizum', 'transferencia'))
);

CREATE TABLE detalle_pedido (
    id_pedido       INTEGER NOT NULL REFERENCES pedidos (id_pedido) ON DELETE CASCADE,
    id_producto     INTEGER NOT NULL REFERENCES productos (id_producto),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL    NOT NULL CHECK (precio_unitario > 0),
    PRIMARY KEY (id_pedido, id_producto)
);

-- ---------- Tabla independiente (se cruza por el mes) ----------

CREATE TABLE campanas (
    id_campana INTEGER PRIMARY KEY,
    mes        TEXT    NOT NULL CHECK (mes GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]'),
    canal      TEXT    NOT NULL CHECK (canal IN ('google_ads', 'meta_ads', 'email')),
    inversion  REAL    NOT NULL CHECK (inversion >= 0),
    UNIQUE (mes, canal)
);

-- ---------- Índices para acelerar las consultas habituales ----------

CREATE INDEX idx_pedidos_cliente   ON pedidos (id_cliente);
CREATE INDEX idx_pedidos_fecha     ON pedidos (fecha_pedido);
CREATE INDEX idx_detalle_producto  ON detalle_pedido (id_producto);
CREATE INDEX idx_productos_categ   ON productos (id_categoria);
