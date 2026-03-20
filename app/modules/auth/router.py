from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import ApiResponse
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.middlewares import limiter
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    MfaLoginRequest,
    MfaPendingResponse,
    OtpLoginRequest,
    PasswordLoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendOtpRequest,
    SocialLoginRequest,
    TokenResponse,
    VerifyOtpRequest,
)
from app.modules.auth.service import auth_service
from app.modules.audit.service import audit_service


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# ── Public Registration (OTP required) ───────────────────────────────────────
@router.post("/register", response_model=ApiResponse)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await auth_service.register(db, payload, skip_otp=False)
    
    # Audit trail (success)
    await audit_service.log(
        db=db,
        user_id=user.id,
        username=user.username,
        action="USER_REGISTER",
        module="AUTH",
        payload=payload.model_dump(),
        description="Public registration.",
        request=request,
        status_code=status.HTTP_200_OK
    )
    
    return ApiResponse.success(
        message="Registration successful.",
        data={"id": user.id, "email": user.email},
    )


# ── Admin Registration (OTP skipped, JWT secured) ────────────────────────────
@router.post("/admin/register", response_model=ApiResponse)
async def admin_register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("USER_MANAGEMENT", "WRITE")),
):
    user = await auth_service.register(db, payload, skip_otp=True)
    return ApiResponse.success(
        message="Admin registration successful.",
        data={"id": user.id, "email": user.email},
    )


# ── Password Login ────────────────────────────────────────────────────────────
@router.post("/login/password", response_model=ApiResponse)
@limiter.limit("5/minute")
async def login_password(
    request: Request,
    payload: PasswordLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        result = await auth_service.login_password(db, payload)
        
        status_code = status.HTTP_202_ACCEPTED if isinstance(result, MfaPendingResponse) else status.HTTP_200_OK
        
        # Log success
        await audit_service.log(
            db=db,
            username=payload.email,
            action="LOGIN_PASSWORD",
            module="AUTH",
            description="Login via password.",
            request=request,
            status_code=status_code,
            response_body=result if status_code == 202 else None  # Save MFA info for debug
        )
    except HTTPException as e:
        # Log failed login attempt
        await audit_service.log(
            db=db,
            username=payload.email,
            action="LOGIN_PASSWORD_FAILED",
            module="AUTH",
            description=f"Error: {e.detail}",
            request=request,
            status_code=e.status_code,
            response_body={"detail": e.detail}
        )
        raise e

    if isinstance(result, MfaPendingResponse):
        # 202 Accepted — MFA required
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=ApiResponse.success(
                message=result.message, data=result.model_dump()
            ).model_dump(),
        )
    return ApiResponse.success(message="Login successful.", data=result.model_dump())


# ── MFA Login ─────────────────────────────────────────────────────────────────
@router.post("/login/mfa", response_model=ApiResponse)
async def login_mfa(
    payload: MfaLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login_mfa(
        db, payload.email, payload.password, payload.mfa_otp
    )
    return ApiResponse.success(
        message="MFA login successful.", data=tokens.model_dump()
    )


# ── Email OTP Login ───────────────────────────────────────────────────────────
@router.post("/login/email-otp", response_model=ApiResponse)
async def login_email_otp(
    payload: OtpLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login_email_otp(db, payload.identifier, payload.otp)
    return ApiResponse.success(message="Login successful.", data=tokens.model_dump())


# ── Mobile OTP Login ──────────────────────────────────────────────────────────
@router.post("/login/mobile-otp", response_model=ApiResponse)
async def login_mobile_otp(
    payload: OtpLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login_mobile_otp(db, payload.identifier, payload.otp)
    return ApiResponse.success(message="Login successful.", data=tokens.model_dump())


# ── Social Login ──────────────────────────────────────────────────────────────
@router.post("/login/google", response_model=ApiResponse)
async def login_google(payload: SocialLoginRequest, db: AsyncSession = Depends(get_db)):
    payload.provider = "GOOGLE"
    tokens = await auth_service.login_social(db, payload)
    return ApiResponse.success(
        message="Google login successful.", data=tokens.model_dump()
    )


@router.post("/login/facebook", response_model=ApiResponse)
async def login_facebook(
    payload: SocialLoginRequest, db: AsyncSession = Depends(get_db)
):
    payload.provider = "FACEBOOK"
    tokens = await auth_service.login_social(db, payload)
    return ApiResponse.success(
        message="Facebook login successful.", data=tokens.model_dump()
    )


@router.post("/login/apple", response_model=ApiResponse)
async def login_apple(payload: SocialLoginRequest, db: AsyncSession = Depends(get_db)):
    payload.provider = "APPLE"
    tokens = await auth_service.login_social(db, payload)
    return ApiResponse.success(
        message="Apple login successful.", data=tokens.model_dump()
    )


# ── OTP Operations ────────────────────────────────────────────────────────────
@router.post("/send-otp", response_model=ApiResponse)
@limiter.limit("3/minute")
async def send_otp(
    request: Request,
    payload: SendOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.send_otp(db, payload.identifier, payload.otp_type)
    return ApiResponse.success(message="OTP sent successfully.")


@router.post("/verify-otp", response_model=ApiResponse)
async def verify_otp(
    payload: VerifyOtpRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    valid = await auth_service.verify_otp(
        db, payload.identifier, payload.otp_type, payload.otp
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP.",
        )
    return ApiResponse.success(message="OTP verified successfully.")


# ── Password Reset ────────────────────────────────────────────────────────────
@router.post("/forgot-password", response_model=ApiResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.forgot_password(db, payload.email)
    return ApiResponse.success(
        message="If this email exists, a reset OTP has been sent."
    )


@router.post("/reset-password", response_model=ApiResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.reset_password(db, payload)
    
    await audit_service.log(
        db=db,
        username=payload.email,
        action="RESET_PASSWORD",
        module="AUTH",
        description="Password reset via OTP completed.",
        payload=payload.model_dump()
    )
    
    return ApiResponse.success(message="Password reset successful.")


# ── Token Refresh ─────────────────────────────────────────────────────────────
@router.post("/refresh-token", response_model=ApiResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.refresh_access_token(db, payload.refresh_token)
    return ApiResponse.success(
        message="Token refreshed successfully.", data=tokens.model_dump()
    )


# ── Logout (Revoke Refresh Token) ─────────────────────────────────────────────
@router.post("/logout", response_model=ApiResponse)
async def logout(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    from app.modules.rbac.service import rbac_service

    await rbac_service.revoke_refresh_token(db, payload.refresh_token)
    return ApiResponse.success(message="Logged out successfully.")
