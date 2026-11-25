"""Pruebas de la Iteración 3: gestión de pagos (casos CP-P01 a CP-P15 del plan de pruebas)."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from random import randint
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app, seed_initial_data
from app.routers.auth import ACTIVE_SESSIONS
from app.routers.pagos import hoy_bogota, sumar_un_mes


def login(client, username="admin", password="Admin2026*"):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def preparar():
    seed_initial_data()
    ACTIVE_SESSIONS.clear()


def nueva_placa(tipo="CARRO"):
    letras = uuid4().hex[:3].upper().replace("0", "A").replace("1", "B")
    letras = "".join(c if c.isalpha() else "X" for c in letras)
    if tipo == "CARRO":
        return f"{letras}{randint(100, 999)}"
    return f"{letras}{randint(10, 99)}Z"


def crear_vehiculo(client, admin, tipo="CARRO", inicio=None, fin=None):
    """Crea un titular y un vehículo con la mensualidad indicada (vencida por defecto)."""
    hoy = hoy_bogota()
    inicio = inicio or hoy - timedelta(days=40)
    fin = fin or hoy - timedelta(days=10)

    titular = client.post(
        "/api/v1/gestion/titulares",
        headers=admin,
        json={"documento": f"8{randint(10**8, 10**9 - 1)}", "nombres": "Titular", "apellidos": "De Prueba"},
    )
    assert titular.status_code == 201
    titular_id = titular.json()["titular"]["usuario_id"]

    placa = nueva_placa(tipo)
    vehiculo = client.post(
        "/api/v1/gestion/vehiculos",
        headers=admin,
        json={
            "placa": placa,
            "tipo": tipo,
            "usuario_titular_id": titular_id,
            "fecha_inicio": inicio.isoformat(),
            "fecha_fin": fin.isoformat(),
        },
    )
    assert vehiculo.status_code == 201
    return placa, titular_id


def pagar(client, headers, placa, metodo="EFECTIVO", referencia=None):
    return client.post(
        "/api/v1/pagos",
        headers=headers,
        json={"placa": placa, "metodo": metodo, "referencia": referencia},
    )


def test_cp_p01_pago_de_carro_vencido():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        operario = login(client, "operario1", "Oper2026*")
        placa, _ = crear_vehiculo(client, admin)

        response = pagar(client, operario, placa)

        assert response.status_code == 201
        comprobante = response.json()["comprobante"]
        hoy = hoy_bogota()
        assert comprobante["valor"] == 250000
        assert comprobante["periodo_inicio"] == hoy.isoformat()
        assert comprobante["periodo_fin"] == sumar_un_mes(hoy).isoformat()
        assert comprobante["numero_comprobante"].startswith("AC-")
        assert len(comprobante["numero_comprobante"]) == 9
        assert comprobante["operario"] == "Carlos Operador"


def test_cp_p02_pago_de_moto():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        placa, _ = crear_vehiculo(client, admin, tipo="MOTOCICLETA")

        response = pagar(client, admin, placa)

        assert response.status_code == 201
        assert response.json()["comprobante"]["valor"] == 100000


def test_cp_p03_pago_adelantado_no_pierde_dias():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        hoy = hoy_bogota()
        vence = hoy + timedelta(days=12)
        placa, _ = crear_vehiculo(client, admin, inicio=hoy - timedelta(days=18), fin=vence)

        response = pagar(client, admin, placa, "TARJETA", "VOUCHER-881")

        assert response.status_code == 201
        comprobante = response.json()["comprobante"]
        assert comprobante["periodo_inicio"] == vence.isoformat()
        assert comprobante["periodo_fin"] == sumar_un_mes(vence).isoformat()


def test_cp_p04_fin_de_mes():
    assert sumar_un_mes(date(2027, 1, 31)) == date(2027, 2, 28)
    assert sumar_un_mes(date(2028, 1, 31)) == date(2028, 2, 29)
    assert sumar_un_mes(date(2026, 12, 15)) == date(2027, 1, 15)
    assert sumar_un_mes(date(2026, 3, 31)) == date(2026, 4, 30)


def test_cp_p05_referencia_obligatoria():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        placa, _ = crear_vehiculo(client, admin)

        for metodo in ("TRANSFERENCIA", "TARJETA"):
            response = pagar(client, admin, placa, metodo, "")
            assert response.status_code == 422

        historial = client.get("/api/v1/pagos", headers=admin, params={"placa": placa})
        assert historial.json() == []


def test_cp_p06_titular_inactivo_rechaza_pago():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        placa, titular_id = crear_vehiculo(client, admin)

        estado = client.patch(
            f"/api/v1/gestion/usuarios/{titular_id}/estado",
            headers=admin,
            params={"activo": 0},
        )
        assert estado.status_code == 200

        response = pagar(client, admin, placa)
        assert response.status_code == 409
        assert "Titular inactivo" in response.json()["detail"]


def test_cp_p07_placa_inexistente():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        response = pagar(client, admin, "NOEXISTE")
        assert response.status_code == 404


def test_cp_p08_ingreso_despues_del_pago():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        operario = login(client, "operario1", "Oper2026*")
        placa, _ = crear_vehiculo(client, admin, tipo="MOTOCICLETA")

        rechazo = client.post("/api/v1/movimientos/ingresos", headers=operario, params={"placa": placa})
        assert rechazo.status_code == 409
        assert "Mensualidad vencida" in rechazo.json()["detail"]

        assert pagar(client, operario, placa).status_code == 201

        ingreso = client.post("/api/v1/movimientos/ingresos", headers=operario, params={"placa": placa})
        assert ingreso.status_code == 201

        # Se deja la celda libre para no afectar otras pruebas
        salida = client.post(
            f"/api/v1/movimientos/{ingreso.json()['movimiento_id']}/salida",
            headers=operario,
        )
        assert salida.status_code == 200


def test_cp_p09_dia_del_vencimiento_bloquea_ingreso():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        hoy = hoy_bogota()
        placa, _ = crear_vehiculo(client, admin, inicio=hoy - timedelta(days=30), fin=hoy)

        estado = client.get(f"/api/v1/pagos/mensualidad/{placa}", headers=admin)
        assert estado.json()["estado"] == "VENCIDA"

        ingreso = client.post("/api/v1/movimientos/ingresos", headers=admin, params={"placa": placa})
        assert ingreso.status_code == 409


def test_estado_por_vencer():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        hoy = hoy_bogota()
        placa, _ = crear_vehiculo(client, admin, inicio=hoy - timedelta(days=27), fin=hoy + timedelta(days=3))

        estado = client.get(f"/api/v1/pagos/mensualidad/{placa}", headers=admin).json()
        assert estado["estado"] == "POR_VENCER"
        assert estado["dias_restantes"] == 3
        assert estado["valor_a_pagar"] == 250000


def test_cp_p10_p11_p12_anulacion_solo_admin_y_ultimo_pago():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        operario = login(client, "operario1", "Oper2026*")
        placa, _ = crear_vehiculo(client, admin)

        primero = pagar(client, operario, placa).json()["comprobante"]
        segundo = pagar(client, operario, placa, "TRANSFERENCIA", "TRF-55021").json()["comprobante"]
        assert segundo["periodo_inicio"] == primero["periodo_fin"]

        # El operario no puede anular
        prohibido = client.post(
            f"/api/v1/pagos/{segundo['pago_id']}/anulacion",
            headers=operario,
            json={"motivo": "Prueba de permisos"},
        )
        assert prohibido.status_code == 403

        # No se puede anular un pago que no es el último
        no_ultimo = client.post(
            f"/api/v1/pagos/{primero['pago_id']}/anulacion",
            headers=admin,
            json={"motivo": "Pago registrado por error"},
        )
        assert no_ultimo.status_code == 409

        # El motivo es obligatorio
        sin_motivo = client.post(
            f"/api/v1/pagos/{segundo['pago_id']}/anulacion",
            headers=admin,
            json={"motivo": ""},
        )
        assert sin_motivo.status_code == 422

        anulado = client.post(
            f"/api/v1/pagos/{segundo['pago_id']}/anulacion",
            headers=admin,
            json={"motivo": "Transferencia rechazada por el banco"},
        )
        assert anulado.status_code == 200
        cuerpo = anulado.json()
        assert cuerpo["pago"]["estado"] == "ANULADO"
        assert cuerpo["pago"]["anulado_por"] == "Administrador General"
        # La vigencia vuelve al fin del primer pago
        assert cuerpo["mensualidad"]["fecha_vencimiento"] == primero["periodo_fin"]

        # El pago anulado sigue visible en el historial
        historial = client.get(
            "/api/v1/pagos", headers=operario, params={"placa": placa, "estado": "ANULADO"}
        ).json()
        assert [p["pago_id"] for p in historial] == [segundo["pago_id"]]


def test_cp_p14_p15_reportes_solo_admin():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        operario = login(client, "operario1", "Oper2026*")
        placa, _ = crear_vehiculo(client, admin, tipo="MOTOCICLETA")

        antes = client.get("/api/v1/reportes/recaudo", headers=admin).json()
        assert pagar(client, admin, placa).status_code == 201
        despues = client.get("/api/v1/reportes/recaudo", headers=admin).json()

        assert despues["total_recaudado"] == antes["total_recaudado"] + 100000
        assert despues["por_metodo"]["EFECTIVO"] == antes["por_metodo"]["EFECTIVO"] + 100000
        assert despues["por_tipo_vehiculo"]["MOTOCICLETA"] == antes["por_tipo_vehiculo"]["MOTOCICLETA"] + 100000

        mora = client.get("/api/v1/reportes/mora", headers=admin)
        assert mora.status_code == 200
        assert placa not in [fila["placa"] for fila in mora.json()]

        assert client.get("/api/v1/reportes/recaudo", headers=operario).status_code == 403
        assert client.get("/api/v1/reportes/mora", headers=operario).status_code == 403


def test_cp_p13_consecutivo_unico_con_pagos_simultaneos():
    preparar()
    with TestClient(app) as client:
        admin = login(client)
        placas = [crear_vehiculo(client, admin, tipo="MOTOCICLETA")[0] for _ in range(6)]

        with ThreadPoolExecutor(max_workers=6) as pool:
            respuestas = list(pool.map(lambda placa: pagar(client, admin, placa), placas))

        assert all(r.status_code == 201 for r in respuestas)
        numeros = [r.json()["comprobante"]["numero_comprobante"] for r in respuestas]
        assert len(set(numeros)) == len(numeros)
