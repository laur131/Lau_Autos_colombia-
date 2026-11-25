import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Mensualidad, Pago, Tarifa, Usuario, Vehiculo
from .auth import get_current_user, require_admin


router = APIRouter(
    prefix="/api/v1/pagos",
    tags=["Gestión de Pagos"]
)

reportes_router = APIRouter(
    prefix="/api/v1/reportes",
    tags=["Reportes de Pagos"]
)

ZONA = ZoneInfo("America/Bogota")
METODOS = ("EFECTIVO", "TRANSFERENCIA", "TARJETA")
DIAS_POR_VENCER = 5


# ---------------------------------------------------------------------------
# Reglas de la mensualidad (también las usa el registro de ingreso)
# ---------------------------------------------------------------------------

def hoy_bogota() -> date:
    return datetime.now(ZONA).date()


def ahora_bogota() -> str:
    return datetime.now(ZONA).replace(microsecond=0).isoformat()


def sumar_un_mes(fecha: date) -> date:
    """Mismo día del mes siguiente; si ese día no existe, el último del mes."""
    anio = fecha.year + (1 if fecha.month == 12 else 0)
    mes = 1 if fecha.month == 12 else fecha.month + 1
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, min(fecha.day, ultimo_dia))


def mensualidades_activas(db: Session, vehiculo_id: int) -> list[Mensualidad]:
    return db.query(Mensualidad).filter(
        Mensualidad.vehiculo_id == vehiculo_id,
        Mensualidad.estado_vigencia == "ACTIVO"
    ).all()


def fecha_vencimiento(db: Session, vehiculo_id: int) -> date | None:
    """Última fecha de vencimiento entre las mensualidades no anuladas."""
    fechas = []
    for mensualidad in mensualidades_activas(db, vehiculo_id):
        try:
            fechas.append(date.fromisoformat(mensualidad.fecha_fin))
        except (ValueError, TypeError):
            continue
    return max(fechas) if fechas else None


def mensualidad_vigente(db: Session, vehiculo_id: int, hoy: date) -> bool:
    """Vigente si alguna mensualidad activa cubre hoy.

    El día del vencimiento ya no está cubierto: fecha_inicio <= hoy < fecha_fin.
    """
    for mensualidad in mensualidades_activas(db, vehiculo_id):
        try:
            inicio = date.fromisoformat(mensualidad.fecha_inicio)
            fin = date.fromisoformat(mensualidad.fecha_fin)
        except (ValueError, TypeError):
            continue
        if inicio <= hoy < fin:
            return True
    return False


def estado_mensualidad(db: Session, vehiculo_id: int, hoy: date) -> dict:
    vencimiento = fecha_vencimiento(db, vehiculo_id)

    if vencimiento is None:
        return {"estado": "SIN_MENSUALIDAD", "fecha_vencimiento": None, "dias_restantes": None}

    dias = (vencimiento - hoy).days

    if not mensualidad_vigente(db, vehiculo_id, hoy):
        estado = "VENCIDA"
    elif dias <= DIAS_POR_VENCER:
        estado = "POR_VENCER"
    else:
        estado = "VIGENTE"

    return {
        "estado": estado,
        "fecha_vencimiento": vencimiento.isoformat(),
        "dias_restantes": dias
    }


def calcular_periodo(db: Session, vehiculo_id: int, hoy: date) -> tuple[date, date]:
    """Si la mensualidad sigue vigente el nuevo periodo empieza en su vencimiento
    (pago adelantado, no se pierden días); si no, empieza hoy."""
    vencimiento = fecha_vencimiento(db, vehiculo_id)

    if vencimiento and mensualidad_vigente(db, vehiculo_id, hoy):
        inicio = vencimiento
    else:
        inicio = hoy

    return inicio, sumar_un_mes(inicio)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def validar_rol_operativo(usuario: Usuario):
    if usuario.rol not in ("ADMIN", "OPERARIO"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para gestionar pagos"
        )


def buscar_vehiculo(db: Session, placa: str) -> Vehiculo:
    placa = placa.strip().upper()
    vehiculo = db.query(Vehiculo).filter(Vehiculo.placa == placa).first()

    if not vehiculo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehículo no registrado"
        )

    return vehiculo


def nombre_completo(db: Session, usuario_id: int | None) -> str | None:
    if usuario_id is None:
        return None
    usuario = db.query(Usuario).filter(Usuario.usuario_id == usuario_id).first()
    return f"{usuario.nombres} {usuario.apellidos}" if usuario else None


def valor_tarifa(db: Session, tipo: str) -> int:
    tarifa = db.query(Tarifa).filter(Tarifa.tipo_vehiculo == tipo).first()

    if not tarifa:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No hay una tarifa configurada para {tipo}"
        )

    return tarifa.valor


def pago_a_dict(db: Session, pago: Pago) -> dict:
    vehiculo = db.query(Vehiculo).filter(Vehiculo.vehiculo_id == pago.vehiculo_id).first()

    return {
        "pago_id": pago.pago_id,
        "numero_comprobante": pago.numero_comprobante,
        "placa": vehiculo.placa if vehiculo else None,
        "tipo_vehiculo": vehiculo.tipo if vehiculo else None,
        "titular": nombre_completo(db, vehiculo.usuario_titular_id) if vehiculo else None,
        "valor": pago.valor,
        "metodo": pago.metodo,
        "referencia": pago.referencia,
        "fecha_hora": pago.fecha_hora,
        "periodo_inicio": pago.periodo_inicio,
        "periodo_fin": pago.periodo_fin,
        "operario_id": pago.operario_id,
        "operario": nombre_completo(db, pago.operario_id),
        "estado": pago.estado,
        "anulado_por": nombre_completo(db, pago.anulado_por_id),
        "fecha_anulacion": pago.fecha_anulacion,
        "motivo_anulacion": pago.motivo_anulacion
    }


# ---------------------------------------------------------------------------
# Endpoints de pagos
# ---------------------------------------------------------------------------

class PagoCreate(BaseModel):
    placa: str = Field(min_length=5, max_length=10)
    metodo: str
    referencia: str | None = Field(default=None, max_length=50)


class AnulacionRequest(BaseModel):
    motivo: str = Field(min_length=5, max_length=200)


@router.get("/tarifas")
def consultar_tarifas(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user)
):
    validar_rol_operativo(usuario)
    tarifas = db.query(Tarifa).order_by(Tarifa.tipo_vehiculo).all()
    return [{"tipo_vehiculo": t.tipo_vehiculo, "valor": t.valor} for t in tarifas]


@router.get("/mensualidad/{placa}")
def consultar_mensualidad(
    placa: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user)
):
    """Estado de la mensualidad y lo que se cobraría si se registra un pago hoy."""
    validar_rol_operativo(usuario)

    vehiculo = buscar_vehiculo(db, placa)
    hoy = hoy_bogota()
    inicio, fin = calcular_periodo(db, vehiculo.vehiculo_id, hoy)

    titular = db.query(Usuario).filter(
        Usuario.usuario_id == vehiculo.usuario_titular_id
    ).first()

    ultimo_pago = db.query(Pago).filter(
        Pago.vehiculo_id == vehiculo.vehiculo_id,
        Pago.estado == "REGISTRADO"
    ).order_by(Pago.pago_id.desc()).first()

    return {
        "placa": vehiculo.placa,
        "tipo_vehiculo": vehiculo.tipo,
        "vehiculo_activo": vehiculo.estado_registro == "ACTIVO",
        "titular": f"{titular.nombres} {titular.apellidos}" if titular else None,
        "titular_activo": bool(titular and titular.activo == 1),
        **estado_mensualidad(db, vehiculo.vehiculo_id, hoy),
        "ultimo_pago": pago_a_dict(db, ultimo_pago) if ultimo_pago else None,
        "valor_a_pagar": valor_tarifa(db, vehiculo.tipo),
        "periodo_propuesto": {
            "inicio": inicio.isoformat(),
            "fin": fin.isoformat()
        }
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def registrar_pago(
    payload: PagoCreate,
    db: Session = Depends(get_db),
    operario: Usuario = Depends(get_current_user)
):
    validar_rol_operativo(operario)

    metodo = payload.metodo.strip().upper()
    referencia = (payload.referencia or "").strip() or None

    if metodo not in METODOS:
        raise HTTPException(
            status_code=422,
            detail="El método de pago debe ser EFECTIVO, TRANSFERENCIA o TARJETA"
        )

    if metodo != "EFECTIVO" and not referencia:
        raise HTTPException(
            status_code=422,
            detail="La referencia es obligatoria para transferencia y tarjeta"
        )

    if metodo == "EFECTIVO":
        referencia = None

    vehiculo = buscar_vehiculo(db, payload.placa)

    if vehiculo.estado_registro != "ACTIVO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehículo inactivo: no se puede registrar el pago"
        )

    titular = db.query(Usuario).filter(
        Usuario.usuario_id == vehiculo.usuario_titular_id
    ).first()

    if not titular or titular.activo != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Titular inactivo: no se puede registrar el pago"
        )

    hoy = hoy_bogota()
    inicio, fin = calcular_periodo(db, vehiculo.vehiculo_id, hoy)
    valor = valor_tarifa(db, vehiculo.tipo)

    # Pago, mensualidad y comprobante se guardan juntos o no se guarda nada
    try:
        mensualidad = Mensualidad(
            vehiculo_id=vehiculo.vehiculo_id,
            fecha_inicio=inicio.isoformat(),
            fecha_fin=fin.isoformat(),
            estado_vigencia="ACTIVO"
        )
        db.add(mensualidad)
        db.flush()

        pago = Pago(
            vehiculo_id=vehiculo.vehiculo_id,
            mensualidad_id=mensualidad.mensualidad_id,
            operario_id=operario.usuario_id,
            valor=valor,
            metodo=metodo,
            referencia=referencia,
            fecha_hora=ahora_bogota(),
            periodo_inicio=inicio.isoformat(),
            periodo_fin=fin.isoformat(),
            estado="REGISTRADO"
        )
        db.add(pago)
        db.flush()

        # El consecutivo sale del identificador del pago: nunca se repite
        pago.numero_comprobante = f"AC-{pago.pago_id:06d}"
        db.commit()
        db.refresh(pago)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar el pago"
        )

    return {
        "mensaje": "Pago registrado correctamente",
        "comprobante": pago_a_dict(db, pago)
    }


@router.get("")
def consultar_pagos(
    placa: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    metodo: str | None = None,
    estado: str | None = None,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user)
):
    validar_rol_operativo(usuario)

    consulta = db.query(Pago)

    if placa and placa.strip():
        vehiculo = db.query(Vehiculo).filter(
            Vehiculo.placa == placa.strip().upper()
        ).first()
        if not vehiculo:
            return []
        consulta = consulta.filter(Pago.vehiculo_id == vehiculo.vehiculo_id)

    if metodo:
        consulta = consulta.filter(Pago.metodo == metodo.strip().upper())

    if estado:
        consulta = consulta.filter(Pago.estado == estado.strip().upper())

    # La fecha se guarda como texto ISO, así que se compara por los 10 primeros caracteres
    if desde:
        consulta = consulta.filter(Pago.fecha_hora >= desde.isoformat())

    if hasta:
        consulta = consulta.filter(Pago.fecha_hora < (hasta + timedelta(days=1)).isoformat())

    pagos = consulta.order_by(Pago.pago_id.desc()).all()
    return [pago_a_dict(db, pago) for pago in pagos]


@router.get("/{pago_id}/comprobante")
def consultar_comprobante(
    pago_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user)
):
    validar_rol_operativo(usuario)

    pago = db.query(Pago).filter(Pago.pago_id == pago_id).first()

    if not pago:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado"
        )

    return pago_a_dict(db, pago)


@router.post("/{pago_id}/anulacion")
def anular_pago(
    pago_id: int,
    payload: AnulacionRequest,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    pago = db.query(Pago).filter(Pago.pago_id == pago_id).first()

    if not pago:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pago no encontrado"
        )

    if pago.estado == "ANULADO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El pago ya está anulado"
        )

    # Solo el último pago vigente del vehículo: así la vigencia se recalcula sin huecos
    ultimo = db.query(Pago).filter(
        Pago.vehiculo_id == pago.vehiculo_id,
        Pago.estado == "REGISTRADO"
    ).order_by(Pago.pago_id.desc()).first()

    if ultimo.pago_id != pago.pago_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Solo se puede anular el último pago registrado del vehículo"
        )

    pago.estado = "ANULADO"
    pago.anulado_por_id = admin.usuario_id
    pago.fecha_anulacion = ahora_bogota()
    pago.motivo_anulacion = payload.motivo.strip()

    if pago.mensualidad_id:
        mensualidad = db.query(Mensualidad).filter(
            Mensualidad.mensualidad_id == pago.mensualidad_id
        ).first()
        if mensualidad:
            mensualidad.estado_vigencia = "ANULADA"

    db.commit()
    db.refresh(pago)

    hoy = hoy_bogota()

    return {
        "mensaje": "Pago anulado; la vigencia se recalculó",
        "pago": pago_a_dict(db, pago),
        "mensualidad": estado_mensualidad(db, pago.vehiculo_id, hoy)
    }


# ---------------------------------------------------------------------------
# Reportes (solo administrador)
# ---------------------------------------------------------------------------

@reportes_router.get("/recaudo")
def reporte_recaudo(
    desde: date | None = None,
    hasta: date | None = None,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    hoy = hoy_bogota()
    desde = desde or hoy.replace(day=1)
    hasta = hasta or hoy

    if hasta < desde:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha final no puede ser anterior a la inicial"
        )

    pagos = db.query(Pago).filter(
        Pago.fecha_hora >= desde.isoformat(),
        Pago.fecha_hora < (hasta + timedelta(days=1)).isoformat()
    ).all()

    validos = [p for p in pagos if p.estado == "REGISTRADO"]
    anulados = [p for p in pagos if p.estado == "ANULADO"]

    por_metodo = {m: 0 for m in METODOS}
    por_tipo = {"CARRO": 0, "MOTOCICLETA": 0}

    for pago in validos:
        por_metodo[pago.metodo] = por_metodo.get(pago.metodo, 0) + pago.valor
        vehiculo = db.query(Vehiculo).filter(Vehiculo.vehiculo_id == pago.vehiculo_id).first()
        if vehiculo:
            por_tipo[vehiculo.tipo] = por_tipo.get(vehiculo.tipo, 0) + pago.valor

    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "total_recaudado": sum(p.valor for p in validos),
        "pagos_registrados": len(validos),
        "pagos_anulados": len(anulados),
        "valor_anulado": sum(p.valor for p in anulados),
        "por_metodo": por_metodo,
        "por_tipo_vehiculo": por_tipo
    }


@reportes_router.get("/mora")
def reporte_mora(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    hoy = hoy_bogota()
    resultado = []

    vehiculos = db.query(Vehiculo).filter(
        Vehiculo.estado_registro == "ACTIVO"
    ).order_by(Vehiculo.placa).all()

    for vehiculo in vehiculos:
        estado = estado_mensualidad(db, vehiculo.vehiculo_id, hoy)
        if estado["estado"] in ("VENCIDA", "POR_VENCER", "SIN_MENSUALIDAD"):
            resultado.append({
                "placa": vehiculo.placa,
                "tipo_vehiculo": vehiculo.tipo,
                "titular": nombre_completo(db, vehiculo.usuario_titular_id),
                **estado
            })

    # Primero los vencidos, luego los que están por vencer
    orden = {"VENCIDA": 0, "SIN_MENSUALIDAD": 1, "POR_VENCER": 2}
    resultado.sort(key=lambda fila: (orden[fila["estado"]], fila["fecha_vencimiento"] or ""))
    return resultado
