from typing import Annotated, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.common import ApiResponse, ApiRouter
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.middlewares import limiter
from app.modules.auth.params import API_PREFIX
from app.modules.auth.schemas import (
    ForgotPasswordRequest,
    MfaLoginRequest,
    MfaPendingResponse,
    OtpLoginRequest,
    PasswordLoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    AdminRegisterRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    SendOtpRequest,
    SocialLoginRequest,
    TokenResponse,
    VerifyOtpRequest,
    RegisterResponse,
)
from app.modules.auth.service import auth_service


router = ApiRouter(prefix=API_PREFIX, tags=["Authentication"])


# ── Public Registration (OTP required) ───────────────────────────────────────
@router.post("/register", response_model=ApiResponse[TokenResponse])
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    tokens = await auth_service.register_with_tokens(db, payload, skip_otp=False)
    
    return ApiResponse.success(
        message="Registration successful.",
        data=tokens.model_dump(),
    )


# ── Admin Registration (OTP skipped, JWT secured) ────────────────────────────
@router.post("/admin/register", response_model=ApiResponse[RegisterResponse])
async def admin_register(
    payload: AdminRegisterRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("USER_MANAGEMENT", "WRITE")),
):
    user = await auth_service.register(db, payload, skip_otp=True)
    return ApiResponse.success(
        message="Admin registration successful.",
        data={"id": user.id, "email": user.email},
    )


# ── Password Login ────────────────────────────────────────────────────────────
@router.post("/login/password", response_model=ApiResponse[Union[TokenResponse, MfaPendingResponse]])
@limiter.limit("5/minute")
async def login_password(
    request: Request,
    payload: PasswordLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await auth_service.login_password(db, payload)

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
@router.post("/login/mfa", response_model=ApiResponse[TokenResponse])
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


# ── OTP Login (unified — email or phone auto-detected) ───────────────────────
@router.post("/login/otp", response_model=ApiResponse[TokenResponse])
@limiter.limit("5/minute")
async def login_otp(
    request: Request,
    payload: OtpLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.login_otp(
        db, payload.identifier, payload.identifier_type, payload.otp
    )
    return ApiResponse.success(message="Login successful.", data=tokens.model_dump())


# ── Social Login ──────────────────────────────────────────────────────────────
@router.post("/login/google", response_model=ApiResponse[TokenResponse])
async def login_google(payload: SocialLoginRequest, db: AsyncSession = Depends(get_db)):
    payload.provider = "GOOGLE"
    tokens = await auth_service.login_social(db, payload)
    return ApiResponse.success(
        message="Google login successful.", data=tokens.model_dump()
    )


@router.post("/login/facebook", response_model=ApiResponse[TokenResponse])
async def login_facebook(
    payload: SocialLoginRequest, db: AsyncSession = Depends(get_db)
):
    payload.provider = "FACEBOOK"
    tokens = await auth_service.login_social(db, payload)
    return ApiResponse.success(
        message="Facebook login successful.", data=tokens.model_dump()
    )


@router.post("/login/apple", response_model=ApiResponse[TokenResponse])
async def login_apple(payload: SocialLoginRequest, db: AsyncSession = Depends(get_db)):
    payload.provider = "APPLE"
    tokens = await auth_service.login_social(db, payload)
    return ApiResponse.success(
        message="Apple login successful.", data=tokens.model_dump()
    )


# ── OTP Operations ────────────────────────────────────────────────────────────
@router.post("/send-otp", response_model=ApiResponse[None])
@limiter.limit("3/minute")
async def send_otp(
    request: Request,
    payload: SendOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.send_otp(db, payload.identifier, payload.otp_type)
    return ApiResponse.success(message="OTP sent successfully.")


@router.post("/verify-otp", response_model=ApiResponse[None])
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
@router.post("/forgot-password", response_model=ApiResponse[None])
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.forgot_password(db, payload.email)
    return ApiResponse.success(
        message="If this email exists, a reset OTP has been sent."
    )


@router.post("/reset-password", response_model=ApiResponse[None])
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await auth_service.reset_password(db, payload)
    
    return ApiResponse.success(message="Password reset successful.")

# ── Password Change ────────────────────────────────────────────────────────────
@router.post("/change-password", response_model=ApiResponse[None])
async def change_password(
    payload: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await auth_service.change_password(db, current_user.uuid, payload)
    return ApiResponse.success(message="Password changed successfully.")


# ── Token Refresh ─────────────────────────────────────────────────────────────
@router.post("/refresh-token", response_model=ApiResponse[TokenResponse])
async def refresh_token(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    tokens = await auth_service.refresh_token(db, payload.refresh_token)
    return ApiResponse.success(
        message="Token refreshed successfully.", data=tokens.model_dump()
    )


# ── Logout (Revoke Refresh Token) ─────────────────────────────────────────────
@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    from app.modules.rbac.service import rbac_service

    await rbac_service.revoke_refresh_token(db, payload.refresh_token)
    return ApiResponse.success(message="Logged out successfully.")
