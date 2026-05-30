"""
Utilidades compartidas para tests (unittest y pytest).

Garantiza aislamiento: DNI únicos por usuario y recargas sin chocar con
límites diarios de juego responsable (500 fichas por defecto).
"""
from __future__ import annotations

import itertools
import uuid
from datetime import date
from decimal import Decimal

from users.models import LimiteJuego, Usuario
from users.validators import _TABLA_ORE_NUMERICA, _indice_digito_verificador

_dni_secuencia = itertools.count(1_000_001)


def generar_dni_valido(n: int | None = None) -> str:
    """Genera un DNI peruano de 8 dígitos con verificador ORE embebido (7+1)."""
    base = next(_dni_secuencia) if n is None else n
    cuerpo = f"{base % 8_999_999:07d}"
    digito = _TABLA_ORE_NUMERICA[_indice_digito_verificador(cuerpo)]
    return f"{cuerpo}{digito}"


def elevar_limites_recarga(usuario, minimo: Decimal = Decimal("100000.0000")) -> None:
    """Eleva límites de juego para que el setup de tests no dispare LimiteSuperadoError."""
    limite = LimiteJuego.objects.get(usuario=usuario)
    limite.limite_diario = minimo
    limite.limite_semanal = minimo
    limite.limite_mensual = minimo
    limite.save(
        update_fields=["limite_diario", "limite_semanal", "limite_mensual"]
    )


def crear_usuario_verificado(username: str | None = None, **kwargs) -> Usuario:
    """Crea un usuario verificado con DNI único."""
    nombre = username or f"user_{uuid.uuid4().hex[:10]}"
    defaults = {
        "username": nombre,
        "email": f"{nombre}@test.com",
        "password": "pass1234",
        "dni": generar_dni_valido(),
        "fecha_nacimiento": date(1995, 6, 15),
        "estado": "verificado",
    }
    defaults.update(kwargs)
    password = defaults.pop("password")
    usuario = Usuario.objects.create_user(**defaults, password=password)
    return usuario


def fundir_wallet(
    usuario,
    monto: Decimal,
    *,
    id_transaccion=None,
) -> None:
    """Recarga fichas elevando límites primero (evita cascada LimiteSuperadoError)."""
    from wallet.services import recargar_fichas

    techo = max(monto, Decimal("1000.0000"))
    elevar_limites_recarga(usuario, techo)
    recargar_fichas(
        usuario,
        monto,
        id_transaccion=id_transaccion or uuid.uuid4(),
    )
