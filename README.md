# AgriMarket — MVP (Sprint 1–4)
Plataforma web de productos agrícolas locales (Sabana de Bogotá). React-free SPA mobile-first + API REST FastAPI + PostgreSQL.

## Ejecutar
    cp .env.example .env      # edita contraseñas y SECRET_KEY
    docker compose up --build
- Aplicación: http://localhost:8000  ·  Documentación API: http://localhost:8000/docs
- Administrador inicial: admin@agrimarket.co / valor de ADMIN_PASSWORD (.env)

## Parámetros (.env)
DB_USER, DB_PASSWORD, DB_NAME (PostgreSQL) · SECRET_KEY (firma JWT, 12 h) · ADMIN_PASSWORD

## Reglas implementadas
Roles productor/consumidor/administrador · bcrypt · consentimiento Ley 1581 · unidades kg|lb|bulto|canastilla|unidad ·
precio y cantidad > 0 · imagen JPG/PNG (comprimida en el cliente a ≤ 500 KB) · catálogo paginado de 20 con búsqueda sin tildes,
categoría y municipio · solicitud con estados Pendiente/Aceptada/Rechazada(motivo)/Entregada · WhatsApp solo tras aceptar ·
administración de categorías y suspensión de usuarios.
