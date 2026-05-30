import os
from celery import Celery

# Establece la configuración de Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Crea la app de Celery
app = Celery('core')

# Carga la configuración de Celery desde settings.py
app.config_from_object('django.conf:settings', namespace='CELERY')

# Busca tareas automáticamente en todas las apps
app.autodiscover_tasks()