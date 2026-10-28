# AgriMarket — MVP (Sprint 1–4)
Plataforma web de productos agrícolas locales (Sabana de Bogotá). React-free SPA mobile-first + API REST FastAPI + PostgreSQL.

## Ejecutar
    cp .env.example .env      # edita contraseñas y SECRET_KEY
    docker compose up --build
- Aplicación: http://localhost:8000  ·  Documentación API: http://localhost:8000/docs
- Administrador inicial: admin@agrimarket.co / valor de ADMIN_PASSWORD (.env)

## Publicar en Render
El archivo `render.yaml` configura el servicio web Docker, PostgreSQL, variables secretas y la ruta de comprobación de salud.

1. Sube el repositorio a GitHub con `render.yaml`.
2. En Render, selecciona **New > Blueprint** y conecta el repositorio.
3. Define un valor seguro para `ADMIN_PASSWORD` cuando Render lo solicite y crea los servicios.
4. Cuando finalice el despliegue, abre la URL `onrender.com` que Render muestra para el servicio `agrimarket`.

El Blueprint usa los planes gratuitos para facilitar una prueba. En Render, el servicio web gratuito se suspende tras 15 minutos sin tráfico y la base de datos gratuita expira a los 30 días. No uses esta configuración gratuita para producción; cambia ambos planes a opciones pagadas si necesitas disponibilidad y persistencia continuas. Render asigna la URL pública al crear el servicio; no es posible activarla antes de completar el despliegue en una cuenta de Render.

## Parámetros (.env)
DB_USER, DB_PASSWORD, DB_NAME (PostgreSQL) · SECRET_KEY (firma JWT, 12 h) · ADMIN_PASSWORD

## Reglas implementadas
Roles productor/consumidor/administrador · bcrypt · consentimiento Ley 1581 · unidades kg|lb|bulto|canastilla|unidad ·
precio y cantidad > 0 · imagen JPG/PNG (comprimida en el cliente a ≤ 500 KB) · catálogo paginado de 20 con búsqueda sin tildes,
categoría y municipio · solicitud con estados Pendiente/Aceptada/Rechazada(motivo)/Entregada · WhatsApp solo tras aceptar ·
administración de categorías y suspensión de usuarios.
