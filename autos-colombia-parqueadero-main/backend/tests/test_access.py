from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, seed_initial_data
from app.database import SessionLocal
from app.models import Usuario
from app.routers.auth import ACTIVE_SESSIONS


def obtener_token(client, username, password):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_rutas_protegidas_requieren_autenticacion():
    seed_initial_data()
    with TestClient(app) as client:
        response = client.get("/api/v1/celdas/")
        assert response.status_code == 401


def test_login_admin_y_operario():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()
    with TestClient(app) as client:
        admin_token = obtener_token(client, "admin", "Admin2026*")
        operario_token = obtener_token(client, "operario1", "Oper2026*")

        assert admin_token
        assert operario_token
        assert admin_token != operario_token


def test_operario_no_puede_administrar_celdas():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()
    with TestClient(app) as client:
        token = obtener_token(client, "operario1", "Oper2026*")
        response = client.post(
            "/api/v1/celdas/",
            json={
                "codigo": "PRUEBA-OPERARIO",
                "tipo_vehiculo": "CARRO",
                "ubicacion": "Zona de pruebas",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


def test_login_rechaza_credenciales_incorrectas():
    seed_initial_data()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "clave-incorrecta"},
        )
        assert response.status_code == 401


def test_historial_solo_permite_admin_y_operario():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()

    db = SessionLocal()
    try:
        documento = "TIT" + uuid4().hex[:8]
        titular = Usuario(
            documento=documento,
            nombres="Titular",
            apellidos="De Prueba",
            username=None,
            password_hash=None,
            rol="TITULAR",
            activo=1,
        )
        db.add(titular)
        db.commit()
        db.refresh(titular)
        titular_id = titular.usuario_id
    finally:
        db.close()

    token_titular = "token-titular-prueba"
    ACTIVE_SESSIONS[token_titular] = titular_id

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/movimientos/historial",
            headers={"Authorization": f"Bearer {token_titular}"},
        )
        assert response.status_code == 403

        token_admin = obtener_token(client, "admin", "Admin2026*")
        admin_response = client.get(
            "/api/v1/movimientos/historial",
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert admin_response.status_code == 200
        assert isinstance(admin_response.json(), list)

    ACTIVE_SESSIONS.pop(token_titular, None)
