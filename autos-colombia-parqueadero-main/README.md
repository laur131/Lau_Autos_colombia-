# Autos Colombia | Sistema de gestión de parqueadero

Prototipo académico desarrollado con Angular, Python, FastAPI, SQLAlchemy y SQLite para administrar el acceso de vehículos y la operación de un parqueadero.

## Funcionalidades

### Autenticación y perfiles
- Inicio y cierre de sesión con credenciales.
- Roles diferenciados: ADMIN y OPERARIO.
- El administrador puede crear cuentas operativas, asignar el rol y activar o desactivar usuarios.
- Las contraseñas se almacenan mediante PBKDF2-HMAC-SHA256; no se guardan en texto plano.

### Administración de usuarios y vehículos
- Registro de titulares.
- Registro de vehículos asociados a un titular.
- Validación de placas duplicadas, titular activo y fechas de mensualidad.
- Consulta y control del estado de usuarios.

### Administración de celdas individuales
- Inventario de celdas identificadas por código.
- Clasificación por tipo de vehículo: CARRO o MOTOCICLETA.
- Registro de ubicación, estado y activación.
- Creación y actualización de celdas restringidas al administrador.
- Una celda ocupada no puede enviarse a mantenimiento.

### Operación del parqueadero
- Registro de ingreso y salida.
- Validación de vehículo activo y mensualidad vigente.
- Asignación de una celda disponible compatible con el vehículo.
- Liberación de la misma celda al registrar la salida.
- Historial de movimientos para administradores y operarios.
- Resumen de aforo separado para carros y motocicletas.

### Gestión de pagos (Iteración 3)
- Tarifas de la mensualidad por tipo de vehículo: carro $250.000 y moto $100.000.
- Registro del pago por placa con método EFECTIVO, TRANSFERENCIA o TARJETA; transferencia y tarjeta exigen número de referencia.
- El valor sale de la tarifa y no se puede editar. El periodo empieza hoy si la mensualidad está vencida, o en la fecha de vencimiento si todavía está vigente (pago adelantado). Termina el mismo día del mes siguiente (o el último día del mes si ese día no existe).
- Cada pago genera un comprobante con consecutivo único (AC-000001) que se puede imprimir o guardar en PDF desde el navegador.
- Estado de la mensualidad por placa: vigente, por vencer (5 días o menos) o vencida.
- El ingreso se rechaza si la mensualidad está vencida; el día del vencimiento ya no se permite el ingreso.
- Historial de pagos con filtros por placa, fechas, método y estado.
- Anulación solo por el administrador, con motivo obligatorio y únicamente sobre el último pago del vehículo; el pago queda ANULADO (no se borra) y la vigencia se recalcula.
- Reportes para el administrador: recaudo por rango de fechas, método y tipo de vehículo, y lista de vehículos en mora o por vencer.

### Datos de demostración
Al arrancar con la base vacía se crean las cuentas `admin` / `Admin2026*` y `operario1` / `Oper2026*`, 70 celdas de carro, 10 de moto, las tarifas y tres vehículos:

| Placa | Tipo | Estado de la mensualidad |
|---|---|---|
| ABC123 | Carro | Vencida (para mostrar el pago) |
| DEF456 | Carro | Por vencer (3 días) |
| MOT12A | Moto | Vigente |

Para empezar de cero, detén el backend y borra la carpeta `backend/data`.

## Requisitos
- Python 3.10 o superior.
- Node.js y npm compatibles con la versión de Angular definida en frontend/package.json.

## Ejecución local en Windows
Abre dos terminales de PowerShell desde la carpeta del proyecto.

### 1. Backend
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000
Documentación interactiva: http://127.0.0.1:8000/docs

### 2. Frontend
```powershell
cd frontend
npm install
npm start
```
Interfaz: http://localhost:4200

### 3. Pruebas
```powershell
cd backend
pytest -q tests
```
`tests/test_iteracion_3.py` cubre los casos del plan de pruebas de pagos (CP-P01 a CP-P12). Las pruebas usan los endpoints actuales de la API. La aplicación de demostración utiliza SQLite local; para pruebas repetibles y aisladas se recomienda configurar una base temporal específica para el entorno de pruebas.

## Credenciales iniciales de demostración
- Administrador: admin / Admin2026*
- Operario: operario1 / Oper2026*
Estas credenciales son únicamente para ejecución académica local. Deben cambiarse antes de cualquier despliegue.

## Configuración y seguridad
- La base de datos local se crea en backend/data/autos_colombia.sqlite3.
- El frontend apunta por defecto a http://127.0.0.1:8000/api/v1.
- CORS está limitado a los orígenes locales de Angular (localhost:4200 y 127.0.0.1:4200).
- Las sesiones actuales se mantienen en memoria del proceso; al reiniciar el backend, los usuarios deben iniciar sesión nuevamente.
- Este repositorio es un prototipo académico y no debe exponerse directamente a Internet sin endurecer autenticación, configuración, almacenamiento de secretos, sesiones y despliegue.

## Estructura principal
- backend/app/: API, modelos, persistencia y reglas de negocio.
- backend/app/routers/: autenticación, gestión, celdas y movimientos.
- backend/tests/: pruebas automatizadas de acceso y administración.
- frontend/src/app/: interfaz de inicio de sesión, operación y administración.
- docs/: documentación, diagramas y mockups del proyecto.
