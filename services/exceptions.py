from __future__ import annotations

from datetime import datetime


class ValidacionError(Exception):
    """Errores de negocio por datos inválidos o operación no permitida."""


class IngresoActivoDuplicado(ValidacionError):
    """La placa ya tiene un ingreso activo en el parqueadero."""


class CierreDiarioYaExiste(ValidacionError):
    """Ya existe un cierre de caja para la fecha indicada."""


class CierreNoEncontrado(ValidacionError):
    """No existe el cierre solicitado."""


class CierreSinSnapshot(ValidacionError):
    """El cierre no tiene un snapshot histórico utilizable."""


class ConfiguracionFaltante(ValidacionError):
    """No existe configuración de precio/cupos para el tipo de vehículo."""
