
import { CommonModule } from '@angular/common';
import {
  HttpClient,
  HttpErrorResponse,
  HttpHeaders,
  HttpParams
} from '@angular/common/http';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { apiResponded } from './refresh-view.interceptor';

type View = 'ingreso' | 'salida' | 'historial' | 'cuentas' | 'celdas' | 'pagos' | 'historial-pagos' | 'reportes';

interface Usuario {
  usuario_id: number;
  nombres: string;
  apellidos: string;
  username: string;
  rol: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  usuario: Usuario;
}

interface ManagedUser extends Omit<Usuario, 'username'> {
  username: string | null;
  documento: string;
  activo: number;
}

interface ParkingCell {
  celda_id: number;
  codigo: string;
  tipo_vehiculo: string;
  ubicacion: string;
  estado: string;
  activa: number;
}

interface Count {
  ocupadas: number;
  disponibles: number;
  capacidad: number;
}

interface Occupancy {
  carros: Count;
  motocicletas: Count;
}

interface Movement {
  movimiento_id: number;
  placa: string | null;
  celda: string | null;
  fecha_hora_entrada: string;
  fecha_hora_salida: string | null;
  observacion_entrada: string;
  observacion_salida: string;
  operario_id: number;
  operario_cierre_id: number | null;
  estado: 'ABIERTO' | 'CERRADO';
}

interface Payment {
  pago_id: number;
  numero_comprobante: string;
  placa: string;
  tipo_vehiculo: string;
  titular: string;
  valor: number;
  metodo: string;
  referencia: string | null;
  fecha_hora: string;
  periodo_inicio: string;
  periodo_fin: string;
  operario: string;
  estado: 'REGISTRADO' | 'ANULADO';
  anulado_por: string | null;
  fecha_anulacion: string | null;
  motivo_anulacion: string | null;
}

interface MonthlyStatus {
  placa: string;
  tipo_vehiculo: string;
  vehiculo_activo: boolean;
  titular: string | null;
  titular_activo: boolean;
  estado: 'VIGENTE' | 'POR_VENCER' | 'VENCIDA' | 'SIN_MENSUALIDAD';
  fecha_vencimiento: string | null;
  dias_restantes: number | null;
  ultimo_pago: Payment | null;
  valor_a_pagar: number;
  periodo_propuesto: { inicio: string; fin: string };
}

interface Collection {
  desde: string;
  hasta: string;
  total_recaudado: number;
  pagos_registrados: number;
  pagos_anulados: number;
  valor_anulado: number;
  por_metodo: Record<string, number>;
  por_tipo_vehiculo: Record<string, number>;
}

interface Overdue {
  placa: string;
  tipo_vehiculo: string;
  titular: string;
  estado: string;
  fecha_vencimiento: string | null;
  dias_restantes: number | null;
}

const API = 'http://127.0.0.1:8000/api/v1';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
})
export class App implements OnInit {

  private readonly http = inject(HttpClient);
  private readonly cdr = inject(ChangeDetectorRef);

  constructor() {
    // Redibuja la vista cada vez que la API responde (ver refresh-view.interceptor.ts)
    apiResponded.subscribe(() => this.cdr.markForCheck());
  }

  token: string | null = null;
  currentUser: Usuario | null = null;

  loginUsername = '';
  loginPassword = '';

  view: View = 'ingreso';

  occupancy: Occupancy | null = null;
  managedUsers: ManagedUser[] = [];
  parkingCells: ParkingCell[] = [];

  accountDocument = '';
  accountNames = '';
  accountLastNames = '';
  accountUsername = '';
  accountPassword = '';
  accountRole = 'OPERARIO';

  cellCode = '';
  cellType = 'CARRO';
  cellLocation = 'Zona General';
  movements: Movement[] = [];
  filteredMovements: Movement[] = [];

  entryPlate = '';
  entryNote = '';

  exitPlate = '';
  exitNote = '';
  openMovement: Movement | null = null;

  historyPlate = '';
  fromDate = '';
  toDate = '';
  historyState = '';

  // Gestión de pagos (Iteración 3)
  paymentPlate = '';
  paymentMethod = 'EFECTIVO';
  paymentReference = '';
  monthlyStatus: MonthlyStatus | null = null;
  receipt: Payment | null = null;

  payments: Payment[] = [];
  paymentFilterPlate = '';
  paymentFrom = '';
  paymentTo = '';
  paymentFilterMethod = '';
  paymentFilterState = '';
  voidingPayment: Payment | null = null;
  voidReason = '';

  reportFrom = '';
  reportTo = '';
  collection: Collection | null = null;
  overdue: Overdue[] = [];

  busy = false;
  message = '';
  messageType: 'success' | 'error' | 'info' = 'info';

  ngOnInit(): void {
    // El usuario debe iniciar sesión para acceder al sistema.
  }

  get isAdmin(): boolean {
    return this.currentUser?.rol === 'ADMIN';
  }

  private get headers(): HttpHeaders {
    return new HttpHeaders({
      Authorization: `Bearer ${this.token}`
    });
  }

  login(): void {
    if (this.busy || !this.loginUsername.trim() || !this.loginPassword) {
      return;
    }

    this.busy = true;
    this.message = '';

    this.http.post<LoginResponse>(`${API}/auth/login`, {
      username: this.loginUsername.trim(),
      password: this.loginPassword
    }).subscribe({
      next: response => {
        this.token = response.access_token;
        this.currentUser = response.usuario;

        this.loginPassword = '';
        this.busy = false;
        this.messageType = 'success';
        this.message = `Bienvenido, ${response.usuario.nombres}.`;

        this.refresh();
        if (this.isAdmin) this.loadAdminData();
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  logout(): void {
    if (!this.token) {
      return;
    }

    this.http.post(
      `${API}/auth/logout`,
      {},
      { headers: this.headers }
    ).subscribe({
      next: () => this.finishLogout(),
      error: () => this.finishLogout()
    });
  }

  private finishLogout(): void {
    this.token = null;
    this.currentUser = null;
    this.occupancy = null;
    this.movements = [];
    this.filteredMovements = [];
    this.managedUsers = [];
    this.parkingCells = [];
    this.openMovement = null;
    this.monthlyStatus = null;
    this.receipt = null;
    this.payments = [];
    this.collection = null;
    this.overdue = [];
    this.paymentPlate = '';
    this.entryPlate = '';
    this.exitPlate = '';
    this.message = '';
    this.view = 'ingreso';
  }

  setView(view: View): void {
    this.view = view;
    this.message = '';

    if (view === 'historial') this.loadHistory();
    if (view === 'cuentas' || view === 'celdas') this.loadAdminData();
    if (view === 'historial-pagos') this.loadPayments();
    if (view === 'reportes') this.loadReports();
  }

  // ---------------- Gestión de pagos ----------------

  findMonthly(): void {
    const plate = this.paymentPlate.trim().toUpperCase();
    if (!this.token || !plate) return;

    this.receipt = null;
    this.message = '';

    this.http.get<MonthlyStatus>(
      `${API}/pagos/mensualidad/${encodeURIComponent(plate)}`,
      { headers: this.headers }
    ).subscribe({
      next: status => this.monthlyStatus = status,
      error: error => {
        this.monthlyStatus = null;
        this.showError(error);
      }
    });
  }

  registerPayment(): void {
    if (!this.token || !this.monthlyStatus || this.busy) return;

    this.busy = true;
    this.message = '';

    this.http.post<{ mensaje: string; comprobante: Payment }>(
      `${API}/pagos`,
      {
        placa: this.monthlyStatus.placa,
        metodo: this.paymentMethod,
        referencia: this.paymentMethod === 'EFECTIVO' ? null : this.paymentReference.trim()
      },
      { headers: this.headers }
    ).subscribe({
      next: response => {
        this.busy = false;
        this.receipt = response.comprobante;
        this.messageType = 'success';
        this.message = `${response.mensaje}. Comprobante ${response.comprobante.numero_comprobante}.`;
        this.paymentReference = '';
        this.findMonthlyKeepingReceipt();
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  private findMonthlyKeepingReceipt(): void {
    if (!this.monthlyStatus) return;
    this.http.get<MonthlyStatus>(
      `${API}/pagos/mensualidad/${encodeURIComponent(this.monthlyStatus.placa)}`,
      { headers: this.headers }
    ).subscribe({ next: status => this.monthlyStatus = status });
  }

  showReceipt(payment: Payment): void {
    this.receipt = payment;
  }

  printReceipt(): void {
    window.print();
  }

  loadPayments(): void {
    if (!this.token) return;

    let params = new HttpParams();
    if (this.paymentFilterPlate.trim()) params = params.set('placa', this.paymentFilterPlate.trim().toUpperCase());
    if (this.paymentFrom) params = params.set('desde', this.paymentFrom);
    if (this.paymentTo) params = params.set('hasta', this.paymentTo);
    if (this.paymentFilterMethod) params = params.set('metodo', this.paymentFilterMethod);
    if (this.paymentFilterState) params = params.set('estado', this.paymentFilterState);

    this.http.get<Payment[]>(`${API}/pagos`, { headers: this.headers, params }).subscribe({
      next: payments => this.payments = payments,
      error: error => this.showError(error)
    });
  }

  startVoid(payment: Payment): void {
    this.voidingPayment = payment;
    this.voidReason = '';
  }

  confirmVoid(): void {
    if (!this.token || !this.voidingPayment || this.busy) return;

    this.busy = true;

    this.http.post<{ mensaje: string }>(
      `${API}/pagos/${this.voidingPayment.pago_id}/anulacion`,
      { motivo: this.voidReason.trim() },
      { headers: this.headers }
    ).subscribe({
      next: response => {
        this.busy = false;
        this.messageType = 'success';
        this.message = response.mensaje;
        this.voidingPayment = null;
        this.loadPayments();
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  loadReports(): void {
    if (!this.token || !this.isAdmin) return;

    let params = new HttpParams();
    if (this.reportFrom) params = params.set('desde', this.reportFrom);
    if (this.reportTo) params = params.set('hasta', this.reportTo);

    this.http.get<Collection>(`${API}/reportes/recaudo`, { headers: this.headers, params }).subscribe({
      next: collection => {
        this.collection = collection;
        this.reportFrom = collection.desde;
        this.reportTo = collection.hasta;
      },
      error: error => this.showError(error)
    });

    this.http.get<Overdue[]>(`${API}/reportes/mora`, { headers: this.headers }).subscribe({
      next: rows => this.overdue = rows,
      error: error => this.showError(error)
    });
  }

  money(value: number | null | undefined): string {
    return new Intl.NumberFormat('es-CO', {
      style: 'currency',
      currency: 'COP',
      maximumFractionDigits: 0
    }).format(value ?? 0);
  }

  day(value: string | null): string {
    if (!value) return '—';
    const [y, m, d] = value.substring(0, 10).split('-').map(Number);
    return new Intl.DateTimeFormat('es-CO', { dateStyle: 'medium' }).format(new Date(y, m - 1, d));
  }

  statusLabel(status: string): string {
    return ({
      VIGENTE: 'Vigente',
      POR_VENCER: 'Por vencer',
      VENCIDA: 'Vencida',
      SIN_MENSUALIDAD: 'Sin mensualidad'
    } as Record<string, string>)[status] ?? status;
  }

  refresh(): void {
    if (!this.token) {
      return;
    }

    this.http.get<any>(
      `${API}/celdas/`,
      { headers: this.headers }
    ).subscribe({
      next: response => {
        this.occupancy = response.resumen_aforo;
      },
      error: error => this.showError(error)
    });
  }

  loadAdminData(): void {
    if (!this.token || !this.isAdmin) return;

    this.http.get<ManagedUser[]>(`${API}/gestion/usuarios`, {
      headers: this.headers
    }).subscribe({
      next: users => this.managedUsers = users,
      error: error => this.showError(error)
    });

    this.http.get<any>(`${API}/celdas/`, {
      headers: this.headers
    }).subscribe({
      next: response => this.parkingCells = response.celdas ?? [],
      error: error => this.showError(error)
    });
  }

  createAccount(): void {
    if (!this.token || !this.isAdmin || this.busy) return;
    this.busy = true;
    this.http.post(`${API}/auth/cuentas`, {
      documento: this.accountDocument.trim(),
      nombres: this.accountNames.trim(),
      apellidos: this.accountLastNames.trim(),
      username: this.accountUsername.trim(),
      password: this.accountPassword,
      rol: this.accountRole
    }, { headers: this.headers }).subscribe({
      next: () => {
        this.busy = false;
        this.messageType = 'success';
        this.message = 'Cuenta creada correctamente.';
        this.accountDocument = '';
        this.accountNames = '';
        this.accountLastNames = '';
        this.accountUsername = '';
        this.accountPassword = '';
        this.accountRole = 'OPERARIO';
        this.loadAdminData();
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  toggleUser(user: ManagedUser): void {
    if (!this.token || !this.isAdmin || this.busy) return;
    const nextState = user.activo === 1 ? 0 : 1;
    const params = new HttpParams().set('activo', String(nextState));
    this.http.patch(`${API}/gestion/usuarios/${user.usuario_id}/estado`, null, {
      headers: this.headers,
      params
    }).subscribe({
      next: () => {
        this.messageType = 'success';
        this.message = 'Estado de la cuenta actualizado.';
        this.loadAdminData();
      },
      error: error => this.showError(error)
    });
  }

  createCell(): void {
    if (!this.token || !this.isAdmin || this.busy) return;
    this.busy = true;
    this.http.post(`${API}/celdas/`, {
      codigo: this.cellCode.trim().toUpperCase(),
      tipo_vehiculo: this.cellType,
      ubicacion: this.cellLocation.trim()
    }, { headers: this.headers }).subscribe({
      next: () => {
        this.busy = false;
        this.messageType = 'success';
        this.message = 'Celda individual creada correctamente.';
        this.cellCode = '';
        this.loadAdminData();
        this.refresh();
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  toggleCellMaintenance(cell: ParkingCell): void {
    if (!this.token || !this.isAdmin || this.busy) return;
    const nextState = cell.estado === 'MANTENIMIENTO' ? 'DISPONIBLE' : 'MANTENIMIENTO';
    this.http.patch(`${API}/celdas/${cell.celda_id}`, {
      estado: nextState
    }, { headers: this.headers }).subscribe({
      next: () => {
        this.messageType = 'success';
        this.message = `Celda ${cell.codigo}: estado actualizado.`;
        this.loadAdminData();
        this.refresh();
      },
      error: error => this.showError(error)
    });
  }

  registerEntry(): void {
    if (this.busy || !this.entryPlate.trim() || !this.token) {
      return;
    }

    this.busy = true;
    this.message = '';

    const params = new HttpParams()
      .set('placa', this.entryPlate.trim().toUpperCase())
      .set('observacion', this.entryNote);

    this.http.post<any>(
      `${API}/movimientos/ingresos`,
      null,
      {
        headers: this.headers,
        params
      }
    ).subscribe({
      next: response => {
        this.busy = false;
        this.messageType = 'success';

        this.message =
          `Ingreso registrado: ${response.placa} · ` +
          `Movimiento #${response.movimiento_id} · ` +
          `Celda ${response.celda_asignada}.`;

        this.entryPlate = '';
        this.entryNote = '';

        this.refresh();
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  findOpen(): void {
    if (!this.exitPlate.trim() || !this.token) {
      return;
    }

    this.busy = true;
    this.openMovement = null;
    this.message = '';

    this.http.get<Movement[]>(
      `${API}/movimientos/historial`,
      { headers: this.headers }
    ).subscribe({
      next: movements => {
        this.busy = false;

        const plate = this.exitPlate.trim().toUpperCase();

        this.openMovement = movements.find(
          movement =>
            movement.placa?.toUpperCase() === plate &&
            movement.estado === 'ABIERTO'
        ) ?? null;

        if (this.openMovement) {
          this.messageType = 'info';
          this.message =
            `Entrada abierta encontrada para ${plate}.`;
        } else {
          this.messageType = 'error';
          this.message =
            'No se encontró una entrada abierta para esa placa.';
        }
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  registerExit(): void {
    if (!this.openMovement || this.busy || !this.token) {
      return;
    }

    this.busy = true;

    const params = new HttpParams()
      .set('observacion_salida', this.exitNote);

    this.http.post<any>(
      `${API}/movimientos/${this.openMovement.movimiento_id}/salida`,
      null,
      {
        headers: this.headers,
        params
      }
    ).subscribe({
      next: response => {
        this.busy = false;
        this.messageType = 'success';

        this.message =
          `Salida registrada. Celda ${response.celda_liberada} liberada.`;

        this.openMovement = null;
        this.exitPlate = '';
        this.exitNote = '';

        this.refresh();
      },
      error: error => {
        this.busy = false;
        this.showError(error);
      }
    });
  }

  loadHistory(): void {
    if (!this.token) {
      return;
    }

    this.http.get<Movement[]>(
      `${API}/movimientos/historial`,
      { headers: this.headers }
    ).subscribe({
      next: movements => {
        this.movements = movements;
        this.applyHistoryFilters();
      },
      error: error => this.showError(error)
    });
  }

  applyHistoryFilters(): void {
    const plate = this.historyPlate.trim().toUpperCase();

    this.filteredMovements = this.movements.filter(movement => {
      const matchesPlate =
        !plate || movement.placa?.toUpperCase().includes(plate);

      const entryDate = movement.fecha_hora_entrada.substring(0, 10);

      const matchesFrom =
        !this.fromDate || entryDate >= this.fromDate;

      const matchesTo =
        !this.toDate || entryDate <= this.toDate;

      const matchesState =
        !this.historyState || movement.estado === this.historyState;

      return matchesPlate && matchesFrom && matchesTo && matchesState;
    });
  }

  showError(error: HttpErrorResponse): void {
    this.messageType = 'error';

    const detail = error.error?.detail;

    this.message =
      typeof detail === 'string'
        ? detail
        : 'No fue posible completar la operación. Verifica el backend y tu conexión.';
  }

  date(value: string | null): string {
    return value
      ? new Intl.DateTimeFormat('es-CO', {
          dateStyle: 'medium',
          timeStyle: 'short'
        }).format(new Date(value))
      : 'En curso';
  }
}

