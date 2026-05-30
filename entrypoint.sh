#!/bin/sh
set -e

echo "Esperando a PostgreSQL..."
until python -c "
import socket, sys
try:
    s = socket.create_connection(('$DB_HOST', int('$DB_PORT')), timeout=2)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
  echo "  DB no disponible, reintentando..."
  sleep 2
done
echo "PostgreSQL listo."

wait_for_migrations() {
  echo "Esperando a que las migraciones estén aplicadas..."
  until python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute(
        \"SELECT 1 FROM django_migrations WHERE app = 'users' LIMIT 1\"
    )
    assert cursor.fetchone()
" 2>/dev/null; do
    echo "  Migraciones pendientes, reintentando..."
    sleep 2
  done
  echo "Migraciones listas."
}

if [ "$SKIP_MIGRATIONS" = "1" ]; then
  wait_for_migrations
else
  echo "Aplicando migraciones..."
  python manage.py migrate --noinput
fi

# Servicios Celery: ejecutar el comando pasado por docker-compose.
if [ "$#" -gt 0 ]; then
  echo "Iniciando servicio: $*"
  exec "$@"
fi

echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "Cargando fixtures de eventos..."
python manage.py loaddata fixtures/seed_eventos.json || true

echo "Creando usuarios de prueba..."
python manage.py seed_usuarios || true

echo "Iniciando servidor ASGI (Daphne)..."
exec daphne -b 0.0.0.0 -p 8000 core.asgi:application
