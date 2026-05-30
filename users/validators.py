from datetime import date
from django.core.exceptions import ValidationError


def validar_dni_peruano(valor: str) -> None:
    if not valor or len(valor) != 8 or not valor.isdigit():
        raise ValidationError(
            "El DNI peruano debe tener exactamente 8 dígitos numéricos."
        )


def validar_mayor_de_edad(fecha_nacimiento: date) -> None:
    hoy = date.today()
    edad = (
        hoy.year - fecha_nacimiento.year
        - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    )
    if edad < 18:
        raise ValidationError(
            "Debes ser mayor de 18 años para registrarte en esta plataforma."
        )