"""
Fixtures globales de pytest reutilizables en todas las apps.
"""
import uuid
from decimal import Decimal

import pytest
from django.utils import timezone

from test_support import crear_usuario_verificado, fundir_wallet


@pytest.fixture
def usuario_verificado(db):
    return crear_usuario_verificado(username=f"fixture_{uuid.uuid4().hex[:8]}")


@pytest.fixture
def usuario_con_fichas(usuario_verificado):
    fundir_wallet(usuario_verificado, Decimal("1000.0000"))
    return usuario_verificado


@pytest.fixture
def evento_programado(db):
    from betting.models import Evento, EstadoEvento

    return Evento.objects.create(
        nombre="Peru vs Brasil - Fixture",
        deporte="futbol",
        equipo_local="Peru",
        equipo_visitante="Brasil",
        fecha_inicio=timezone.now() + timezone.timedelta(hours=3),
        estado=EstadoEvento.PROGRAMADO,
    )


@pytest.fixture
def mercado_abierto(evento_programado):
    from betting.models import Mercado, TipoMercado, EstadoMercado

    return Mercado.objects.create(
        evento=evento_programado,
        tipo=TipoMercado.UNO_X_DOS,
        estado=EstadoMercado.ABIERTO,
        monto_minimo=Decimal("1.0000"),
        monto_maximo=Decimal("5000.0000"),
    )


@pytest.fixture
def cuota_local(mercado_abierto):
    from betting.models import Cuota

    return Cuota.objects.create(
        mercado=mercado_abierto,
        seleccion="local",
        valor=Decimal("2.5000"),
        activa=True,
    )


@pytest.fixture
def apuesta_aceptada(usuario_con_fichas, cuota_local):
    from betting.services import crear_apuesta

    return crear_apuesta(
        usuario=usuario_con_fichas,
        cuota=cuota_local,
        monto=Decimal("100.0000"),
        clave_idempotencia=uuid.uuid4(),
    )
