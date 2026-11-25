
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Movimiento, Vehiculo, Usuario, Celda
from .auth import get_current_user
from .pagos import hoy_bogota, mensualidad_vigente


router = APIRouter(
    prefix="/api/v1/movimientos",
    tags=["Movimientos y Asignación de Celda"]
)


def validar_operario(operario: Usuario):
    if operario.rol not in ("ADMIN", "OPERARIO"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para registrar movimientos"
        )


# Registrar el ingreso de un vehículo
@router.post("/ingresos", status_code=status.HTTP_201_CREATED)
def registrar_ingreso(
    placa: str,
    observacion: str = "",
    celda_id: int | None = None,
    db: Session = Depends(get_db),
    operario: Usuario = Depends(get_current_user)
):
    validar_operario(operario)

    placa = placa.strip().upper()

    if not placa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La placa es obligatoria"
        )

    # Buscar el vehículo
    vehiculo = db.query(Vehiculo).filter(
        Vehiculo.placa == placa
    ).first()

    if not vehiculo or vehiculo.estado_registro != "ACTIVO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vehículo no registrado o inactivo"
        )

    if vehiculo.tipo not in ("CARRO", "MOTOCICLETA"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El vehículo tiene un tipo no válido"
        )

    # Verificar que el titular esté activo
    titular = db.query(Usuario).filter(
        Usuario.usuario_id == vehiculo.usuario_titular_id
    ).first()

    if not titular or titular.activo != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Titular inactivo: acceso denegado"
        )

    # Verificar que la mensualidad esté vigente. La vigencia sale de las
    # mensualidades no anuladas, que se renuevan al registrar un pago.
    # El día del vencimiento el ingreso ya se rechaza.
    if not mensualidad_vigente(db, vehiculo.vehiculo_id, hoy_bogota()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mensualidad vencida: registre el pago para autorizar el ingreso"
        )

    # Evitar que un vehículo tenga dos ingresos abiertos
    movimiento_abierto = db.query(Movimiento).filter(
        Movimiento.vehiculo_id == vehiculo.vehiculo_id,
        Movimiento.fecha_hora_salida.is_(None)
    ).first()

    if movimiento_abierto:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El vehículo ya tiene un ingreso sin registrar su salida"
        )

    # Buscar una celda individual disponible
    consulta_celdas = db.query(Celda).filter(
        Celda.tipo_vehiculo == vehiculo.tipo,
        Celda.activa == 1,
        Celda.estado == "DISPONIBLE"
    )

    if celda_id is not None:
        celda = consulta_celdas.filter(
            Celda.celda_id == celda_id
        ).first()

        if not celda:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La celda seleccionada no está disponible o no corresponde al vehículo"
            )
    else:
        celda = consulta_celdas.order_by(
            Celda.codigo
        ).first()

        if not celda:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No hay celdas disponibles para {vehiculo.tipo}"
            )

    # Registrar el ingreso y ocupar la celda
    movimiento = Movimiento(
        vehiculo_id=vehiculo.vehiculo_id,
        celda_id=celda.celda_id,
        operario_id=operario.usuario_id,
        fecha_hora_entrada=datetime.now().isoformat(),
        observacion_entrada=observacion.strip()
    )

    celda.estado = "OCUPADA"

    try:
        db.add(movimiento)
        db.commit()
        db.refresh(movimiento)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar el ingreso"
        )

    return {
        "mensaje": "Ingreso registrado correctamente",
        "movimiento_id": movimiento.movimiento_id,
        "placa": vehiculo.placa,
        "celda_asignada": celda.codigo,
        "operario_id": operario.usuario_id,
        "fecha_hora_entrada": movimiento.fecha_hora_entrada
    }


# Registrar la salida de un vehículo
@router.post("/{movimiento_id}/salida")
def registrar_salida(
    movimiento_id: int,
    observacion_salida: str = "",
    db: Session = Depends(get_db),
    operario: Usuario = Depends(get_current_user)
):
    validar_operario(operario)

    movimiento = db.query(Movimiento).filter(
        Movimiento.movimiento_id == movimiento_id,
        Movimiento.fecha_hora_salida.is_(None)
    ).first()

    if not movimiento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró un movimiento abierto con ese identificador"
        )

    celda = db.query(Celda).filter(
        Celda.celda_id == movimiento.celda_id
    ).first()

    if not celda:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se encontró la celda asociada al movimiento"
        )

    # Registrar la salida y liberar la misma celda asignada
    fecha_salida = datetime.now().isoformat()

    movimiento.fecha_hora_salida = fecha_salida
    movimiento.operario_cierre_id = operario.usuario_id
    movimiento.observacion_salida = observacion_salida.strip()

    celda.estado = "DISPONIBLE"

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No fue posible registrar la salida"
        )

    return {
        "mensaje": "Salida registrada y celda liberada correctamente",
        "movimiento_id": movimiento.movimiento_id,
        "operario_cierre_id": operario.usuario_id,
        "celda_liberada": celda.codigo,
        "fecha_hora_salida": fecha_salida
    }


# Consultar el historial de movimientos
@router.get("/historial")
def consultar_historial(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    # El historial contiene información operativa y solo debe estar
    # disponible para administradores y operarios autenticados.
    validar_operario(user)

    movimientos = db.query(Movimiento).order_by(
        Movimiento.movimiento_id.desc()
    ).all()

    resultado = []

    for movimiento in movimientos:
        vehiculo = db.query(Vehiculo).filter(
            Vehiculo.vehiculo_id == movimiento.vehiculo_id
        ).first()

        celda = db.query(Celda).filter(
            Celda.celda_id == movimiento.celda_id
        ).first()

        resultado.append({
            "movimiento_id": movimiento.movimiento_id,
            "placa": vehiculo.placa if vehiculo else None,
            "celda": celda.codigo if celda else None,
            "fecha_hora_entrada": movimiento.fecha_hora_entrada,
            "fecha_hora_salida": movimiento.fecha_hora_salida,
            "observacion_entrada": movimiento.observacion_entrada,
            "observacion_salida": movimiento.observacion_salida,
            "operario_id": movimiento.operario_id,
            "operario_cierre_id": movimiento.operario_cierre_id,
            "estado": (
                "ABIERTO"
                if movimiento.fecha_hora_salida is None
                else "CERRADO"
            )
        })

    return resultado

