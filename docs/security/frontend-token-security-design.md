# Frontend Token Security Design — Phase 13 / Phase 20.1

## Status: COMPLETE (All 3 phases implemented)

## Threat Model

### Current State (localStorage)
- Access token stored in `localStorage` → vulnerable to XSS
- Refresh token stored in `localStorage` → vulnerable to XSS
- Any XSS attack can steal both tokens
- JavaScript can access tokens at any time

### Target State (HttpOnly Cookies)
- Access token: short-lived (15min), stored in memory (SPA needs it for Authorization header)
- Refresh token: HttpOnly, Secure, SameSite=Lax cookie
- JavaScript cannot access refresh token
- XSS attacks cannot steal refresh token
- CSRF protection via SameSite attribute + Origin/Referer validation

## Migration Strategy

### Phase 1: Backend Support — COMPLETE
- Backend sets refresh token as HttpOnly cookie on `/auth/login` and `/auth/refresh`
- Backend does NOT return refresh_token in response body
- Frontend uses in-memory storage for access token

### Phase 2: Frontend Migration — COMPLETE
- Frontend sends `credentials: 'include'` on all requests (browser sends cookie automatically)
- Frontend does NOT store refresh token in any JavaScript-accessible storage
- Frontend uses in-memory storage for access token (needed for Authorization header)

### Phase 3: Cleanup — COMPLETE
- Backend does NOT accept `body.refresh_token` on `/auth/refresh` or `/auth/logout`
- Refresh token is HttpOnly cookie only
- No backward-compatible body fallback

## Cookie Configuration

```typescript
// Backend: Set refresh token cookie
Set-Cookie: refresh_token=<token>; 
  HttpOnly; 
  Secure; 
  SameSite=Lax;
  Path=/api/v1/auth/refresh;
  Max-Age=604800;  // 7 days
```

Note: SameSite=Lax (not Strict) is correct. Strict would block same-site navigations
which breaks the refresh flow when users navigate to the app from external links.
Lax blocks cross-site CSRF on state-changing requests while allowing same-site flow.

## Tests Required

1. Refresh token is HttpOnly (not accessible via JavaScript)
2. Refresh token is Secure (only sent over HTTPS)
3. Refresh token has SameSite=Strict
4. Access token is short-lived (15min)
5. Refresh token rotation still works
6. Logout clears the cookie
7. CSRF protection works
