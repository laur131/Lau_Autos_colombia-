from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from datetime import timedelta

from .models import Usuario, Celda, Vehiculo, Mensualidad, Tarifa
from .routers import auth, celdas, gestion, movimientos, pagos

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Autos Colombia API — Iteraciones 1, 2 y 3", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def seed_initial_data():
    db = SessionLocal()
    try:
        if not db.query(Usuario).filter(Usuario.username == "admin").first():
            db.add(Usuario(
                documento="10000001",
                nombres="Administrador",
                apellidos="General",
                username="admin",
                password_hash=auth.hash_password("Admin2026*"),
                rol="ADMIN",
                activo=1
            ))
        if not db.query(Usuario).filter(Usuario.username == "operario1").first():
            db.add(Usuario(
                documento="10000002",
                nombres="Carlos",
                apellidos="Operador",
                username="operario1",
                password_hash=auth.hash_password("Oper2026*"),
                rol="OPERARIO",
                activo=1
            ))
        if db.query(Celda).count() == 0:
            for i in range(1, 71):
                db.add(Celda(codigo=f"C-{i:02d}", tipo_vehiculo="CARRO", ubicacion="Nivel 1", estado="DISPONIBLE", activa=1))
            for i in range(1, 11):
                db.add(Celda(codigo=f"M-{i:02d}", tipo_vehiculo="MOTOCICLETA", ubicacion="Zona Motos", estado="DISPONIBLE", activa=1))
        # Tarifas de la mensualidad (Iteración 3)
        if db.query(Tarifa).count() == 0:
            db.add(Tarifa(tipo_vehiculo="CARRO", valor=250000))
            db.add(Tarifa(tipo_vehiculo="MOTOCICLETA", valor=100000))
        db.commit()
        seed_demo_data(db)
    finally:
        db.close()

def seed_demo_data(db):
    """Titulares y vehículos de demostración, solo si la base no tiene titulares.

    ABC123: carro con la mensualidad vencida (para mostrar el pago).
    DEF456: carro vigente que vence en 3 días (aparece en "por vencer").
    MOT12A: moto vigente.
    """
    if db.query(Usuario).filter(Usuario.rol == "TITULAR").first():
        return

    hoy = pagos.hoy_bogota()
    titular_1 = Usuario(documento="1045123456", nombres="María", apellidos="Gómez Restrepo", rol="TITULAR", activo=1)
    titular_2 = Usuario(documento="71234987", nombres="Jorge", apellidos="Mesa Úsuga", rol="TITULAR", activo=1)
    db.add_all([titular_1, titular_2])
    db.flush()

    demo = [
        ("ABC123", "CARRO", "Chevrolet", "Gris", titular_1, hoy - timedelta(days=40), hoy - timedelta(days=10)),
        ("DEF456", "CARRO", "Renault", "Blanco", titular_2, hoy - timedelta(days=27), hoy + timedelta(days=3)),
        ("MOT12A", "MOTOCICLETA", "Yamaha", "Negro", titular_2, hoy - timedelta(days=5), hoy + timedelta(days=25)),
    ]
    for placa, tipo, marca, color, titular, inicio, fin in demo:
        vehiculo = Vehiculo(placa=placa, tipo=tipo, marca=marca, color=color,
                            usuario_titular_id=titular.usuario_id, estado_registro="ACTIVO")
        db.add(vehiculo)
        db.flush()
        db.add(Mensualidad(vehiculo_id=vehiculo.vehiculo_id, fecha_inicio=inicio.isoformat(),
                           fecha_fin=fin.isoformat(), estado_vigencia="ACTIVO"))
    db.commit()


app.include_router(auth.router)
app.include_router(celdas.router)
app.include_router(gestion.router)
app.include_router(movimientos.router)
app.include_router(pagos.router)
app.include_router(pagos.reportes_router)
