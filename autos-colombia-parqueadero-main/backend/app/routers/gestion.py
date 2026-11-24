
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Usuario, Vehiculo, Mensualidad
from .auth import require_admin


router = APIRouter(
    prefix="/api/v1/gestion",
    tags=["Gestión de Usuarios y Vehículos"]
)


# Datos necesarios para registrar un titular
class TitularCreate(BaseModel):
    documento: str = Field(min_length=5, max_length=20)
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)


# Datos necesarios para registrar un vehículo
class VehiculoCreate(BaseModel):
    placa: str = Field(min_length=5, max_length=10)
    tipo: str
    marca: str = Field(default="", max_length=50)
    color: str = Field(default="", max_length=30)
    usuario_titular_id: int = Field(gt=0)
    fecha_inicio: str
    fecha_fin: str


# Consultar usuarios sin exponer contraseñas ni hashes
@router.get("/usuarios")
def listar_usuarios(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    usuarios = db.query(Usuario).order_by(Usuario.usuario_id).all()

    return [
        {
            "usuario_id": usuario.usuario_id,
            "documento": usuario.documento,
            "nombres": usuario.nombres,
            "apellidos": usuario.apellidos,
            "username": usuario.username,
            "rol": usuario.rol,
            "activo": usuario.activo
        }
        for usuario in usuarios
    ]


# Registrar un titular
@router.post("/titulares", status_code=status.HTTP_201_CREATED)
def registrar_titular(
    payload: TitularCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    documento = payload.documento.strip()
    nombres = payload.nombres.strip()
    apellidos = payload.apellidos.strip()

    if not documento or not nombres or not apellidos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Todos los campos del titular son obligatorios"
        )

    existente = db.query(Usuario).filter(
        Usuario.documento == documento
    ).first()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento ya se encuentra registrado"
        )

    nuevo = Usuario(
        documento=documento,
        nombres=nombres,
        apellidos=apellidos,
        rol="TITULAR",
        activo=1
    )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return {
        "mensaje": "Titular registrado correctamente",
        "titular": {
            "usuario_id": nuevo.usuario_id,
            "documento": nuevo.documento,
            "nombres": nuevo.nombres,
            "apellidos": nuevo.apellidos,
            "rol": nuevo.rol,
            "activo": nuevo.activo
        }
    }


# Activar o desactivar una cuenta
@router.patch("/usuarios/{usuario_id}/estado")
def cambiar_estado_usuario(
    usuario_id: int,
    activo: int,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    if activo not in (0, 1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estado debe ser 1 (activo) o 0 (inactivo)"
        )

    usuario = db.query(Usuario).filter(
        Usuario.usuario_id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )

    if usuario.usuario_id == admin.usuario_id and activo == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta"
        )

    usuario.activo = activo
    db.commit()

    return {
        "mensaje": "Estado actualizado correctamente",
        "usuario_id": usuario_id,
        "activo": activo
    }


# Registrar un vehículo y su mensualidad
@router.post("/vehiculos", status_code=status.HTTP_201_CREATED)
def registrar_vehiculo(
    payload: VehiculoCreate,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):
    placa = payload.placa.strip().upper()
    tipo = payload.tipo.strip().upper()

    if not placa:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La placa es obligatoria"
        )

    if tipo not in ("CARRO", "MOTOCICLETA"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El tipo debe ser CARRO o MOTOCICLETA"
        )

    # Validar formato y coherencia de las fechas
    try:
        fecha_inicio = date.fromisoformat(payload.fecha_inicio)
        fecha_fin = date.fromisoformat(payload.fecha_fin)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Las fechas deben tener el formato AAAA-MM-DD"
        )

    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha de finalización no puede ser anterior a la fecha de inicio"
        )

    # Verificar que exista un titular activo
    titular = db.query(Usuario).filter(
        Usuario.usuario_id == payload.usuario_titular_id,
        Usuario.activo == 1,
        Usuario.rol == "TITULAR"
    ).first()

    if not titular:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Titular no encontrado, inactivo o con un rol incorrecto"
        )

    # Evitar placas duplicadas
    existente = db.query(Vehiculo).filter(
        Vehiculo.placa == placa
    ).first()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La placa ya está registrada"
        )

    vehiculo = Vehiculo(
        placa=placa,
        tipo=tipo,
        marca=payload.marca.strip(),
        color=payload.color.strip(),
        usuario_titular_id=payload.usuario_titular_id,
        estado_registro="ACTIVO"
    )

    db.add(vehiculo)
    db.flush()

    mensualidad = Mensualidad(
        vehiculo_id=vehiculo.vehiculo_id,
        fecha_inicio=fecha_inicio.isoformat(),
        fecha_fin=fecha_fin.isoformat(),
        estado_vigencia="ACTIVO"
    )

    db.add(mensualidad)
    db.commit()
    db.refresh(vehiculo)
    db.refresh(mensualidad)

    return {
        "mensaje": "Vehículo y mensualidad registrados correctamente",
        "vehiculo": {
            "vehiculo_id": vehiculo.vehiculo_id,
            "placa": vehiculo.placa,
            "tipo": vehiculo.tipo,
            "marca": vehiculo.marca,
            "color": vehiculo.color,
            "usuario_titular_id": vehiculo.usuario_titular_id,
            "estado_registro": vehiculo.estado_registro
        },
        "mensualidad": {
            "mensualidad_id": mensualidad.mensualidad_id,
            "fecha_inicio": mensualidad.fecha_inicio,
            "fecha_fin": mensualidad.fecha_fin,
            "estado_vigencia": mensualidad.estado_vigencia
        }
    }
