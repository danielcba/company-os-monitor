# Phase 13 — Frontend Token Security Design

## Threat Model

### Current State (localStorage)
- Access token stored in `localStorage` → vulnerable to XSS
- Refresh token stored in `localStorage` → vulnerable to XSS
- Any XSS attack can steal both tokens
- JavaScript can access tokens at any time

### Target State (HttpOnly Cookies)
- Access token: short-lived (15min), can stay in memory (SPA needs it for Authorization header)
- Refresh token: HttpOnly, Secure, SameSite=Strict cookie
- JavaScript cannot access refresh token
- XSS attacks cannot steal refresh token
- CSRF protection via SameSite attribute

## Migration Strategy

### Phase 1: Backend Support (Current)
- Backend sets refresh token as HttpOnly cookie on `/auth/login` and `/auth/refresh`
- Backend still returns refresh_token in response body for backward compatibility
- Frontend can still use localStorage as fallback

### Phase 2: Frontend Migration
- Frontend reads refresh token from cookie (via `document.cookie`)
- Frontend stops storing refresh token in localStorage
- Frontend still uses in-memory storage for access token (needed for Authorization header)

### Phase 3: Cleanup
- Backend stops returning refresh_token in response body
- Frontend removes localStorage refresh token code
- Remove fallback code

## Cookie Configuration

```typescript
// Backend: Set refresh token cookie
Set-Cookie: refresh_token=<token>; 
  HttpOnly; 
  Secure; 
  SameSite=Strict; 
  Path=/api/v1/auth/refresh;
  Max-Age=604800;  // 7 days
```

## Tests Required

1. Refresh token is HttpOnly (not accessible via JavaScript)
2. Refresh token is Secure (only sent over HTTPS)
3. Refresh token has SameSite=Strict
4. Access token is short-lived (15min)
5. Refresh token rotation still works
6. Logout clears the cookie
7. CSRF protection works
