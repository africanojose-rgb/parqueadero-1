from __future__ import annotations

from datetime import datetime


class ValidacionError(Exception):
    """Errores de negocio por datos inválidos o operación no permitida."""


class ConfiguracionFaltante(ValidacionError):
    """No existe configuración de precio/cupos para el tipo de vehículo."""
