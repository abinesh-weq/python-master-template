from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.otp import otp_service
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import (
    MfaPendingResponse,
    PasswordLoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SocialLoginRequest,
    TokenResponse,
)
from app.modules.integration.service import integration_service
from app.modules.rbac.service import rbac_service
from app.modules.users.models import UserLogin
from app.modules.users.schemas import UserCreateRequest
from app.modules.users.service import user_service


class AuthService:

    # ── Registration Flow ──────────────────────────────────────────────────────

    async def register(
        self,
        db: AsyncSession,
        payload: RegisterRequest,
        skip_otp: bool = False,
        assigned_role_name: Optional[str] = None,
    ) -> UserLogin:
        """
        Public registration — validates email + mobile OTP before creating user.
        Admin registration passes skip_otp=True.
        """
        # Check duplicate email
        if payload.email:
            existing_email = await user_service.get_by_email(db, payload.email)
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email is already registered.",
                )

        # Check duplicate phone
        if payload.phone_number:
            existing_phone = await user_service.get_by_phone(db, payload.phone_number)
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone number is already registered.",
                )

        if not skip_otp:
            # Validate Email OTP if email was provided
            if payload.email:
                if not payload.email_otp:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email OTP is required for registration.",
                    )
                email_valid = await otp_service.verify_otp(
                    db, identifier=payload.email, otp_type="EMAIL_OTP", otp_code=payload.email_otp
                )
                if not email_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired email OTP.",
                    )

            # Validate Mobile OTP if phone was provided
            if payload.phone_number:
                if not payload.mobile_otp:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Mobile OTP is required for registration.",
                    )
                mobile_valid = await otp_service.verify_otp(
                    db, identifier=payload.phone_number, otp_type="MOBILE_OTP", otp_code=payload.mobile_otp
                )
                if not mobile_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired mobile OTP.",
                    )

        # Determine role
        role_name_to_lookup = assigned_role_name or payload.role_name
        role_id = None
        
        if role_name_to_lookup:
            role_record = await rbac_service.get_role_by_name(db, role_name_to_lookup)
            if not role_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{role_name_to_lookup}' not found."
                )
            role_id = role_record.id

        if not role_id:
            # Auto-assign default ROLE_USER for public registration
            default_role = await rbac_service.get_role_by_name(
                db, settings.DEFAULT_USER_ROLE
            )
            if default_role:
                role_id = default_role.id

        create_payload = UserCreateRequest(
            name=payload.username, # Default name to username if not provided separately
            username=payload.username,
            email=payload.email,
            phone_number=payload.phone_number,
            password=payload.password,
            provider="LOCAL",
            role_id=role_id,
            is_verified=True # Registration via OTP implies verification
        )
        user = await user_service.create_user(db, create_payload)
        
        # Cleanup used OTPs
        if not skip_otp:
            if payload.email:
                await otp_service.invalidate_otp(db, payload.email, "EMAIL_OTP")
            if payload.phone_number:
                await otp_service.invalidate_otp(db, payload.phone_number, "MOBILE_OTP")
                
        return user

    # ── Password Login Flow ────────────────────────────────────────────────────

    async def login_password(
        self, db: AsyncSession, payload: PasswordLoginRequest
    ) -> TokenResponse | MfaPendingResponse:
        """
        If MFA is enabled → send OTP and return 202-style MfaPendingResponse.
        Else → issue full token pair.
        """
        user = await self._authenticate_user(db, payload.email, payload.password)

        if user.is_mfa_enabled:
            # Trigger OTP dispatch via integration engine
            otp = await otp_service.send_otp(db, user.email, "MFA", settings.OTP_EXPIRE_MINUTES)
            print("MFA OTP: ", otp)
            await integration_service.dispatch(
                db=db,
                template_code="OTP_EMAIL",
                recipient=user.email,
                variables={"OTP": otp, "USERNAME": user.username},
            )
            return MfaPendingResponse()

        if payload.device_id:
            user.device_id = payload.device_id
            await db.flush()

        return await self._issue_tokens(db, user)

    # ── MFA Login ──────────────────────────────────────────────────────────────

    async def login_mfa(
        self, db: AsyncSession, email: str, password: str, mfa_otp: str
    ) -> TokenResponse:
        user = await self._authenticate_user(db, email, password)
        valid = await otp_service.verify_otp(db, email, "MFA", mfa_otp)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired MFA OTP.",
            )
        # Invalidate OTP after use
        await otp_service.invalidate_otp(db, email, "MFA")
        return await self._issue_tokens(db, user)

    # ── Email OTP Login ────────────────────────────────────────────────────────

    async def login_email_otp(
        self, db: AsyncSession, email: str, otp: str
    ) -> TokenResponse:
        user = await user_service.get_by_email(db, email)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive.",
            )

        # Check if Email OTP login is allowed for this role
        await self._check_login_allowed(db, user, "email_otp_login_allowed")

        valid = await otp_service.verify_otp(db, email, "EMAIL_OTP", otp)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired email OTP.",
            )
        # Invalidate OTP after use
        await otp_service.invalidate_otp(db, email, "EMAIL_OTP")
        return await self._issue_tokens(db, user)

    # ── Mobile OTP Login ───────────────────────────────────────────────────────

    async def login_mobile_otp(
        self, db: AsyncSession, phone: str, otp: str
    ) -> TokenResponse:
        user = await user_service.get_by_phone(db, phone)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive.",
            )

        # Check if Mobile OTP login is allowed for this role
        await self._check_login_allowed(db, user, "mobile_otp_login_allowed")

        valid = await otp_service.verify_otp(db, phone, "MOBILE_OTP", otp)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired mobile OTP.",
            )
        # Invalidate OTP after use
        await otp_service.invalidate_otp(db, phone, "MOBILE_OTP")
        return await self._issue_tokens(db, user)

    # ── Social / SSO Login ─────────────────────────────────────────────────────

    async def login_social(
        self, db: AsyncSession, payload: SocialLoginRequest
    ) -> TokenResponse:
        """
        Verifies provider token, auto-provisions user if first login.
        Supports GOOGLE, FACEBOOK, APPLE.
        """
        profile = await self._verify_social_token(
            payload.provider, payload.access_token
        )

        email = profile.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Social provider did not return an email address.",
            )

        user = await user_service.get_by_email(db, email)
        if not user:
            # Auto-provision
            default_role = await rbac_service.get_role_by_name(
                db, settings.DEFAULT_USER_ROLE
            )
            create_payload = UserCreateRequest(
                username=profile.get("name", email.split("@")[0]),
                email=email,
                provider=payload.provider.upper(),
                role_id=default_role.id if default_role else None,
            )
            user = await user_service.create_user(db, create_payload)
        else:
            if user.provider != payload.provider.upper():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Account registered with {user.provider}. Use that provider.",
                )

        # Check if Social login is allowed for this role
        await self._check_login_allowed(db, user, "social_login_allowed")

        if payload.device_id:
            user.device_id = payload.device_id
            await db.flush()

        return await self._issue_tokens(db, user)

    # ── OTP Operations ─────────────────────────────────────────────────────────

    async def send_otp(
        self,
        db: AsyncSession,
        identifier: str,
        otp_type: str,
    ) -> None:
        """
        Generates and dispatches OTP via integration engine.
        otp_type: EMAIL_OTP | MOBILE_OTP | MFA
        """
        otp = await otp_service.send_otp(db, identifier, otp_type, settings.OTP_EXPIRE_MINUTES)

        # Verification print
        print(f"DEBUG: OTP stored for {identifier} [{otp_type}] (hashed in DB)")

        # Determine channel and template
        if otp_type == "MOBILE_OTP":
            await integration_service.dispatch(
                db=db,
                template_code="OTP_SMS",
                recipient=identifier,
                variables={"OTP": otp},
            )
        else:
            await integration_service.dispatch(
                db=db,
                template_code="OTP_EMAIL",
                recipient=identifier,
                variables={"OTP": otp},
            )

    async def verify_otp(self, db: AsyncSession, identifier: str, otp_type: str, otp: str) -> bool:
        return await otp_service.verify_otp(db, identifier, otp_type, otp)

    # ── Password Reset ─────────────────────────────────────────────────────────

    async def forgot_password(self, db: AsyncSession, email: str) -> None:
        user = await user_service.get_by_email(db, email)
        if not user:
            # Silent fail — don't reveal account existence
            return
        otp = await otp_service.send_otp(db, email, "PASSWORD_RESET", settings.OTP_EXPIRE_MINUTES)
        await integration_service.dispatch(
            db=db,
            template_code="PASSWORD_RESET_EMAIL",
            recipient=email,
            variables={"OTP": otp, "USERNAME": user.username},
        )

    async def reset_password(
        self, db: AsyncSession, payload: ResetPasswordRequest
    ) -> None:
        valid = await otp_service.verify_otp(
            db, payload.email, "PASSWORD_RESET", payload.reset_otp
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password reset OTP.",
            )
        user = await user_service.get_by_email(db, payload.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        user.password = hash_password(payload.new_password)
        # Invalidate OTP after use
        await otp_service.invalidate_otp(db, payload.email, "PASSWORD_RESET")
        await db.flush()

    # ── Refresh Token Flow ─────────────────────────────────────────────────────

    async def refresh_access_token(
        self, db: AsyncSession, refresh_token: str
    ) -> TokenResponse:
        """
        Validates refresh token from DB, revokes old token (rotation),
        issues a new access + refresh pair.
        """
        # 1. Verify JWT signature & expiry
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise JWTError("Not a refresh token")
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        # 2. Check DB — token must exist and not be revoked
        stored = await rbac_service.get_refresh_token(db, refresh_token)
        if not stored:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked or does not exist.",
            )

        # 3. Load user
        user = await user_service.get_by_id(db, stored.user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
            )

        # 4. Rotate — revoke old, issue new pair
        await rbac_service.revoke_refresh_token(db, refresh_token)
        return await self._issue_tokens(db, user)

    # ── Internal Helpers ───────────────────────────────────────────────────────

    async def _authenticate_user(
        self, db: AsyncSession, email: str, password: str
    ) -> UserLogin:
        user = await user_service.get_by_email(db, email)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
            )

        # Check if Password login is allowed for this role
        await self._check_login_allowed(db, user, "pwd_login_allowed")

        if user.provider != "LOCAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This account uses {user.provider} login. Use social login instead.",
            )
        if not user.password or not verify_password(password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
            )
        return user

    async def _check_login_allowed(self, db: AsyncSession, user: UserLogin, field: str):
        """Helper to verify if a role permits a specific login method."""
        if user.role_id:
            role = await rbac_service.get_role_by_id(db, user.role_id)
            if role and not getattr(role, field, True):
                method_name = field.replace("_allowed", "").replace("_", " ").title()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{method_name} is disabled for your role.",
                )

    async def _issue_tokens(self, db: AsyncSession, user: UserLogin) -> TokenResponse:
        """Creates access + refresh token pair and persists refresh token."""
        access_token = create_access_token(subject=user.email)
        refresh_token = create_refresh_token(subject=user.email)

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        ).isoformat()

        await rbac_service.save_refresh_token(
            db, user_id=user.id, token=refresh_token, expires_at=expires_at
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    @staticmethod
    async def _verify_social_token(provider: str, access_token: str) -> dict:
        """
        Verifies the provider access token and returns the user profile.
        GOOGLE uses tokeninfo endpoint; FACEBOOK uses graph API.
        APPLE token verification uses apple-auth JWT approach (simplified here).
        """
        provider = provider.upper()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if provider == "GOOGLE":
                    resp = await client.get(
                        "https://www.googleapis.com/oauth2/v3/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                elif provider == "FACEBOOK":
                    resp = await client.get(
                        "https://graph.facebook.com/me",
                        params={
                            "fields": "id,name,email",
                            "access_token": access_token,
                        },
                    )
                elif provider == "APPLE":
                    # Apple sends an identity JWT — decode without verification for email claim
                    # In production, verify with Apple's public keys
                    import base64, json as _json

                    parts = access_token.split(".")
                    if len(parts) < 2:
                        raise HTTPException(
                            status_code=400, detail="Invalid Apple token."
                        )
                    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
                    profile_data = _json.loads(base64.urlsafe_b64decode(padded))
                    return profile_data
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unsupported provider: {provider}",
                    )

                if resp.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid {provider} access token.",
                    )
                return resp.json()
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Could not reach {provider} servers: {exc}",
            )


auth_service = AuthService()
