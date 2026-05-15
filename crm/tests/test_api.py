"""
Integration tests for the CRM API.
Run: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
from app.main import app

# ── In-memory SQLite for tests ────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_crm.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="function")
def setup_db():
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────
def register_and_login(email="test@test.com", password="secret123", role="manager"):
    client.post("/api/v1/auth/register", json={
        "email": email, "full_name": "Test User", "password": password, "role": role
    })
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────────────────────
class TestAuth:
    def test_register_first_user_becomes_admin(self):
        resp = client.post("/api/v1/auth/register", json={
            "email": "first@test.com", "full_name": "First", "password": "pass123"
        })
        assert resp.status_code == 201
        assert resp.json()["role"] == "admin"

    def test_login_success(self):
        token = register_and_login()
        assert token is not None

    def test_login_wrong_password(self):
        register_and_login()
        resp = client.post("/api/v1/auth/login", json={
            "email": "test@test.com", "password": "wrong"
        })
        assert resp.status_code == 401

    def test_get_me(self):
        token = register_and_login()
        resp = client.get("/api/v1/auth/me", headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@test.com"

    def test_protected_route_without_token(self):
        resp = client.get("/api/v1/clients")
        assert resp.status_code == 403  # missing bearer


# ── Client tests ──────────────────────────────────────────────────────────────
class TestClients:
    def test_create_and_list_client(self):
        token = register_and_login()
        resp = client.post("/api/v1/clients", json={
            "company_name": "ACME Corp", "industry": "Tech", "status": "lead"
        }, headers=auth_header(token))
        assert resp.status_code == 201
        assert resp.json()["company_name"] == "ACME Corp"

        list_resp = client.get("/api/v1/clients", headers=auth_header(token))
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    def test_update_client(self):
        token = register_and_login()
        c = client.post("/api/v1/clients", json={"company_name": "Old Name"}, headers=auth_header(token)).json()
        resp = client.put(f"/api/v1/clients/{c['id']}", json={"company_name": "New Name"}, headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "New Name"

    def test_delete_client_requires_admin(self):
        # First registered user becomes admin
        admin_token = register_and_login()
        # Second user is manager
        manager_token = register_and_login("m@test.com", "pass123", "manager")
        c = client.post("/api/v1/clients", json={"company_name": "ToDelete"}, headers=auth_header(admin_token)).json()
        # manager cannot delete
        resp = client.delete(f"/api/v1/clients/{c['id']}", headers=auth_header(manager_token))
        assert resp.status_code == 403


# ── Deal tests ────────────────────────────────────────────────────────────────
class TestDeals:
    def test_create_deal_sets_probability(self):
        token = register_and_login()
        c = client.post("/api/v1/clients", json={"company_name": "Biz"}, headers=auth_header(token)).json()
        resp = client.post("/api/v1/deals", json={
            "title": "Big Deal", "client_id": c["id"], "stage": "negotiation", "amount": 50000
        }, headers=auth_header(token))
        assert resp.status_code == 201
        assert resp.json()["probability"] == 75

    def test_pipeline_endpoint(self):
        token = register_and_login()
        c = client.post("/api/v1/clients", json={"company_name": "Biz"}, headers=auth_header(token)).json()
        client.post("/api/v1/deals", json={"title": "D1", "client_id": c["id"], "stage": "proposal"}, headers=auth_header(token))
        resp = client.get("/api/v1/deals/pipeline", headers=auth_header(token))
        assert resp.status_code == 200
        assert "proposal" in resp.json()


# ── Analytics tests ───────────────────────────────────────────────────────────
class TestAnalytics:
    def test_summary(self):
        token = register_and_login()
        resp = client.get("/api/v1/analytics/summary", headers=auth_header(token))
        assert resp.status_code == 200
        data = resp.json()
        assert "clients" in data
        assert "deals" in data
        assert "tasks" in data
