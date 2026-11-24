# KIT DE CORRECCIÓN — AUTOS COLOMBIA
**Guía de aplicación basada en la revisión del repositorio `HGNA23/autos-colombia-parqueadero`**

## 1. Para qué sirve este kit

Este kit convierte la retroalimentación del docente en cambios concretos sobre los archivos que existen actualmente en GitHub. No es una reconstrucción desde cero ni una autorización para reemplazar toda la carpeta `backend/app`.

**Estado de esta revisión:** se inspeccionó el árbol del repositorio y el contenido de los archivos principales del backend, frontend, pruebas y README. No se ejecutó el proyecto completo en un equipo local ni se verificó la interfaz en navegador. Por eso, este kit distingue entre hallazgos comprobados y pruebas que todavía deben ejecutarse.

**Importante:** no aplicar el ZIP anterior llamado `Autos_Colombia_Codigo_Backend_Corregido.zip`. Esa propuesta sustituía archivos centrales sin haber conciliado toda la estructura existente. Este kit no depende de ese ZIP.

## 2. Diagnóstico real del repositorio

### Hallazgos comprobados

1. `backend/requirements.txt` no incluye SQLAlchemy, aunque `database.py`, `models.py` y los routers lo importan. La instalación indicada en el README puede fallar al iniciar el backend.
2. El backend activo está en `backend/app/`. Existe otra copia en `backend/backend/app/`; varios archivos tienen el mismo contenido. También hay una base SQLite dentro de `backend/backend/data/`.
3. `backend/app/main.py` solo registra los routers `auth`, `celdas`, `gestion` y `movimientos`. No registra routers de pagos, novedades, vehículos independientes ni ocupación.
4. La interfaz Angular actual es un único componente de operación. `frontend/src/app/app.routes.ts` tiene `Routes = []`; no existen rutas funcionales para login, usuarios, roles o celdas.
5. El frontend consulta `/api/v1/ocupacion`, `/api/v1/vehiculos`, `/api/v1/movimientos/abiertos/{placa}` y `/api/v1/movimientos`, pero esas rutas no están implementadas en los routers actuales revisados.
6. El frontend envía el ingreso y la salida como JSON e incluye `operario_id: 1`. El backend recibe placa y observaciones como parámetros de consulta y obtiene el operario desde el token. Los contratos no coinciden.
7. `backend/tests/test_access.py` importa `connect`, `create_app` y `plus_one_month` desde `app.main`, pero esos elementos no existen en el `main.py` actual. Es una prueba de otra versión del proyecto.
8. `backend/tests/test_iteracion_2.py` acepta 200, 201 o 409 al crear una celda. Por tanto, puede considerar como aceptable que la celda no se haya creado.
9. `gestion.py` permite consultar usuarios a cualquier usuario autenticado y devuelve los modelos directamente. Debe limitarse el acceso y no exponer hashes de contraseñas.
10. `auth.py` usa SHA-256 simple para las contraseñas y guarda sesiones en memoria. Es una solución débil; para el prototipo académico debe mejorarse el hash y documentarse la limitación de las sesiones.
11. `celdas.py` ya tiene listado, creación y edición individual, pero requiere validaciones adicionales de estados, tipo de vehículo, código, campos vacíos y cambios de celdas ocupadas.
12. El README tiene dos descripciones de alcance contradictorias: una indica que el módulo de usuarios no está integrado y otra afirma que login y celdas ya están implementados. Debe quedar una sola descripción que coincida con el código final.
13. El repositorio sí contiene archivos PNG de diagramas y mockups en `backend/docs/`. Hay que revisar que sean legibles y que correspondan a las pantallas y funciones que finalmente queden implementadas.

## 3. Orden de trabajo recomendado

No se debe empezar rediseñando todo. El orden evita que la interfaz se conecte a endpoints inexistentes.

### Fase A. Estabilizar el backend existente

**Archivo: `backend/requirements.txt`**
- Agregar `SQLAlchemy` a las dependencias.
- Mantener FastAPI, Uvicorn, pytest y httpx.
- Instalar desde una copia de trabajo limpia y comprobar que el servidor inicia.

**Archivo: `backend/app/database.py`**
- Conservar inicialmente la conexión y la ubicación de SQLite.
- Activar la integridad referencial de SQLite (`PRAGMA foreign_keys=ON`) en cada conexión.
- No cambiar el nombre de tablas ni columnas sin revisar primero la base de datos existente.

**Archivo: `backend/app/models.py`**
- No reemplazarlo por un modelo simplificado.
- Comparar cada clase y columna con la estructura real de `backend/backend/data/autos_colombia.sqlite3` y cualquier base local del equipo.
- Confirmar si existen tablas de pagos y novedades. Si hacen parte del alcance, modelarlas sin borrar información.
- Definir relaciones y restricciones de unicidad donde correspondan.

**Archivo: `backend/app/main.py`**
- Mantener los routers existentes mientras se corrigen.
- Registrar los routers que realmente se implementen para pagos, novedades, vehículos y ocupación.
- Agregar un endpoint de salud (`GET /api/v1/health`).
- No declarar una función o ruta en README si no existe en código.

### Fase B. Completar autenticación, cuentas y permisos

**Archivo: `backend/app/routers/auth.py`**
- Mantener `POST /api/v1/auth/login`.
- Verificar credenciales de cuentas activas.
- Reemplazar SHA-256 directo por un hash de contraseña con sal y factor de trabajo (por ejemplo, PBKDF2).
- Mantener roles explícitos `ADMIN` y `OPERARIO`.
- Crear un endpoint para cerrar sesión o invalidar el token.
- Evitar que la respuesta de login o cualquier listado devuelva `password_hash`.
- Para el alcance académico, documentar cómo se administran los tokens. No presentar sesiones en memoria como autenticación productiva.

**Archivo: `backend/app/routers/gestion.py`**
- Restringir el listado y administración de cuentas al administrador.
- Separar la ficha de una persona titular de una cuenta que puede iniciar sesión.
- Agregar operaciones de crear, consultar, editar y activar/desactivar cuentas operativas.
- No permitir que un operador cree administradores ni cambie su propio rol.
- Validar documento y nombre de usuario duplicados.
- No devolver hashes ni credenciales en respuestas.

**Permisos mínimos que deben quedar demostrables**
- Administrador: gestionar cuentas, roles y celdas; consultar información administrativa.
- Operador: registrar ingresos y salidas y consultar las funciones operativas autorizadas.
- Titular: registro asociado a vehículos; no puede iniciar sesión en el panel operativo salvo que el alcance lo defina expresamente.

### Fase C. Completar la gestión de celdas individuales

**Archivo: `backend/app/routers/celdas.py`**
- Conservar el identificador único de cada celda.
- Permitir crear, listar y editar celdas.
- Estados permitidos: `DISPONIBLE`, `OCUPADA`, `MANTENIMIENTO`.
- Tipos permitidos: `CARRO`, `MOTOCICLETA`.
- Rechazar códigos vacíos o repetidos.
- No permitir desactivar, cambiar de tipo o poner en mantenimiento una celda ocupada.
- No permitir que un usuario con rol `OPERARIO` cree, edite o desactive celdas.
- La capacidad debe calcularse a partir de celdas activas individuales, no solo de un número máximo aislado.

**Criterio de aceptación:** el administrador crea una celda `C-71`, la consulta en el inventario, la edita y la pone en mantenimiento. Un operador que intente crear o editar una celda recibe HTTP 403. Una celda ocupada no puede desactivarse.

### Fase D. Unificar contratos entre Angular y FastAPI

**Archivo: `backend/app/routers/movimientos.py`**
- Definir esquemas Pydantic para recibir JSON de ingreso y salida.
- Obtener el identificador del operario exclusivamente desde el usuario autenticado; nunca confiar en `operario_id` enviado por el navegador.
- Implementar la búsqueda de movimientos abiertos por placa.
- Implementar listado de movimientos con filtros que la interfaz utiliza.
- Devolver los campos que la interfaz necesita: movimiento, placa, tipo, fecha de entrada, fecha de salida, estado, observaciones y celda asignada.
- Hacer que la actualización del movimiento y el estado de la celda se confirmen en una misma transacción.

**Rutas que la interfaz actual espera y que deben existir o deben cambiarse también en Angular**
- `GET /api/v1/ocupacion`
- `GET /api/v1/vehiculos`
- `POST /api/v1/movimientos/ingresos`
- `GET /api/v1/movimientos/abiertos/{placa}`
- `POST /api/v1/movimientos/{id}/salida`
- `GET /api/v1/movimientos`

No basta con crear rutas: sus nombres, parámetros y respuestas deben coincidir con los tipos que consume Angular.

### Fase E. Construir los módulos que faltan en Angular

La interfaz actual solo contiene ingreso, salida e historial. Los siguientes archivos deben crearse o actualizarse:

**Crear**
- `frontend/src/app/core/auth.service.ts`: login, token y usuario autenticado.
- `frontend/src/app/core/auth.interceptor.ts`: agregar el encabezado Bearer a las solicitudes protegidas.
- `frontend/src/app/guards/auth.guard.ts`: impedir acceso sin sesión.
- `frontend/src/app/guards/role.guard.ts`: controlar acceso según rol.
- `frontend/src/app/pages/login/`: formulario de acceso.
- `frontend/src/app/pages/usuarios/`: tabla y formularios de cuentas.
- `frontend/src/app/pages/celdas/`: inventario y formulario de celdas.

**Actualizar**
- `frontend/src/app/app.routes.ts`: rutas de login, operación, usuarios y celdas.
- `frontend/src/app/app.config.ts`: registrar interceptor y configuración de rutas.
- `frontend/src/app/app.ts` y `app.html`: conservar el módulo operativo y añadir navegación por permisos.
- `frontend/src/app/app.css`: mantener el estilo visual existente y adaptarlo a los nuevos módulos.

**Reglas de interfaz**
- Sin sesión: mostrar login, no el panel operativo.
- ADMIN: mostrar operación, usuarios y celdas.
- OPERARIO: mostrar solo operación y las consultas autorizadas.
- Ocultar botones no autorizados no sustituye la validación del backend. El backend también debe rechazar la acción.

## 4. Documentación y evidencias

El repositorio tiene estos recursos:
- `backend/docs/diagramas/01_Diagrama_Casos_Uso.png`
- `backend/docs/diagramas/02_Diagrama_Clases_Unificado.png`
- `backend/docs/diagramas/03_Diagrama_Secuencia.png`
- `backend/docs/diagramas/04_Diagrama_Componentes.png`
- `backend/docs/mockups/01_Mockup_Login_Credenciales_Permisos.png`
- `backend/docs/mockups/02_Mockup_Celdas_Individuales.png`
- `backend/docs/mockups/03_Mockup_Ingreso_Auditoria.png`

Acciones:
1. Abrir cada imagen y comprobar que el texto se lea.
2. Verificar que los roles, rutas y nombres de clases coincidan con el código.
3. Incluir los mockups de login, usuarios y celdas en el informe.
4. Incluir diagramas de casos de uso, clases, secuencia y componentes.
5. Guardar capturas de la aplicación ejecutándose y de Swagger (`/docs`).
6. No llamar “evidencia de ejecución” a un diagrama o a una descripción.

## 5. Pruebas que deben ejecutarse

No marcar pruebas como exitosas antes de ejecutarlas. Como mínimo:

| ID | Prueba | Resultado esperado |
|---|---|---|
| P-01 | Login con administrador válido | 200 y token |
| P-02 | Login con contraseña incorrecta | 401 |
| P-03 | Login con cuenta inactiva | 403 |
| P-04 | Operador intenta crear cuenta | 403 |
| P-05 | Administrador crea cuenta operativa | 201 |
| P-06 | Usuario duplicado | 409 |
| P-07 | Operador intenta crear celda | 403 |
| P-08 | Administrador crea celda individual | 201 |
| P-09 | Código de celda duplicado | 409 |
| P-10 | Celda ocupada se intenta desactivar | 409 |
| P-11 | Vehículo no registrado intenta ingresar | 409 |
| P-12 | Mensualidad vencida intenta ingresar | 409 |
| P-13 | Segundo ingreso con movimiento abierto | 409 |
| P-14 | Ingreso válido | 201, movimiento y celda ocupada |
| P-15 | Salida válida | 200, movimiento cerrado y celda liberada |
| P-16 | Usuario sin token consulta módulo protegido | 401 |

### Problemas actuales de las pruebas
- `backend/tests/test_access.py` pertenece a otra estructura y no puede considerarse válida para el backend actual mientras importe funciones inexistentes.
- `backend/tests/test_iteracion_2.py` debe cambiar la aceptación amplia `in (200, 201, 409)` por una expectativa exacta de creación exitosa, con preparación de datos aislada para que la prueba pueda repetirse.
- Las pruebas deben usar una base temporal, no modificar la base de datos real del proyecto.
- Guardar la salida real de `pytest -q` y capturas de los casos clave.

## 6. Organización de carpetas

La carpeta activa que indica el README es `backend/app/`. La copia `backend/backend/` duplica código y contiene una base SQLite versionada.

Propuesta:
- Mantener `backend/app/` como única fuente del código.
- Antes de eliminar `backend/backend/`, comparar sus archivos y respaldar la base SQLite.
- No borrar la base de datos ni moverla hasta confirmar qué información contiene.
- Mantener documentación en una sola ubicación, preferiblemente `backend/docs/`, y corregir los enlaces del README para que apunten a esa ubicación.
- No subir archivos `.venv`, `node_modules`, bases de datos con datos reales ni archivos temporales.

## 7. Cómo aplicar y comprobar

1. Descargar una copia ZIP del repositorio actual o clonar el repositorio.
2. Crear una rama de trabajo llamada `correccion-ea2`.
3. Copiar la base SQLite a una carpeta de respaldo antes de cualquier cambio.
4. Aplicar las fases A, B, C y D en backend.
5. Instalar dependencias y ejecutar el backend.
6. Abrir `http://127.0.0.1:8000/docs` y comprobar rutas y respuestas.
7. Aplicar la fase E en Angular.
8. Ejecutar `npm install` y `npm run build`.
9. Ejecutar las pruebas de backend con `pytest -q`.
10. Resolver todos los errores antes de actualizar el informe.
11. Actualizar README, mockups, diagramas e informe para que describan exactamente la versión que sí funciona.
12. Solo entonces integrar los cambios a `main`.

## 8. Criterio de “terminado”

El proyecto no se considera corregido hasta que:
- el servidor instala e inicia sin errores;
- el login funciona con cuentas de administrador y operador;
- las rutas protegidas exigen token;
- el backend aplica permisos, no solo la interfaz;
- el administrador puede administrar cuentas y celdas individuales;
- el operador no puede ejecutar acciones administrativas;
- ingreso y salida funcionan desde Angular y registran al operario autenticado;
- la ocupación refleja las celdas individuales;
- las pruebas relevantes pasan y se conserva su salida real;
- el informe, mockups, diagramas y README coinciden con la implementación.

**No se debe afirmar que el proyecto está listo si solo compila una parte, si el login existe únicamente en el backend o si las pruebas no se ejecutaron.**
