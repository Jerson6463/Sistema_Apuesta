from datetime import date

from django.core.exceptions import ValidationError

# Algoritmo RENIEC — Módulo 11 con tablas ORE (numérica y alfabética).
_FACTORES_DNI = (3, 2, 7, 6, 5, 4, 3, 2)
_TABLA_ORE_NUMERICA = (6, 7, 8, 9, 0, 1, 1, 2, 3, 4, 5)
_TABLA_ORE_LETRAS = ("K", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J")


def _indice_digito_verificador(digitos: str) -> int:
    """Índice ORE (0-10) a partir de los 8 dígitos del documento."""
    nums = [int(d) for d in digitos]
    factores = _FACTORES_DNI[: len(nums)]
    suma = sum(n * f for n, f in zip(nums, factores))
    clave = 11 - (suma % 11)
    return 0 if clave == 11 else clave


def es_dni_peruano_valido(dni: str, digito_verificador: str) -> bool:
    """
    Función pura: valida un DNI peruano con el algoritmo Módulo 11 de RENIEC.

    Recibe los 8 dígitos del documento y el dígito verificador (numérico o letra
    ORE impresa en la esquina del DNI físico). No depende de Django ni de I/O.


    Returns:
        True si el verificador coincide con el cálculo RENIEC; False en caso contrario.
    """
    if len(dni) != 8 or not dni.isdigit():
        return False

    verificador = str(digito_verificador).strip().upper()
    if len(verificador) != 1:
        return False

    indice = _indice_digito_verificador(dni)

    if verificador.isdigit():
        return _TABLA_ORE_NUMERICA[indice] == int(verificador)

    if verificador.isalpha():
        return _TABLA_ORE_LETRAS[indice] == verificador

    return False


def calcular_digito_verificador_dni(dni: str) -> int:
    """Calcula el dígito verificador numérico ORE para un DNI de 8 dígitos."""
    if len(dni) != 8 or not dni.isdigit():
        raise ValueError("El DNI debe tener exactamente 8 dígitos numéricos.")
    return _TABLA_ORE_NUMERICA[_indice_digito_verificador(dni)]


def calcular_digito_verificador_dni_letra(dni: str) -> str:
    """Calcula el dígito verificador alfabético ORE para un DNI de 8 dígitos."""
    if len(dni) != 8 or not dni.isdigit():
        raise ValueError("El DNI debe tener exactamente 8 dígitos numéricos.")
    return _TABLA_ORE_LETRAS[_indice_digito_verificador(dni)]


def validar_digito_verificador_dni(dni_completo: str) -> bool:
    """Valida un DNI de 9 caracteres: 8 dígitos + verificador (numérico o letra ORE)."""
    if len(dni_completo) != 9:
        return False
    return es_dni_peruano_valido(dni_completo[:8], dni_completo[8])


def validar_dni_peruano(valor: str) -> None:
    """Validador Django del campo `dni`: formato de 8 dígitos numéricos."""
    if not valor or len(valor) != 8 or not valor.isdigit():
        raise ValidationError(
            "El DNI peruano debe tener exactamente 8 dígitos numéricos."
        )


def validar_dni_con_verificador(dni: str, digito_verificador: str) -> None:
    """
    Validación KYC en registro: 8 dígitos del documento + dígito verificador
    impreso en el DNI físico (numérico ORE o letra ORE).
    """
    validar_dni_peruano(dni)

    verificador = str(digito_verificador or "").strip()
    if not verificador:
        raise ValidationError("El dígito verificador es obligatorio.")
    if len(verificador) != 1:
        raise ValidationError(
            "El dígito verificador debe ser un carácter (0-9 o letra ORE: K, A…J)."
        )

    if not es_dni_peruano_valido(dni, verificador):
        raise ValidationError(
            "El dígito verificador no coincide con el número de DNI ingresado."
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
