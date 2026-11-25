import { HttpInterceptorFn } from '@angular/common/http';
import { Subject, tap } from 'rxjs';

/**
 * Angular 22 usa OnPush por defecto y la aplicación no tiene zone.js, así que
 * no se entera sola de que llegó una respuesta de la API. Este interceptor
 * avisa después de cada respuesta para que el componente redibuje la vista.
 */
export const apiResponded = new Subject<void>();

export const refreshViewInterceptor: HttpInterceptorFn = (req, next) => {
  const notify = () => queueMicrotask(() => apiResponded.next());

  return next(req).pipe(
    tap({ next: notify, error: notify })
  );
};
