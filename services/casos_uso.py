from __future__ import annotations

from datetime import datetime

from domain import enums, reglas
from domain.enums import EstadoReporte
from domain.entities import ConfiguracionVehiculo
from infrastructure import repos
from infrastructure.archivos import generar_cierre_caja, generar_ticket
from services.exceptions import (
    CierreDiarioYaExiste,
    CierreNoEncontrado,
    CierreSinSnapshot,
    ConfiguracionFaltante,
    IngresoActivoDuplicado,
    ValidacionError,
)

_ingreso_repo = repos.IngresoRepo()
_mensualidad_repo = repos.MensualidadRepo()
_config_repo = repos.ConfiguracionRepo()
_cierre_repo = repos.CierreRepo()


def _validar_placa(placa: str) -> str:
    placa = (placa or "").strip().upper()
    if not placa:
        raise ValidacionError("La placa es obligatoria.")
    return placa


def registrar_entrada(placa, tipo, marca, propietario, telefono):
    placa = _validar_placa(placa)
    if not tipo:
        raise ValidacionError("Debe seleccionar un tipo de vehículo.")
    if _ingreso_repo.existe_en_sitio(placa):
        raise IngresoActivoDuplicado(
            f"La placa '{placa}' ya tiene un ingreso activo en el parqueadero."
        )
    try:
        return _ingreso_repo.registrar_entrada(
            placa, tipo, marca or "", propietario or "", telefono or ""
        )
    except repos.IngresoActivoDuplicadoPersistenceError as exc:
        raise IngresoActivoDuplicado(
            f"La placa '{placa}' ya tiene un ingreso activo en el parqueadero."
        ) from exc


def buscar_placa(placa):
    return _ingreso_repo.buscar_en_sitio(_validar_placa(placa))


def previsualizar_cobro(placa) -> dict:
    ingreso = _ingreso_repo.buscar_en_sitio(_validar_placa(placa))
    if not ingreso:
        raise ValidacionError("Vehículo no encontrado en sitio.")
    cfg = _config_repo.obtener(ingreso.tipo)
    tarifa = cfg.tarifa_hora if cfg else 0.0
    ahora = datetime.now()
    horas = reglas.calcular_horas(ingreso.entrada, ahora)
    total = horas * tarifa
    return {
        "id": ingreso.id,
        "placa": ingreso.placa,
        "tipo": ingreso.tipo,
        "marca": ingreso.marca,
        "entrada": ingreso.entrada.strftime("%Y-%m-%d %H:%M:%S"),
        "horas": horas,
        "tarifa": tarifa,
        "total": total,
    }


def cobrar_salida(placa) -> dict:
    cobro = previsualizar_cobro(placa)
    salida = datetime.now()
    _ingreso_repo.finalizar(cobro["id"], salida, cobro["total"])
    ticket = generar_ticket(
        cobro["placa"], cobro["tipo"], cobro["entrada"], salida.strftime("%Y-%m-%d %H:%M:%S"),
        cobro["horas"], cobro["total"],
    )
    return {**cobro, "ticket": str(ticket)}


def _precio_mensual(tipo: str) -> float:
    cfg = _config_repo.obtener(tipo)
    if not cfg:
        raise ConfiguracionFaltante(
            f"No hay configuración de precio para '{tipo}'."
        )
    return float(cfg.tarifa_mes)


def registrar_mensualidad(placa, marca, propietario, telefono, tipo) -> dict:
    placa = _validar_placa(placa)
    if tipo not in {t.value for t in enums.TIPOS_MENSUALES}:
        raise ValidacionError("Tipo de mensualidad no válido.")
    precio = _precio_mensual(tipo)
    ahora = datetime.now()
    venc = reglas.fecha_vencimiento(ahora)
    _mensualidad_repo.registrar(placa, marca or "", propietario or "", telefono or "", tipo, ahora, venc)
    _ingreso_repo.registrar_pago_mes(placa, marca or "", propietario or "", tipo, ahora, precio)
    return {"placa": placa, "precio": precio, "vencimiento": venc.strftime("%Y-%m-%d %H:%M:%S")}


def renovar_mensualidad(placa) -> dict:
    placa = _validar_placa(placa)
    m = _mensualidad_repo.obtener_por_placa(placa)
    if not m:
        raise ValidacionError("No existe mensualidad para esa placa.")
    precio = _precio_mensual(m.tipo)
    ahora = datetime.now()
    base = max(ahora, m.fecha_vencimiento)
    nueva_f = reglas.fecha_vencimiento(base)
    _mensualidad_repo.renovar(placa, ahora, nueva_f)
    _ingreso_repo.registrar_pago_mes(placa, m.marca, m.propietario, enums.TipoPago.RENOVACION_MES.value, ahora, precio)
    return {"placa": placa, "precio": precio, "vencimiento": nueva_f.strftime("%Y-%m-%d %H:%M:%S")}


def eliminar_mensualidad(placa) -> None:
    _mensualidad_repo.eliminar(_validar_placa(placa))


def listar_mensualidades() -> list[dict]:
    hoy = datetime.now()
    resultado = []
    for m in _mensualidad_repo.listar():
        tag = reglas.clasificar_vencimiento(m.fecha_vencimiento, hoy)
        resultado.append(
            {
                "placa": m.placa,
                "marca": m.marca,
                "propietario": m.propietario,
                "telefono": m.telefono,
                "vencimiento": m.fecha_vencimiento.strftime("%Y-%m-%d %H:%M:%S"),
                "tipo": m.tipo,
                "tag": tag,
            }
        )
    return resultado


def listar_en_sitio() -> list[dict]:
    return [
        {
            "placa": i.placa,
            "marca": i.marca,
            "tipo": i.tipo,
            "propietario": i.propietario,
            "entrada": i.entrada.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for i in _ingreso_repo.listar_en_sitio()
    ]


def obtener_resumen_cierre() -> dict:
    hoy = datetime.now().strftime("%Y-%m-%d")
    resumen = _ingreso_repo.resumen_dia(hoy)
    en_sitio = _ingreso_repo.listar_en_sitio()
    inventario = [(i.placa, i.tipo, i.entrada.strftime("%Y-%m-%d %H:%M:%S")) for i in en_sitio]
    total = resumen["horas_total"] + resumen["mes_total"]
    return {
        **resumen,
        "fecha": hoy,
        "total": total,
        "vehiculos_salida": resumen["horas_count"] + resumen["mes_count"],
        "inventario": inventario,
    }


def _marcar_reporte_generado(cierre_id: int) -> None:
    actualizado = _cierre_repo.actualizar_estado_reporte_condicional(
        cierre_id,
        EstadoReporte.GENERADO,
    )
    if actualizado:
        return
    cierre_actual = _cierre_repo.obtener_por_id(cierre_id)
    if cierre_actual and cierre_actual.estado_reporte == EstadoReporte.GENERADO:
        return
    raise ValidacionError(
        f"El reporte del cierre '{cierre_id}' fue publicado, "
        "pero no se pudo confirmar el estado GENERADO en SQLite "
        "(no se pudo confirmar la operación)."
    )


def _marcar_reporte_error(cierre_id: int, error_original: Exception) -> None:
    actualizado = _cierre_repo.actualizar_estado_reporte_condicional(
        cierre_id,
        EstadoReporte.ERROR,
    )
    if actualizado:
        return
    cierre_actual = _cierre_repo.obtener_por_id(cierre_id)
    if cierre_actual and cierre_actual.estado_reporte == EstadoReporte.GENERADO:
        return
    raise ValidacionError(
        f"No se pudo persistir el estado ERROR del cierre '{cierre_id}'."
    )


def confirmar_cierre() -> dict:
    resumen = obtener_resumen_cierre()
    fecha = resumen["fecha"]
    if _cierre_repo.existe_por_fecha(fecha):
        raise CierreDiarioYaExiste(f"Ya existe un cierre para la fecha '{fecha}'.")
    try:
        cierre = _cierre_repo.registrar(
            fecha,
            resumen["total"],
            resumen["vehiculos_salida"],
            total_horas=resumen["horas_total"],
            cantidad_horas=resumen["horas_count"],
            total_mensualidades=resumen["mes_total"],
            cantidad_mensualidades=resumen["mes_count"],
            inventario_snapshot=resumen["inventario"],
            estado_reporte=EstadoReporte.PENDIENTE,
        )
    except repos.CierreDiarioDuplicadoPersistenceError as exc:
        raise CierreDiarioYaExiste(f"Ya existe un cierre para la fecha '{fecha}'.") from exc
    try:
        generar_cierre_caja(
            resumen["fecha"],
            resumen["horas_total"],
            resumen["horas_count"],
            resumen["mes_total"],
            resumen["mes_count"],
            resumen["total"],
            resumen["inventario"],
        )
    except Exception as error_generacion:
        try:
            _marcar_reporte_error(cierre.id, error_generacion)
        except Exception as error_estado:
            error_generacion.add_note(
                f"No se pudo persistir ERROR para el cierre {cierre.id}: {error_estado}"
            )
        raise
    _marcar_reporte_generado(cierre.id)
    return resumen


def _validar_cierre_recuperable(cierre) -> None:
    campos_obligatorios = (
        "fecha",
        "total",
        "vehiculos_salida",
        "total_horas",
        "cantidad_horas",
        "total_mensualidades",
        "cantidad_mensualidades",
        "inventario_snapshot",
    )
    if any(getattr(cierre, campo) is None for campo in campos_obligatorios):
        raise CierreSinSnapshot(
            f"El cierre '{cierre.id}' no tiene datos históricos completos."
        )
    if not isinstance(cierre.inventario_snapshot, list):
        raise CierreSinSnapshot(
            f"El snapshot del cierre '{cierre.id}' no tiene un formato válido."
        )
    for item in cierre.inventario_snapshot:
        if (
            not isinstance(item, (tuple, list))
            or len(item) != 3
            or any(not isinstance(valor, str) or not valor for valor in item)
        ):
            raise CierreSinSnapshot(
                f"El snapshot del cierre '{cierre.id}' no tiene un formato válido."
            )


def recuperar_reporte_cierre(cierre_id: int):
    try:
        cierre = _cierre_repo.obtener_por_id(cierre_id)
    except repos.CierreSnapshotInvalidoPersistenceError as exc:
        raise CierreSinSnapshot(
            f"El cierre '{cierre_id}' no tiene un snapshot válido."
        ) from exc
    if not cierre:
        raise CierreNoEncontrado(f"No existe el cierre '{cierre_id}'.")
    if cierre.estado_reporte not in (EstadoReporte.PENDIENTE, EstadoReporte.ERROR):
        raise ValidacionError(
            f"El cierre '{cierre_id}' no está disponible para recuperación."
        )
    _validar_cierre_recuperable(cierre)
    try:
        archivo = generar_cierre_caja(
            cierre.fecha,
            cierre.total_horas,
            cierre.cantidad_horas,
            cierre.total_mensualidades,
            cierre.cantidad_mensualidades,
            cierre.total,
            cierre.inventario_snapshot,
        )
    except Exception as error_generacion:
        try:
            _marcar_reporte_error(cierre.id, error_generacion)
        except Exception as error_estado:
            error_generacion.add_note(
                f"No se pudo persistir ERROR para el cierre {cierre.id}: {error_estado}"
            )
        raise
    _marcar_reporte_generado(cierre.id)
    return archivo


def ventas_hoy() -> float:
    return _ingreso_repo.sumar_valor_pagado_hoy(datetime.now().strftime("%Y-%m-%d"))


def obtener_configuracion() -> list[ConfiguracionVehiculo]:
    return _config_repo.obtener_todas()


def guardar_configuracion(tipo, tarifa_hora, tarifa_mes, cupos) -> None:
    if not tipo:
        raise ValidacionError("Debe seleccionar un tipo de vehículo.")
    try:
        th = float(tarifa_hora)
        tm = float(tarifa_mes)
        cup = int(cupos)
    except (TypeError, ValueError):
        raise ValidacionError("Los valores de precio y cupo deben ser numéricos.")
    if th < 0 or tm < 0 or cup < 0:
        raise ValidacionError("Los valores no pueden ser negativos.")
    _config_repo.guardar(ConfiguracionVehiculo(tipo, th, tm, cup))


def calcular_ocupacion() -> dict:
    """Conteo de ocupación real para las tarjetas del dashboard."""
    conf = {c.tipo: c for c in _config_repo.obtener_todas()}
    ocupacion_hora = _ingreso_repo.contar_en_sitio_por_tipo()
    mensuales = _mensualidad_repo.listar()
    ocupacion_mes = {}
    for m in mensuales:
        ocupacion_mes[m.tipo] = ocupacion_mes.get(m.tipo, 0) + 1

    def ocupado(tipo):
        return ocupacion_hora.get(tipo, 0)

    def cupos(tipo):
        return conf.get(tipo).cupos_totales if conf.get(tipo) else 0

    return {
        "moto_hora": (ocupado("Moto Hora"), cupos("Moto Hora")),
        "moto_mes": (ocupacion_mes.get("Moto Mes", 0), cupos("Moto Mes")),
        "otros": (
            ocupado("Carro") + ocupado("Camion") + ocupado("Autobus"),
            cupos("Carro") + cupos("Camion") + cupos("Autobus"),
        ),
        "alertas_mes": sum(
            1
            for m in mensuales
            if reglas.clasificar_vencimiento(m.fecha_vencimiento, datetime.now()) != "ok"
        ),
    }
