import { HttpInterceptorFn } from '@angular/common/http';

/**
 * HTTP interceptor to add JWT token to requests
 * Note: In this implementation, authentication uses HTTP-only cookies
 * set by the backend, so no explicit token header is needed.
 * The browser automatically sends cookies with requests.
 * 
 * This interceptor is included for future extensibility if needed.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // Cookies are automatically included by the browser
  // No need to manually add Authorization header
  
  // Ensure credentials are included in requests
  const authReq = req.clone({
    withCredentials: true
  });

  return next(authReq);
};

