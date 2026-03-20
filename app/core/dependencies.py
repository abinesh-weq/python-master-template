from typing import Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.modules.rbac.service import rbac_service
from app.modules.users.service import user_service

bearer_scheme = HTTPBearer(auto_error=False)


# ── Current User Extraction ───────────────────────────────────────────────────

async def get_current_user_email(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> str:
    """
    Extracts user email (sub claim) from Bearer JWT.
    Raises 401 if token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise JWTError("Not an access token")
        email: str = payload.get("sub")
        if not email:
            raise JWTError("No subject in token")
        return email
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    email: str = Depends(get_current_user_email),
    db: AsyncSession = Depends(get_db),
):
    """Loads the full UserLogin record for the authenticated user."""
    user = await user_service.get_by_email(db, email)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )
    return user


# ── RBAC Permission Matrix ────────────────────────────────────────────────────

def require_permission(module_code: str, action: str) -> Callable:
    """
    Factory that returns a FastAPI Depends callable enforcing RBAC.

    Algorithm (mirrors Java RBAC interceptor):
    1. Parse JWT → extract user_id
    2. Resolve module_code → module_id in module_master
    3. Check access_control_master for user-specific override (ABSOLUTE precedence)
    4. If no override → fall back to role_module_mapping
    5. If both deny → raise HTTP 403

    Usage:
        @router.get("/", dependencies=[Depends(require_permission("USER_MANAGEMENT", "READ"))])
    """

    async def _check(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        # ── Step 2: Resolve module ─────────────────────────────────────────
        module = await rbac_service.get_module_by_code(db, module_code)
        if not module:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Module '{module_code}' is not configured in module_master.",
            )

        # ── Step 3: Check per-user override (access_control_master) ───────
        user_override = await rbac_service.get_user_access(db, current_user.id, module.id)
        if user_override:
            granted = _evaluate_action(user_override, action)
            if not granted:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: user override denies {action} on {module_code}.",
                )
            return current_user  # Override grants access — stop here

        # ── Step 4: Fall back to role_module_mapping ───────────────────────
        if not current_user.role_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User has no role assigned.",
            )

        role_mappings = await rbac_service.get_role_modules(db, current_user.role_id)
        role_mapping = next(
            (m for m in role_mappings if m.module_id == module.id), None
        )

        if not role_mapping or not _evaluate_action(role_mapping, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: role does not permit {action} on {module_code}.",
            )

        return current_user

    return _check


def _evaluate_action(mapping, action: str) -> bool:
    """Maps action string to the corresponding boolean column on a mapping record."""
    action_map = {
        "READ": "can_read",
        "WRITE": "can_write",
        "UPDATE": "can_update",
        "DELETE": "can_delete",
        "EXPORT": "can_export",
    }
    attr = action_map.get(action.upper())
    if not attr:
        return False
    return bool(getattr(mapping, attr, False))


# ── Pre-built Dependency Shortcuts ───────────────────────────────────────────
# These mirror Java @PreAuthorize("hasPermission(...)") shorthand


def require_user_management(action: str = "READ"):
    return require_permission("USER_MANAGEMENT", action)


def require_rbac_management(action: str = "READ"):
    return require_permission("RBAC_MANAGEMENT", action)


def require_master(action: str = "READ"):
    return require_permission("MASTER", action)
