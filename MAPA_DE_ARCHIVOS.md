# Mapa de archivos y cambios

| Archivo/ruta | Acción | Motivo |
|---|---|---|
| `backend/requirements.txt` | Actualizar | Falta SQLAlchemy |
| `backend/app/database.py` | Ajustar con cuidado | Integridad referencial SQLite y conexión |
| `backend/app/models.py` | Revisar, no reemplazar a ciegas | Debe coincidir con DB existente |
| `backend/app/main.py` | Actualizar | Montar routers reales y health |
| `backend/app/routers/auth.py` | Actualizar | Hash seguro, login, cierre de sesión, autorización |
| `backend/app/routers/gestion.py` | Actualizar | Administración real de cuentas y protección de datos |
| `backend/app/routers/celdas.py` | Actualizar | Validaciones de CRUD y permisos |
| `backend/app/routers/movimientos.py` | Actualizar | Contrato JSON, búsqueda abierta, filtros, transacciones |
| `backend/app/routers/` | Crear routers faltantes si el alcance los exige | Pagos, novedades, vehículos, ocupación |
| `backend/tests/test_access.py` | Reescribir o retirar tras reemplazo | Importa funciones que no existen en main |
| `backend/tests/test_iteracion_2.py` | Corregir | Acepta 409 como si crear celda fuera éxito |
| `frontend/src/app/core/` | Crear | Servicio auth e interceptor |
| `frontend/src/app/guards/` | Crear | Guardas de autenticación y rol |
| `frontend/src/app/pages/login/` | Crear | Pantalla de login |
| `frontend/src/app/pages/usuarios/` | Crear | Gestión de cuentas |
| `frontend/src/app/pages/celdas/` | Crear | Gestión de celdas individuales |
| `frontend/src/app/app.routes.ts` | Actualizar | Actualmente no tiene rutas |
| `frontend/src/app/app.config.ts` | Actualizar | Registrar interceptor y router |
| `frontend/src/app/app.ts` y `app.html` | Actualizar | Navegación y pantallas según rol |
| `frontend/src/app/app.css` | Actualizar | Mantener identidad visual y adaptar pantallas |
| `README.md` | Reescribir secciones contradictorias | Documentar solo lo que sí está implementado |
| `backend/docs/diagramas/` | Revisar y actualizar | Consistencia con modelo final |
| `backend/docs/mockups/` | Revisar y completar | Login, usuarios y celdas |
| `backend/docs/entregables/` | Actualizar informe | Evidencias y alcance final |

## No borrar todavía
- `backend/backend/data/autos_colombia.sqlite3`: respaldar e inspeccionar antes.
- `backend/backend/`: contiene una copia de archivos; comparar antes de eliminar.
- `backend/app/models.py`: no sustituir por un modelo reducido.
