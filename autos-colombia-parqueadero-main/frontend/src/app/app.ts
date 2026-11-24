
import { CommonModule } from '@angular/common';
import {
  HttpClient,
  HttpErrorResponse,
  HttpHeaders,
  HttpParams
} from '@angular/common/http';
import { Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

type View = 'ingreso' | 'salida' | 'historial';

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

  token: string | null = null;
  currentUser: Usuario | null = null;

  loginUsername = '';
  loginPassword = '';

  view: View = 'ingreso';

  occupancy: Occupancy | null = null;
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

  busy = false;
  message = '';
  messageType: 'success' | 'error' | 'info' = 'info';

  ngOnInit(): void {
    // El usuario debe iniciar sesión para acceder al sistema.
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
    this.openMovement = null;
    this.entryPlate = '';
    this.exitPlate = '';
    this.message = '';
    this.view = 'ingreso';
  }

  setView(view: View): void {
    this.view = view;
    this.message = '';

    if (view === 'historial') {
      this.loadHistory();
    }
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

