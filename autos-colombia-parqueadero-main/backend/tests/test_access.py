from fastapi.testclient import TestClient

from app.main import app, seed_initial_data
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


def test_historial_requiere_rol_operativo():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()
    with TestClient(app) as client:
        token = obtener_token(client, "admin", "Admin2026*")
        response = client.get(
            "/api/v1/movimientos/historial",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)
