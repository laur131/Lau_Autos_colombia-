from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, seed_initial_data
from app.routers.auth import ACTIVE_SESSIONS


def login(client, username="admin", password="Admin2026*"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_admin_crea_cuenta_operativa():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()
    with TestClient(app) as client:
        headers = login(client)
        suffix = uuid4().hex[:8]
        response = client.post(
            "/api/v1/auth/cuentas",
            headers=headers,
            json={
                "documento": f"90{suffix}",
                "nombres": "Usuario",
                "apellidos": "De Prueba",
                "username": f"operador_{suffix}",
                "password": "ClavePrueba2026",
                "rol": "OPERARIO",
            },
        )
        assert response.status_code == 201
        assert response.json()["rol"] == "OPERARIO"


def test_admin_crea_y_actualiza_celda_individual():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()
    with TestClient(app) as client:
        headers = login(client)
        code = f"QA-{uuid4().hex[:8].upper()}"
        created = client.post(
            "/api/v1/celdas/",
            headers=headers,
            json={
                "codigo": code,
                "tipo_vehiculo": "CARRO",
                "ubicacion": "Zona de pruebas",
            },
        )
        assert created.status_code == 201

        cell = next(
            item for item in client.get(
                "/api/v1/celdas/", headers=headers
            ).json()["celdas"] if item["codigo"] == code
        )
        updated = client.patch(
            f"/api/v1/celdas/{cell['celda_id']}",
            headers=headers,
            json={"estado": "MANTENIMIENTO"},
        )
        assert updated.status_code == 200
        assert updated.json()["celda"]["estado"] == "MANTENIMIENTO"


def test_operario_no_puede_crear_celdas():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()
    with TestClient(app) as client:
        headers = login(client, "operario1", "Oper2026*")
        response = client.post(
            "/api/v1/celdas/",
            headers=headers,
            json={
                "codigo": f"NO-{uuid4().hex[:8]}",
                "tipo_vehiculo": "CARRO",
                "ubicacion": "Zona de pruebas",
            },
        )
        assert response.status_code == 403
