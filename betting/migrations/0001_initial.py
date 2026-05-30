import uuid
import django.db.models.deletion
import django_fsm
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Evento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=200, verbose_name="Nombre")),
                ("deporte", models.CharField(max_length=50, verbose_name="Deporte")),
                ("equipo_local", models.CharField(max_length=100, verbose_name="Equipo local")),
                ("equipo_visitante", models.CharField(max_length=100, verbose_name="Equipo visitante")),
                ("fecha_inicio", models.DateTimeField(verbose_name="Fecha de inicio")),
                ("estado", django_fsm.FSMField(
                    choices=[
                        ("programado", "Programado"),
                        ("en_vivo", "En vivo"),
                        ("finalizado", "Finalizado"),
                        ("suspendido", "Suspendido"),
                        ("anulado", "Anulado"),
                    ],
                    default="programado",
                    max_length=50,
                    protected=True,
                    verbose_name="Estado",
                )),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Evento",
                "verbose_name_plural": "Eventos",
                "ordering": ["fecha_inicio"],
            },
        ),
        migrations.CreateModel(
            name="Mercado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(
                    choices=[
                        ("1X2", "1X2 (Gana local / Empate / Gana visitante)"),
                        ("over_under", "Over/Under 2.5 goles"),
                        ("btts", "Ambos equipos anotan (BTTS)"),
                        ("handicap", "Hándicap asiático simple"),
                        ("goleador", "Goleador exacto"),
                    ],
                    max_length=20,
                    verbose_name="Tipo de mercado",
                )),
                ("estado", models.CharField(
                    choices=[
                        ("abierto", "Abierto"),
                        ("suspendido", "Suspendido"),
                        ("cerrado", "Cerrado"),
                        ("liquidado", "Liquidado"),
                    ],
                    default="abierto",
                    max_length=15,
                    verbose_name="Estado",
                )),
                ("monto_minimo", models.DecimalField(decimal_places=4, default=Decimal("1.0000"), max_digits=18, verbose_name="Monto mínimo")),
                ("monto_maximo", models.DecimalField(decimal_places=4, default=Decimal("1000.0000"), max_digits=18, verbose_name="Monto máximo")),
                ("margen_operador", models.DecimalField(decimal_places=4, default=Decimal("0.0500"), max_digits=5, verbose_name="Margen del operador (ej. 0.05 = 5%)")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("evento", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mercados", to="betting.evento", verbose_name="Evento")),
            ],
            options={
                "verbose_name": "Mercado",
                "verbose_name_plural": "Mercados",
            },
        ),
        migrations.AddConstraint(
            model_name="mercado",
            constraint=models.UniqueConstraint(fields=["evento", "tipo"], name="mercado_evento_tipo_unico"),
        ),
        migrations.CreateModel(
            name="Cuota",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seleccion", models.CharField(max_length=50, verbose_name="Selección")),
                ("valor", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="Cuota decimal europea")),
                ("activa", models.BooleanField(default=True, verbose_name="Activa")),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("mercado", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cuotas", to="betting.mercado", verbose_name="Mercado")),
            ],
            options={
                "verbose_name": "Cuota",
                "verbose_name_plural": "Cuotas",
            },
        ),
        migrations.AddConstraint(
            model_name="cuota",
            constraint=models.UniqueConstraint(fields=["mercado", "seleccion"], name="cuota_mercado_seleccion_unica"),
        ),
        migrations.CreateModel(
            name="Apuesta",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("monto_apostado", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="Monto apostado")),
                ("cuota_al_apostar", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="Cuota al momento de apostar")),
                ("pago_potencial", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="Pago potencial (stake × odds)")),
                ("clave_idempotencia", models.UUIDField(unique=True, verbose_name="Clave de idempotencia")),
                ("estado", django_fsm.FSMField(
                    choices=[
                        ("pendiente", "Pendiente"),
                        ("aceptada", "Aceptada"),
                        ("ganada", "Ganada"),
                        ("perdida", "Perdida"),
                        ("anulada", "Anulada"),
                        ("cash_out", "Cash-out"),
                    ],
                    default="aceptada",
                    max_length=50,
                    protected=True,
                    verbose_name="Estado",
                )),
                ("ip_origen", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP de origen")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("cuota", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="apuestas", to="betting.cuota", verbose_name="Cuota seleccionada")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="apuestas", to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={
                "verbose_name": "Apuesta",
                "verbose_name_plural": "Apuestas",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="ApuestaCombinada",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("monto_apostado", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="Monto apostado")),
                ("cuota_total", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="Cuota total (producto)")),
                ("pago_potencial", models.DecimalField(decimal_places=4, max_digits=18, verbose_name="Pago potencial")),
                ("clave_idempotencia", models.UUIDField(unique=True)),
                ("estado", django_fsm.FSMField(
                    choices=[
                        ("pendiente", "Pendiente"),
                        ("aceptada", "Aceptada"),
                        ("ganada", "Ganada"),
                        ("perdida", "Perdida"),
                        ("anulada", "Anulada"),
                        ("cash_out", "Cash-out"),
                    ],
                    default="aceptada",
                    max_length=50,
                    protected=True,
                )),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("selecciones", models.ManyToManyField(related_name="combinadas", to="betting.cuota", verbose_name="Selecciones")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="apuestas_combinadas", to=settings.AUTH_USER_MODEL, verbose_name="Usuario")),
            ],
            options={
                "verbose_name": "Apuesta combinada",
                "verbose_name_plural": "Apuestas combinadas",
            },
        ),
        migrations.CreateModel(
            name="HistorialCuota",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valor_anterior", models.DecimalField(decimal_places=4, max_digits=18)),
                ("valor_nuevo", models.DecimalField(decimal_places=4, max_digits=18)),
                ("registrado_en", models.DateTimeField(auto_now_add=True)),
                ("cuota", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="historial", to="betting.cuota")),
            ],
            options={
                "verbose_name": "Historial de cuota",
                "verbose_name_plural": "Historial de cuotas",
                "ordering": ["-registrado_en"],
            },
        ),
    ]