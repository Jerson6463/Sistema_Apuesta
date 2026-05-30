class EventoNoDisponibleError(Exception):
    """El evento no está en estado que permita apuestas simples (debe ser PROGRAMADO)."""


class UsuarioNoHabilitadoError(Exception):
    """El usuario no está verificado o está autoexcluido/bloqueado."""


class SaldoInsuficienteApuestaError(Exception):
    """El usuario no tiene saldo disponible para el monto de la apuesta."""


class MontoFueraDeRangoError(Exception):
    """El monto de la apuesta está fuera del rango min/max del mercado."""


class MercadoCerradoError(Exception):
    """El mercado no está abierto para recibir apuestas."""


class ApuestaYaLiquidadaError(Exception):
    """Se intenta liquidar una apuesta que ya fue procesada."""


class SeleccionMutuamenteExcluyenteError(Exception):
    """Selecciones incompatibles en una apuesta combinada (mismo mercado)."""


class CashOutNoDisponibleError(Exception):
    """No es posible hacer cash-out en el estado actual de la apuesta."""