import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistroAuditoria",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tipo_evento", models.CharField(
                    choices=[
                        ("apuesta", "Apuesta"),
                        ("wallet", "Movimiento de wallet"),
                        ("odds", "Cambio de cuota"),
                        ("usuario", "Cambio de usuario/KYC"),
                        ("login", "Autenticación"),
                        ("admin", "Acción de administrador"),
                        ("antifraude", "Detección de fraude"),
                    ],
                    max_length=20,
                    verbose_name="Tipo de evento",
                )),
                ("payload", models.JSONField(verbose_name="Datos del evento")),
                ("hash_anterior", models.CharField(max_length=64, verbose_name="Hash del registro anterior")),
                ("hash_actual", models.CharField(max_length=64, verbose_name="Hash de este registro")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("usuario", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="registros_auditoria",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Usuario",
                )),
            ],
            options={
                "verbose_name": "Registro de auditoría",
                "verbose_name_plural": "Registros de auditoría",
                "ordering": ["creado_en"],
            },
        ),
        migrations.CreateModel(
            name="ActividadSospechosa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo_alerta", models.CharField(
                    choices=[
                        ("multiples_cuentas_ip", "Múltiples cuentas desde misma IP"),
                        ("patron_apuestas_identicas", "Patrón de apuestas idénticas en grupo"),
                        ("deposito_cashout_inmediato", "Depósito seguido inmediatamente de cash-out"),
                        ("lavado_bonos", "Posible abuso de bonos"),
                        ("apuestas_sin_riesgo", "Apuestas sin riesgo (cubriendo todos los resultados)"),
                    ],
                    max_length=50,
                    verbose_name="Tipo de alerta",
                )),
                ("descripcion", models.TextField(verbose_name="Descripción detallada")),
                ("revisado", models.BooleanField(default=False, verbose_name="Revisado por admin")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("revisado_en", models.DateTimeField(blank=True, null=True)),
                ("revisado_por", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="alertas_revisadas",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="alertas_fraude",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Usuario",
                )),
            ],
            options={
                "verbose_name": "Actividad sospechosa",
                "verbose_name_plural": "Actividades sospechosas",
                "ordering": ["-creado_en"],
            },
        ),
    ]