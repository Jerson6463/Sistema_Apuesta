"""
Factories de Factory Boy para datos de prueba aislados.
"""
from datetime import date

import factory
from factory.django import DjangoModelFactory

from users.models import Usuario
from users.validators import _TABLA_ORE_NUMERICA, _indice_digito_verificador


def generar_dni_secuencia(n: int) -> str:
    cuerpo = f"{(1_000_000 + n) % 8_999_999:07d}"
    digito = _TABLA_ORE_NUMERICA[_indice_digito_verificador(cuerpo)]
    return f"{cuerpo}{digito}"


class UsuarioFactory(DjangoModelFactory):
    class Meta:
        model = Usuario
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"factory_user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@factory.test")
    dni = factory.Sequence(generar_dni_secuencia)
    fecha_nacimiento = date(1995, 6, 15)
    estado = "verificado"

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        if not create:
            return
        self.set_password(extracted or "pass1234")
        self.save()
