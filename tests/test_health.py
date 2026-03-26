from app.core.config import settings


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["UP", "DOWN"]
    assert data["version"] == settings.APP_VERSION
    assert data["components"]["database"]["status"] in ["UP", "DOWN"]
    assert data["components"]["cache"]["status"] in ["UP", "DOWN"]


def test_cache_clear_endpoint(client):
    response = client.post("/api/v1/admin/cache/clear")
    assert response.status_code == 200
    assert response.json() == {"status": "SUCCESS", "message": "Cache cleared"}


def test_refresh_token_invalid_returns_401(client):
    response = client.post("/api/v1/auth/refresh-token", json={"refresh_token": "invalid_token"})
    assert response.status_code == 401
    data = response.json()
    assert data.get("status") == "ERROR"
    assert data.get("errorCode") == "401"


def test_email_otp_identifier_validates_as_email(client):
    payload = {
        "identifier": "abinesh@gmail.com",
        "otp": "123456",
    }
    response = client.post("/api/v1/auth/login/email-otp", json=payload)
    assert response.status_code != 422


def test_mobile_otp_identifier_validates_as_phone(client):
    payload = {
        "identifier": "9876543210",
        "otp": "123456",
    }
    response = client.post("/api/v1/auth/login/mobile-otp", json=payload)
    assert response.status_code != 422


def test_mobile_otp_identifier_normalization(client):
    payload = {
        "identifier": " +91 98765-43210 ",
        "otp": "123456",
    }
    response = client.post("/api/v1/auth/login/mobile-otp", json=payload)
    # 401 if user not found, but validation should pass; not 422
    assert response.status_code in (401, 200)


def test_mobile_otp_identifier_invalid_format(client):
    payload = {"identifier": "(abc) 123-4567", "otp": "123456"}
    response = client.post("/api/v1/auth/login/mobile-otp", json=payload)
    assert response.status_code == 422


def test_invalid_identifier_returns_422(client):
    payload = {
        "identifier": "bad@identifier",
        "otp": "123456",
    }
    response = client.post("/api/v1/auth/login/email-otp", json=payload)
    assert response.status_code == 422


def test_email_identifier_rules(client):
    valid_payload = {"identifier": "abinesh@gmail.com", "otp": "123456"}
    assert client.post("/api/v1/auth/login/email-otp", json=valid_payload).status_code != 422

    invalid_payloads = [
        {"identifier": " abinesh@gmail.com", "otp": "123456"},
        {"identifier": "abinesh@gmail.com ", "otp": "123456"},
        {"identifier": "abinesh@gmailcom", "otp": "123456"},
        {"identifier": "abinesh@@gmail.com", "otp": "123456"},
        {"identifier": "abinesh@.com", "otp": "123456"},
        {"identifier": "@gmail.com", "otp": "123456"},
    ]

    for payload in invalid_payloads:
        response = client.post("/api/v1/auth/login/email-otp", json=payload)
        assert response.status_code == 422


def test_invalid_data_returns_422(client):
    response = client.post(
        "/api/v1/auth/admin/register",
        json={"username": "testuser", "password": "weak", "email": "user@example.com"},
    )
    assert response.status_code == 422


import uuid


def test_duplicate_user_conflict_returns_409(client):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "username": f"dupuser_{unique}",
        "email": f"dup-{unique}@localhost.com",
        "password": "StrongP@ssword1",
    }
    first = client.post("/api/v1/auth/admin/register", json=payload)
    assert first.status_code in (200, 201)

    second = client.post("/api/v1/auth/admin/register", json=payload)
    assert second.status_code == 409
