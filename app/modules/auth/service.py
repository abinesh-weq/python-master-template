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
    validate_access_token,
    validate_refresh_token,
    hash_password,
    verify_password,
    get_token_subject,
    get_token_jti,
)
from app.modules.auth.schemas import (
    MfaPendingResponse,
    PasswordLoginRequest,
    RegisterRequest,
    AdminRegisterRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
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
        payload: RegisterRequest | AdminRegisterRequest,
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
                email_otp = getattr(payload, "email_otp", None)
                if not email_otp:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Email OTP is required for registration.",
                    )
                email_valid = await otp_service.verify_otp(
                    db, identifier=payload.email, otp_type="EMAIL_OTP", otp_code=email_otp
                )
                if not email_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired email OTP.",
                    )

            # Validate Mobile OTP if phone was provided
            if payload.phone_number:
                mobile_otp = getattr(payload, "mobile_otp", None)
                if not mobile_otp:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Mobile OTP is required for registration.",
                    )
                mobile_valid = await otp_service.verify_otp(
                    db, identifier=payload.phone_number, otp_type="MOBILE_OTP", otp_code=mobile_otp
                )
                if not mobile_valid:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid or expired mobile OTP.",
                    )

        # Determine role
        role_name_to_lookup = assigned_role_name or payload.role_name
        role_uuid = None
        
        if role_name_to_lookup:
            role_record = await rbac_service.get_role_by_name(db, role_name_to_lookup)
            if not role_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Role '{role_name_to_lookup}' not found."
                )
            role_uuid = role_record.uuid

        if not role_uuid:
            # Auto-assign default USER for public registration
            default_role = await rbac_service.get_role_by_name(
                db, settings.DEFAULT_USER_ROLE
            )
            if default_role:
                role_uuid = default_role.uuid

        create_payload = UserCreateRequest(
            name=payload.username, # Default name to username if not provided separately
            username=payload.username,
            email=payload.email,
            phone_number=payload.phone_number,
            password=payload.password,
            provider="LOCAL",
            role_uuid=role_uuid,
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

    async def register_with_tokens(
        self,
        db: AsyncSession,
        payload: RegisterRequest | AdminRegisterRequest,
        skip_otp: bool = False,
        assigned_role_name: Optional[str] = None,
    ) -> TokenResponse:
        """
        Register user and immediately issue tokens (auto-login).
        Same validation as register() but returns TokenResponse.
        """
        # Reuse existing registration logic
        user = await self.register(db, payload, skip_otp, assigned_role_name)
        
        # Issue tokens immediately (auto-login)
        return await self._issue_tokens(db, user)

    # ── Password Login Flow ────────────────────────────────────────────────────

    async def login_password(
        self, db: AsyncSession, payload: PasswordLoginRequest
    ) -> TokenResponse | MfaPendingResponse:
        """
        If MFA is enabled → send OTP and return 202-style MfaPendingResponse.
        Else → issue full token pair.
        Supports both email and phone number login.
        """
        # Determine identifier and lookup method
        if payload.email:
            identifier = payload.email
            user = await user_service.get_by_email(db, identifier)
        else:
            identifier = payload.phone_number
            user = await user_service.get_by_phone(db, identifier)
        
        if not user or not user.is_active:
            # Provide specific error based on identifier type
            if payload.email:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email not registered. Please sign up first.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Phone number not registered. Please sign up first.",
                )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive. Please contact support.",
            )

        if user.is_mfa_enabled:
            if user.email:
                recipient = user.email
                template_code = "OTP_EMAIL"
                msg = "MFA OTP has been sent. Please check your registered email."
            elif user.phone_number:
                recipient = user.phone_number
                template_code = "OTP_SMS"
                msg = "MFA OTP has been sent. Please check your registered mobile number."
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid email or mobile number found to send MFA OTP.",
                )

            # Trigger OTP dispatch via integration engine
            otp = await otp_service.send_otp(db, recipient, "MFA", settings.OTP_EXPIRE_MINUTES)
            await integration_service.dispatch(
                db=db,
                template_code=template_code,
                recipient=recipient,
                variables={"OTP": otp, "USERNAME": user.username},
            )
            return MfaPendingResponse(message=msg)

        # Check if Password login is allowed for this role
        await self._check_login_allowed(db, user, "pwd_login_allowed")

        if user.provider != "LOCAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This account uses {user.provider} login. Use social login instead.",
            )
        
        if not user.password or not verify_password(payload.password, user.password):
            # Provide specific error based on identifier type
            if payload.email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid phone number or password.",
                )
        
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

    # ── OTP Login (unified) ────────────────────────────────────────────────────

    async def login_otp(
        self, db: AsyncSession, identifier: str, identifier_type: str, otp: str
    ) -> TokenResponse:
        """
        Single entry point for OTP-based login.
        identifier_type is resolved by OtpLoginRequest before reaching here:
          "email"  → lookup by email,  verify EMAIL_OTP
          "mobile" → lookup by phone,  verify MOBILE_OTP
        """
        if identifier_type == "email":
            user = await user_service.get_by_email(db, identifier)
            otp_type = "EMAIL_OTP"
            login_field = "email_otp_login_allowed"
        else:
            user = await user_service.get_by_phone(db, identifier)
            otp_type = "MOBILE_OTP"
            login_field = "mobile_otp_login_allowed"

        if not user:
            # Provide specific error based on identifier type
            if identifier_type == "email":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Email not registered. Please sign up first.",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Phone number not registered. Please sign up first.",
                )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive. Please contact support.",
            )

        await self._check_login_allowed(db, user, login_field)

        valid = await otp_service.verify_otp(db, identifier, otp_type, otp)
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP.",
            )

        await otp_service.invalidate_otp(db, identifier, otp_type)
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
                role_uuid=default_role.uuid if default_role else None,
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

        # Determine channel and template
        if otp_type == "MOBILE_OTP":
            template_code = "OTP_SMS"
        else:
            template_code = "OTP_EMAIL"

        dispatch_success = await integration_service.dispatch(
            db=db,
            template_code=template_code,
            recipient=identifier,
            variables={"OTP": otp, "USERNAME": ""},
        )

        if not dispatch_success:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to send OTP; please try again later.",
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

    async def change_password(
        self, db: AsyncSession, user_uuid: str, payload: ChangePasswordRequest
    ) -> None:
        user = await user_service.get_by_uuid(db, user_uuid)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not registered. Please sign up first.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive. Please contact support.",
            )
        if user.provider != "LOCAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"This account uses {user.provider} login. Please change your password there.",
            )
        if not user.password or not verify_password(payload.old_password, user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect old password.",
            )
        user.password = hash_password(payload.new_password)
        await db.flush()

    # ── Refresh Token Flow ─────────────────────────────────────────────────────

    async def refresh_token(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        """
        Validates refresh token from DB, revokes old token (rotation),
        issues a new access + refresh pair.
        Enhanced with proper token validation per specification.
        """
        # 1. Validate refresh token structure and claims
        try:
            payload = validate_refresh_token(refresh_token)
            user_email = payload.get("sub")  # Email as subject per specification
            jti = payload.get("jti")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token format.",
            )

        # 2. Check DB — token must exist and not be revoked
        stored = await rbac_service.get_refresh_token(db, refresh_token)
        if not stored or stored.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked or does not exist.",
            )

        # 3. Load user by email (JWT subject)
        user = await user_service.get_by_email(db, user_email)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive.",
            )

        # 5. Rotate — revoke old, issue new pair (proper token rotation)
        await rbac_service.revoke_refresh_token(db, refresh_token)
        
        # Revoke all other refresh tokens for this user for enhanced security
        await rbac_service.revoke_all_user_tokens(db, user.uuid)
        
        return await self._issue_tokens(db, user)

    # ── Internal Helpers ───────────────────────────────────────────────────────

    async def _authenticate_user(
        self, db: AsyncSession, email: str, password: str
    ) -> UserLogin:
        user = await user_service.get_by_email(db, email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Email not registered. Please sign up first.",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive. Please contact support.",
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
                detail="Invalid email or password.",
            )
        return user

    async def _check_login_allowed(self, db: AsyncSession, user: UserLogin, field: str):
        """Helper to verify if a role permits a specific login method."""
        if user.role_uuid:
            role = await rbac_service.get_role_by_uuid(db, user.role_uuid)
            if role and not getattr(role, field, True):
                method_name = field.replace("_allowed", "").replace("_", " ").title()
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"{method_name} is disabled for your role.",
                )

    async def _issue_tokens(self, db: AsyncSession, user: UserLogin) -> TokenResponse:
        """Creates access + refresh token pair and persists refresh token."""
        # Use user email as subject per specification
        access_token = create_access_token(subject=user.email, extra_claims={"uuid": user.uuid})
        refresh_token = create_refresh_token(subject=user.email)

        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(days=7)  # Fixed 7 days per specification
        ).isoformat()

        await rbac_service.save_refresh_token(
            db, user_uuid=user.uuid, token=refresh_token, expires_at=expires_at
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
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
