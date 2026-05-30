"""
Management command: python manage.py seed_usuarios
Crea usuarios de prueba con distintos estados y recarga fichas iniciales.
"""
from datetime import date
from decimal import Decimal
import uuid

from django.core.management.base import BaseCommand

from users.models import Usuario


USUARIOS_SEED = [
    {
        "username": "admin_fairbet",
        "email": "admin@fairbet.edu",
        "dni": "12345678",
        "fecha_nacimiento": date(1985, 3, 10),
        "first_name": "Admin",
        "last_name": "FairBet",
        "estado": "verificado",
        "is_staff": True,
        "is_superuser": True,
        "fichas": Decimal("0"),
    },
    {
        "username": "jugador_verificado",
        "email": "jugador@fairbet.edu",
        "dni": "87654321",
        "fecha_nacimiento": date(1998, 7, 22),
        "first_name": "Carlos",
        "last_name": "Rios",
        "estado": "verificado",
        "fichas": Decimal("1000.0000"),
    },
    {
        "username": "jugador_pendiente",
        "email": "pendiente@fairbet.edu",
        "dni": "11223344",
        "fecha_nacimiento": date(2000, 1, 15),
        "first_name": "Ana",
        "last_name": "Gomez",
        "estado": "pendiente_verificacion",
        "fichas": Decimal("0"),
    },
    {
        "username": "jugador_nuevo",
        "email": "nuevo@fairbet.edu",
        "dni": "55667788",
        "fecha_nacimiento": date(1995, 11, 30),
        "first_name": "Luis",
        "last_name": "Vargas",
        "estado": "verificado",
        "fichas": Decimal("500.0000"),
    },
]

CONTRASENA_DEFECTO = "FairBet2026!"


class Command(BaseCommand):
    help = "Crea usuarios de prueba con fichas iniciales para desarrollo."

    def handle(self, *args, **options):
        from wallet.services import recargar_fichas

        for datos in USUARIOS_SEED:
            fichas = datos.pop("fichas")
            estado = datos.pop("estado")
            is_staff = datos.pop("is_staff", False)
            is_superuser = datos.pop("is_superuser", False)

            if Usuario.objects.filter(username=datos["username"]).exists():
                self.stdout.write(f"  ⚠  Usuario '{datos['username']}' ya existe. Omitido.")
                continue

            usuario = Usuario.objects.create_user(
                password=CONTRASENA_DEFECTO,
                **datos,
            )
            usuario.estado = estado
            usuario.is_staff = is_staff
            usuario.is_superuser = is_superuser
            usuario.save(update_fields=["estado", "is_staff", "is_superuser"])

            if fichas > 0:
                recargar_fichas(usuario, fichas, id_transaccion=uuid.uuid4())

            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓  Usuario '{usuario.username}' creado "
                    f"(estado={estado}, fichas={fichas})."
                )
            )

        self.stdout.write(self.style.SUCCESS("\nSeed de usuarios completado."))
        self.stdout.write(f"Contraseña para todos: {CONTRASENA_DEFECTO}")