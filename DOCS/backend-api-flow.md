# WeQ Standalone Backend (FastAPI) - Common Template Guide

## 1. Overview

This document describes the backend architecture, module responsibilities, and complete API flows that frontend developers use for end-to-end features.

- Framework: FastAPI
- DB: SQLAlchemy Async + Alembic migrations
- Auth: JWT + refresh token + MFA + OTP + social
- RBAC: module-permission matrix + user overrides
- In-memory caching: fastapi-cache2
- Rate limiting: slowapi
- App-level stable endpoints: `/health`, `/api/v1/admin/cache/clear`


## 2. Project Structure (Features)

- `app/core`
  - `config.py`: settings + env variables
  - `database.py`: engine + session
  - `dependencies.py`: auth & permission dependencies
  - `middlewares.py`: logging, audits, request id, rate limit
  - `exceptions.py`: global handler

- `app/modules/auth`
  - authentication flows (
    `/api/v1/auth/*`)

- `app/modules/users`
  - admin user CRUD

- `app/modules/rbac`
  - RBAC roles/modules/mappings

- `app/modules/predefined`
  - master data list/config (read-heavy, cache + clear on mutation)

- `app/modules/integration`
  - dynamic provider/API mapping/config endpoints

- `main.py`
  - app startup/shutdown
  - router registration
  - health and cache APIs


## 3. Configuration (ENV / settings)

Key settings in `.env` / `config.py`:
- `DATABASE_URL`: SQLAlchemy async DSN
- `APP_NAME`, `APP_VERSION`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM` (HS256, HS384, HS512)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`
- `AUTH_ENABLED` (0 for dev bypass, 1 production)
- `CORS_ORIGINS`


## 4. Startup Sequence (Backend)

1. `main.py` app starts.
2. `on_startup()` initializes `FastAPICache` InMemory backend.
3. middleware layers attach (RequestId -> Logging -> Audit -> CORS).
4. global exception handlers registered.
5. routers mounted.


## 5. Auth API flows (frontend integration)

Base route: `/api/v1/auth`

### 5.1 Public registration
- `POST /register`
- Request: `email, password, name, phone, otp` (or auto-sent OTP)
- Behaviour: `auth_service.register(skip_otp=False)`
- Response: user id/email

### 5.2 Admin registration
- `POST /admin/register` (RBAC protected)
- `skip_otp=True`

### 5.3 Login
- `POST /login/password`
- Returns either `TokenResponse` or `MfaPendingResponse` (202)

### 5.4 MFA
- `POST /login/mfa`
- Input: email, password, mfa_otp

### 5.5 OTP login
- `POST /login/email-otp` or `/login/mobile-otp`

### 5.6 Social login
- `POST /login/google`, `/login/facebook`, `/login/apple`

### 5.7 Token management
- `POST /refresh-token` returns new access token.
- `POST /forgot-password` + `POST /reset-password`
- `POST /change-password` (auth required)

### Frontend notes
- Accept `AccessToken` + `RefreshToken` from auth responses.
- Store tokens in secure storage (HttpOnly cookie or secure local storage, according to app policy).
- Include `Authorization: Bearer <access_token>` on protected API calls.
- On 401/403, auto refresh token using `/refresh-token`, then retry.


## 6. User Admin APIs

Base route: `/api/v1/admin/users`

### 6.1 List users
- `GET /` with optional `search`, `is_active`, `page`, `size`
- `PaginatedResponse` with stable metadata.

### 6.2 Get user
- `GET /{uuid}`

### 6.3 Update user
- `PUT /{uuid}`

### 6.4 Delete user
- `DELETE /{uuid}`

### 6.5 Admin reset password
- `PUT /{uuid}/password`

Permissions needed:
- `USER_MANAGEMENT`: READ, UPDATE, DELETE


## 7. RBAC APIs

Base route: `/api/v1/admin/rbac`

### 7.1 Roles
- `GET /roles`
- `POST /roles`
- `DELETE /roles/{uuid}`

### 7.2 Modules
- `GET /modules`

### 7.3 Role-module mappings
- `GET /roles/{role_uuid}/modules`
- `PUT /roles/{role_uuid}/modules/{module_uuid}`
- `DELETE /roles/{role_uuid}/modules/{module_uuid}`

### 7.4 User access override
- `GET /users/{user_uuid}/access`
- `PUT /users/{user_uuid}/access/{module_uuid}`
- `DELETE /users/{user_uuid}/access/{module_uuid}`

Permissions needed:
- `RBAC_MANAGEMENT` READ/WRITE/UPDATE/DELETE


## 8. Predefined Master APIs + caching

Base route: `/api/v1/predefined`

### 8.1 List master items
- `GET /` with filters (`entity_type`, `name`, `code`, `parent_uuid`, `page`, `size`)
- cached via `@cache(expire=3600)`

### 8.2 CRUD
- `GET /{uuid}`
- `POST /` (WRITE)
- `PUT /{uuid}` (UPDATE)
- `DELETE /{uuid}` (DELETE)

Mutation calls clear cached data via `FastAPICache.clear()`.

Permissions needed: MASTER READ/WRITE/UPDATE/DELETE


## 9. Integration APIs

Base route: `/api/v1/admin/integration`

### 9.1 Provider config
- `GET /providers`, `GET /providers/{uuid}`
- `POST /providers`, `PUT /providers/{uuid}`, `DELETE /providers/{uuid}`

### 9.2 Provider metadata
- `GET /metadata/{provider_uuid}`
- `POST /metadata`, `PUT /metadata/{provider_uuid}`, `DELETE /metadata/{provider_uuid}`

### 9.3 Provider API mappings
- `GET /mappings`, `GET /mappings/{uuid}`
- `POST /mappings`, `PUT /mappings/{uuid}`, `DELETE /mappings/{uuid}`

### 9.4 Notification templates
- `GET /templates`, `POST /templates` (`code` uniqueness check)
- `PUT /templates/{uuid}`, `DELETE /templates/{uuid}`

Permissions needed: INTEGRATION_MANAGEMENT READ/WRITE/UPDATE/DELETE


## 10. Health + cache endpoints

- `GET /health`: checks DB and cache connectivity, returns status + components.
- `POST /api/v1/admin/cache/clear`: instance cache clear (admin). This uses `FastAPICache.clear()`.

Frontend can use `/health` for UI status badges, uptime checks, synthetic monitor.


## 11. Workflow Examples

### 11.1 App startup sequence (frontend perspective)
1. Call `/health` to verify backend readiness.
2. Call `POST /api/v1/auth/login/password` to sign in.
3. Store JWT and call `GET /api/v1/admin/users` with auth header.
4. For a cached dataset (predefined), call `GET /api/v1/predefined`.
5. After admin updates data, call `/api/v1/admin/cache/clear`.

### 11.2 User creation and role binding
1. As superadmin, call `POST /api/v1/auth/admin/register`.
2. Create role via `/api/v1/admin/rbac/roles`.
3. Attach module perms via `/api/v1/admin/rbac/roles/{role_uuid}/modules/{module_uuid}`.
4. Optionally override user permissions via `/api/v1/admin/rbac/users/{user_uuid}/access/{module_uuid}`.


## 12. Recommendations

- For production:
  - `AUTH_ENABLED=1`, secure JWT secret and algorithm (HS512/RS256).
  - Use Redis-backed cache instead of in-memory for distributed scaling.
  - Add TLS termination in ingress and secure cookies for refresh tokens.
  - Use proper role mapping in frontend to hide disabled features.

- Further improvements:
  - add paginated, filterable audit logs endpoint in `app/modules/audit`.
  - add WebSocket event bus for realtime config updates.
  - use FastAPI lifespans to replace `@app.on_event` deprecation.

---

This file is intended to be used as the single source of truth for frontend integration and backend common template usage.  