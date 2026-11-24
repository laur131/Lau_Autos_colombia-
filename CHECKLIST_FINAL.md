# Lista de verificación final — Autos Colombia

## Backend
- [ ] SQLAlchemy instalado desde requirements.
- [ ] La base SQLite se respalda antes de cambios.
- [ ] Modelos cotejados con las tablas reales.
- [ ] Login ADMIN y OPERARIO funcional.
- [ ] Hash de contraseña seguro.
- [ ] Token requerido en rutas protegidas.
- [ ] Listado de usuarios no expone password_hash.
- [ ] Crear, editar y desactivar cuentas solo ADMIN.
- [ ] CRUD de celdas individuales con validaciones.
- [ ] Operador no puede administrar usuarios ni celdas.
- [ ] Rutas de ocupación, vehículos e historial implementadas o frontend adaptado.
- [ ] Ingreso/salida reciben el mismo contrato que envía Angular.
- [ ] Operario se obtiene del token, no del body.
- [ ] Movimientos y estado de celda se guardan transaccionalmente.

## Frontend
- [ ] Login visible al iniciar sin sesión.
- [ ] Token se adjunta a solicitudes protegidas.
- [ ] ADMIN ve Usuarios y Celdas.
- [ ] OPERARIO no ve módulos administrativos.
- [ ] Backend también bloquea acciones no autorizadas.
- [ ] Ingreso y salida funcionan desde Angular.
- [ ] Historial y ocupación muestran datos reales.
- [ ] `npm run build` termina sin errores.

## Pruebas y entrega
- [ ] `pytest -q` ejecutado y salida guardada.
- [ ] Pruebas usan base temporal.
- [ ] Pruebas de login, roles, celdas, ingreso y salida.
- [ ] Capturas reales de ejecución.
- [ ] Mockups y diagramas coinciden con la app final.
- [ ] README sin afirmaciones contradictorias.
- [ ] Informe actualizado con evidencias reales.
- [ ] Rama de corrección revisada antes de integrar a main.
