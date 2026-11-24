
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Celda, Usuario
from .auth import get_current_user, require_admin


router = APIRouter(
    prefix="/api/v1/celdas",
    tags=["Administración de Celdas Individuales"]
)


TIPOS_VALIDOS = ("CARRO", "MOTOCICLETA")
ESTADOS_VALIDOS = ("DISPONIBLE", "MANTENIMIENTO")


class CeldaCreate(BaseModel):
    codigo: str = Field(min_length=2, max_length=20)
    tipo_vehiculo: str
    ubicacion: str = Field(default="Zona General", max_length=100)


class CeldaUpdate(BaseModel):
    tipo_vehiculo: str | None = None
    ubicacion: str | None = None
    estado: str | None = None
    activa: int | None = None


def convertir_celda(celda: Celda):
    return {
        "celda_id": celda.celda_id,
        "codigo": celda.codigo,
        "tipo_vehiculo": celda.tipo_vehiculo,
        "ubicacion": celda.ubicacion,
        "estado": celda.estado,
        "activa": celda.activa
    }


# Consultar las celdas y el resumen del aforo
@router.get("/")
def listar_celdas(
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    celdas = db.query(Celda).order_by(Celda.codigo).all()

    activas = [celda for celda in celdas if celda.activa == 1]

    total_carros = sum(
        1 for celda in activas
        if celda.tipo_vehiculo == "CARRO"
    )

    ocupados_carros = sum(
        1 for celda in activas
        if celda.tipo_vehiculo == "CARRO"
        and celda.estado == "OCUPADA"
    )

    total_motos = sum(
        1 for celda in activas
        if celda.tipo_vehiculo == "MOTOCICLETA"
    )

    ocupados_motos = sum(
        1 for celda in activas
        if celda.tipo_vehiculo == "MOTOCICLETA"
        and celda.estado == "OCUPADA"
    )

    return {
        "resumen_aforo": {
            "carros": {
                "ocupadas": ocupados_carros,
                "disponibles": total_carros - ocupados_carros,
                "capacidad": total_carros
            },
            "motocicletas": {
                "ocupadas": ocupados_motos,
                "disponibles": total_motos - ocupados_motos,
                "capacidad": total_motos
            }
        },
        "celdas": [
            convertir_celda(celda)
            for celda in celdas
        ]
    }


# Crear una celda individual
@router.post("/", status_code=status.HTTP_201_CREATED)
def crear_celda_individual(
    payload: CeldaCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    codigo = payload.codigo.strip().upper()
    tipo = payload.tipo_vehiculo.strip().upper()
    ubicacion = payload.ubicacion.strip()

    if not codigo or not ubicacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El código y la ubicación son obligatorios"
        )

    if tipo not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tipo debe ser CARRO o MOTOCICLETA"
        )

    existente = db.query(Celda).filter(
        Celda.codigo == codigo
    ).first()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una celda con el código {codigo}"
        )

    celda = Celda(
        codigo=codigo,
        tipo_vehiculo=tipo,
        ubicacion=ubicacion,
        estado="DISPONIBLE",
        activa=1
    )

    db.add(celda)
    db.commit()
    db.refresh(celda)

    return {
        "mensaje": "Celda individual creada correctamente",
        "celda": convertir_celda(celda)
    }


# Modificar una celda individual
@router.patch("/{celda_id}")
def modificar_celda_individual(
    celda_id: int,
    payload: CeldaUpdate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    celda = db.query(Celda).filter(
        Celda.celda_id == celda_id
    ).first()

    if not celda:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Celda no encontrada"
        )

    if all(
        valor is None
        for valor in (
            payload.tipo_vehiculo,
            payload.ubicacion,
            payload.estado,
            payload.activa
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes indicar al menos un dato para modificar"
        )

    nuevo_tipo = None
    if payload.tipo_vehiculo is not None:
        nuevo_tipo = payload.tipo_vehiculo.strip().upper()

        if nuevo_tipo not in TIPOS_VALIDOS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El tipo debe ser CARRO o MOTOCICLETA"
            )

    nueva_ubicacion = None
    if payload.ubicacion is not None:
        nueva_ubicacion = payload.ubicacion.strip()

        if not nueva_ubicacion:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La ubicación no puede estar vacía"
            )

    nuevo_estado = None
    if payload.estado is not None:
        nuevo_estado = payload.estado.strip().upper()

        if nuevo_estado not in ESTADOS_VALIDOS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El estado permitido es DISPONIBLE o MANTENIMIENTO"
            )

    if payload.activa is not None and payload.activa not in (0, 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El campo activa debe ser 1 o 0"
        )

    # Una celda ocupada no puede modificarse de forma que
    # afecte el vehículo que tiene asignado.
    if celda.estado == "OCUPADA":
        if (
            payload.activa == 0
            or nuevo_estado == "MANTENIMIENTO"
            or nuevo_tipo is not None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede desactivar, cambiar de tipo o poner en mantenimiento una celda ocupada"
            )

    # No se puede habilitar una celda que siga en mantenimiento
    if (
        payload.activa == 1
        and celda.estado == "MANTENIMIENTO"
        and nuevo_estado != "DISPONIBLE"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Primero debes cambiar el estado de la celda a DISPONIBLE"
        )

    # No se puede poner disponible una celda que esté desactivada
    if (
        nuevo_estado == "DISPONIBLE"
        and celda.activa == 0
        and payload.activa != 1
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Primero debes activar la celda"
        )

    if nuevo_tipo is not None:
        celda.tipo_vehiculo = nuevo_tipo

    if nueva_ubicacion is not None:
        celda.ubicacion = nueva_ubicacion

    if nuevo_estado is not None:
        celda.estado = nuevo_estado

    if payload.activa is not None:
        celda.activa = payload.activa

    db.commit()
    db.refresh(celda)

    return {
        "mensaje": "Celda actualizada correctamente",
        "celda": convertir_celda(celda)
    }
