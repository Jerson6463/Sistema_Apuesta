class SaldoInsuficienteError(Exception):
    """Se lanza cuando el usuario no tiene saldo disponible suficiente."""


class LimiteSuperadoError(Exception):
    """Se lanza cuando la operación supera el límite de juego configurado."""


class TransaccionDuplicadaError(Exception):
    """Se lanza cuando se intenta registrar una transacción ya procesada."""


class CuentaNoVerificadaError(Exception):
    """Se lanza cuando el usuario no tiene cuenta verificada para operar."""
