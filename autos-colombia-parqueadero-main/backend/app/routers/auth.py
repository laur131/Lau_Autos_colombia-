
import hashlib
import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Usuario

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Autenticación y Permisos"]
)

# Sesiones activas del sistema
ACTIVE_SESSIONS = {}

# Configuración del algoritmo de almacenamiento de contraseñas
ITERATIONS = 600_000


def hash_password(raw: str) -> str:
    """Genera un hash seguro de la contraseña con PBKDF2."""

    salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        raw.encode("utf-8"),
        salt.encode("utf-8"),
        ITERATIONS
    ).hex()

    return f"pbkdf2_sha256${ITERATIONS}${salt}${password_hash}"


def verify_password(raw: str, stored_hash: str) -> bool:
    """Verifica contraseñas nuevas y hashes SHA-256 antiguos."""

    if not stored_hash:
        return False

    # Compatibilidad con las contraseñas antiguas
    if "$" not in stored_hash:
        old_hash = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

        return hmac.compare_digest(old_hash, stored_hash)

    try:
        algorithm, iterations, salt, expected_hash = stored_hash.split("$")

        if algorithm != "pbkdf2_sha256":
            return False

        calculated_hash = hashlib.pbkdf2_hmac(
            "sha256",
            raw.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations)
        ).hex()

        return hmac.compare_digest(calculated_hash, expected_hash)

    except (ValueError, TypeError):
        return False


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class CrearCredencialRequest(BaseModel):
    documento: str = Field(min_length=5, max_length=20)
    nombres: str = Field(min_length=2, max_length=100)
    apellidos: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    rol: str


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db)
) -> Usuario:

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sesión requerido"
        )

    token = authorization.removeprefix("Bearer ").strip()
    user_id = ACTIVE_SESSIONS.get(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o expirada"
        )

    user = db.query(Usuario).filter(
        Usuario.usuario_id == user_id,
        Usuario.activo == 1
    ).first()

    if not user:
        ACTIVE_SESSIONS.pop(token, None)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario inactivo o no encontrado"
        )

    return user


def require_admin(
    current_user: Usuario = Depends(get_current_user)
) -> Usuario:

    if current_user.rol != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permiso denegado: se requiere rol ADMIN"
        )

    return current_user


@router.post("/login")
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db)
):

    username = payload.username.strip()

    user = db.query(Usuario).filter(
        Usuario.username == username
    ).first()

    if not user or not verify_password(
        payload.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )

    if user.activo != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta de usuario inactiva"
        )

    if user.rol not in ("ADMIN", "OPERARIO"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol sin acceso al sistema operativo"
        )

    # Actualiza automáticamente los hashes antiguos
    if "$" not in user.password_hash:
        user.password_hash = hash_password(payload.password)
        db.commit()

    token = secrets.token_urlsafe(48)
    ACTIVE_SESSIONS[token] = user.usuario_id

    return {
        "access_token": token,
        "token_type": "bearer",
        "usuario": {
            "usuario_id": user.usuario_id,
            "nombres": user.nombres,
            "apellidos": user.apellidos,
            "username": user.username,
            "rol": user.rol
        }
    }


@router.post("/logout")
def logout(
    authorization: str | None = Header(default=None)
):

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de sesión requerido"
        )

    token = authorization.removeprefix("Bearer ").strip()

    if token not in ACTIVE_SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión inválida o ya cerrada"
        )

    ACTIVE_SESSIONS.pop(token, None)

    return {"mensaje": "Sesión cerrada correctamente"}


@router.post("/cuentas", status_code=status.HTTP_201_CREATED)
def crear_cuenta_operativa(
    payload: CrearCredencialRequest,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_admin)
):

    documento = payload.documento.strip()
    username = payload.username.strip()
    rol = payload.rol.strip().upper()

    if rol not in ("ADMIN", "OPERARIO"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El rol debe ser ADMIN u OPERARIO"
        )

    if db.query(Usuario).filter(
        (Usuario.username == username) |
        (Usuario.documento == documento)
    ).first():

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El usuario o documento ya existe"
        )

    nuevo = Usuario(
        documento=documento,
        nombres=payload.nombres.strip(),
        apellidos=payload.apellidos.strip(),
        username=username,
        password_hash=hash_password(payload.password),
        rol=rol,
        activo=1
    )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo) 

    return {
        "mensaje": "Cuenta creada exitosamente",
        "usuario_id": nuevo.usuario_id,
        "username": nuevo.username,
        "rol": nuevo.rol
    }
