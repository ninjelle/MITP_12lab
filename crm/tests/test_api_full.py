"""
Расширенный набор тестов CRM API с покрытием ≥ 90%.

Промпты, использованные для генерации тестов (Задание 7):

ПРОМПТ 1 — базовый (использован для генерации скелета):
  "Ты senior Python разработчик и QA-инженер. У меня есть FastAPI CRM приложение
   с сущностями: User, Client, Contact, Deal, Task. Роли: admin, manager, viewer.
   Сгенерируй pytest-тесты с покрытием не менее 90%. Для каждого эндпоинта проверь:
   - успешный сценарий (happy path)
   - граничные случаи (пустые поля, максимальные значения, нулевые суммы)
   - негативные сценарии (неверные данные, несуществующие ID)
   - проверку прав доступа (viewer не может создавать, manager видит только своих)
   - обработку ошибок (404, 403, 401, 400)"

ПРОМПТ 2 — граничные случаи предметной области:
  "Для CRM системы сгенерируй тесты граничных случаев:
   - сделка с нулевой суммой (amount=0)
   - сделка с очень большой суммой (amount=999999999)
   - клиент без менеджера (assigned_manager_id=None)
   - задача с просроченной датой (due_date в прошлом)
   - задача без привязки к клиенту и сделке
   - перевод сделки сразу в closed_won минуя промежуточные стадии
   - дублирование email при регистрации
   - логин с несуществующим email"

ПРОМПТ 3 — тесты аналитики и воронки:
  "Сгенерируй тесты для аналитических эндпоинтов CRM:
   - summary при пустой базе (нули везде, не падает)
   - pipeline-funnel содержит все 6 стадий всегда
   - deals-by-month с параметром months=1 и months=24
   - manager-performance: admin видит всех, manager только себя
   - win_rate при 0 побед и 0 поражений (деление на ноль)"

ПРОМПТ 4 — тесты безопасности и аутентификации:
  "Сгенерируй тесты безопасности для FastAPI приложения с JWT:
   - запрос без токена → 403
   - запрос с невалидным токеном → 401
   - запрос с истёкшим токеном → 401
   - viewer пытается создать/удалить → 403
   - manager пытается получить чужого клиента → 403
   - manager пытается удалить клиента → 403
   - нельзя удалить самого себя (admin)"

Запуск с покрытием:
  pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, get_db
from app.main import app

# ── Тестовая БД (SQLite в памяти) ─────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite:///./test_crm_full.db"
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
    import app.models  # noqa — регистрирует все модели
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


# ══════════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════════════════

def register(email="test@test.com", password="secret123", role="manager", full_name="Test User"):
    return client.post("/api/v1/auth/register", json={
        "email": email, "full_name": full_name,
        "password": password, "role": role
    })


def login(email="test@test.com", password="secret123"):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json().get("access_token")


def register_and_login(email="test@test.com", password="secret123", role="manager"):
    register(email, password, role)
    return login(email, password)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def make_client(token, company_name="Test Corp", **kwargs):
    data = {"company_name": company_name, **kwargs}
    return client.post("/api/v1/clients", json=data, headers=auth(token)).json()


def make_deal(token, client_id, title="Test Deal", stage="qualification", amount=10000, **kwargs):
    data = {"title": title, "client_id": client_id, "stage": stage, "amount": amount, **kwargs}
    return client.post("/api/v1/deals", json=data, headers=auth(token)).json()


def make_contact(token, client_id, first_name="Ivan", last_name="Petrov", **kwargs):
    data = {"client_id": client_id, "first_name": first_name, "last_name": last_name, **kwargs}
    return client.post("/api/v1/contacts", json=data, headers=auth(token)).json()


def make_task(token, title="Test Task", **kwargs):
    data = {"title": title, **kwargs}
    return client.post("/api/v1/tasks", json=data, headers=auth(token)).json()


# ══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: АУТЕНТИФИКАЦИЯ
# ══════════════════════════════════════════════════════════════════════════════

class TestAuth:

    def test_first_user_becomes_admin(self):
        """Первый зарегистрированный пользователь получает роль admin."""
        resp = register("first@test.com", "pass123")
        assert resp.status_code == 201
        assert resp.json()["role"] == "admin"

    def test_second_user_gets_manager_role(self):
        """Второй пользователь получает роль manager по умолчанию."""
        register("first@test.com", "pass123")
        resp = register("second@test.com", "pass123")
        assert resp.status_code == 201
        assert resp.json()["role"] == "manager"

    def test_register_duplicate_email_returns_400(self):
        """Повторная регистрация с тем же email → 400."""
        register()
        resp = register()
        assert resp.status_code == 400
        assert "already registered" in resp.json()["detail"]

    def test_login_success_returns_token(self):
        """Успешный логин возвращает access_token."""
        register()
        resp = client.post("/api/v1/auth/login", json={
            "email": "test@test.com", "password": "secret123"
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert resp.json()["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(self):
        """Неверный пароль → 401."""
        register()
        resp = client.post("/api/v1/auth/login", json={
            "email": "test@test.com", "password": "wrongpassword"
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email_returns_401(self):
        """Логин с несуществующим email → 401."""
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com", "password": "pass"
        })
        assert resp.status_code == 401

    def test_get_me_returns_current_user(self):
        """GET /auth/me возвращает данные текущего пользователя."""
        token = register_and_login()
        resp = client.get("/api/v1/auth/me", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@test.com"

    def test_request_without_token_returns_403(self):
        """Запрос без Bearer токена → 403."""
        resp = client.get("/api/v1/clients")
        assert resp.status_code == 403

    def test_request_with_invalid_token_returns_401(self):
        """Запрос с невалидным токеном → 401."""
        resp = client.get("/api/v1/clients", headers={"Authorization": "Bearer invalid.token.here"})
        assert resp.status_code == 401

    def test_health_endpoint(self):
        """GET /health всегда возвращает 200."""
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root_endpoint(self):
        """GET / возвращает информацию о приложении."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "app" in resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: КЛИЕНТЫ (основная сущность)
# ══════════════════════════════════════════════════════════════════════════════

class TestClients:

    def test_create_client_minimal(self):
        """Создание клиента с минимальными полями."""
        token = register_and_login()
        resp = client.post("/api/v1/clients", json={"company_name": "MinCorp"}, headers=auth(token))
        assert resp.status_code == 201
        data = resp.json()
        assert data["company_name"] == "MinCorp"
        assert data["status"] == "lead"

    def test_create_client_full(self):
        """Создание клиента со всеми полями."""
        token = register_and_login()
        resp = client.post("/api/v1/clients", json={
            "company_name": "Full Corp",
            "industry": "Technology",
            "website": "https://fullcorp.com",
            "address": "ул. Ленина 1",
            "city": "Москва",
            "country": "Россия",
            "status": "active",
            "notes": "Важный клиент"
        }, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["city"] == "Москва"
        assert resp.json()["status"] == "active"

    def test_list_clients_empty(self):
        """Список клиентов пуст при старте."""
        token = register_and_login()
        resp = client.get("/api/v1/clients", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_clients_pagination(self):
        """Пагинация: limit и skip работают корректно."""
        token = register_and_login()
        for i in range(5):
            make_client(token, f"Corp {i}")
        resp = client.get("/api/v1/clients?skip=2&limit=2", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_clients_filter_by_status(self):
        """Фильтрация клиентов по статусу."""
        token = register_and_login()
        make_client(token, "Lead Corp", status="lead")
        make_client(token, "Active Corp", status="active")
        resp = client.get("/api/v1/clients?status=lead", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["status"] == "lead"

    def test_list_clients_search_by_name(self):
        """Поиск клиентов по названию (регистронезависимый)."""
        token = register_and_login()
        make_client(token, "Unique Name Corp")
        make_client(token, "Other Company")
        resp = client.get("/api/v1/clients?search=unique", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_client_by_id(self):
        """Получение клиента по ID."""
        token = register_and_login()
        c = make_client(token, "GetMe Corp")
        resp = client.get(f"/api/v1/clients/{c['id']}", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "GetMe Corp"

    def test_get_nonexistent_client_returns_404(self):
        """Несуществующий клиент → 404."""
        token = register_and_login()
        resp = client.get("/api/v1/clients/99999", headers=auth(token))
        assert resp.status_code == 404

    def test_update_client(self):
        """Обновление полей клиента."""
        token = register_and_login()
        c = make_client(token, "Old Name")
        resp = client.put(f"/api/v1/clients/{c['id']}", json={
            "company_name": "New Name", "status": "active"
        }, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["company_name"] == "New Name"
        assert resp.json()["status"] == "active"

    def test_update_nonexistent_client_returns_404(self):
        """Обновление несуществующего клиента → 404."""
        token = register_and_login()
        resp = client.put("/api/v1/clients/99999", json={"company_name": "X"}, headers=auth(token))
        assert resp.status_code == 404

    def test_delete_client_by_admin(self):
        """Админ может удалить клиента."""
        token = register_and_login()  # первый → admin
        c = make_client(token, "ToDelete")
        resp = client.delete(f"/api/v1/clients/{c['id']}", headers=auth(token))
        assert resp.status_code == 204
        assert client.get(f"/api/v1/clients/{c['id']}", headers=auth(token)).status_code == 404

    def test_delete_client_by_manager_returns_403(self):
        """Менеджер не может удалять клиентов → 403."""
        admin_token = register_and_login()
        manager_token = register_and_login("mgr@test.com", "pass123", "manager")
        c = make_client(admin_token, "Protected")
        resp = client.delete(f"/api/v1/clients/{c['id']}", headers=auth(manager_token))
        assert resp.status_code == 403

    def test_delete_nonexistent_client_returns_404(self):
        """Удаление несуществующего клиента → 404."""
        token = register_and_login()
        resp = client.delete("/api/v1/clients/99999", headers=auth(token))
        assert resp.status_code == 404

    def test_viewer_cannot_create_client(self):
        """Viewer не может создавать клиентов → 403."""
        register_and_login()  # admin
        viewer_token = register_and_login("viewer@test.com", "pass", "viewer")
        resp = client.post("/api/v1/clients", json={"company_name": "X"}, headers=auth(viewer_token))
        assert resp.status_code == 403

    def test_manager_sees_only_own_clients(self):
        """Менеджер видит только своих клиентов."""
        admin_token = register_and_login()
        mgr_token = register_and_login("mgr@test.com", "pass", "manager")
        make_client(admin_token, "Admin Client")
        make_client(mgr_token, "Manager Client")
        resp = client.get("/api/v1/clients", headers=auth(mgr_token))
        assert len(resp.json()) == 1
        assert resp.json()[0]["company_name"] == "Manager Client"

    def test_get_client_contacts(self):
        """GET /clients/{id}/contacts возвращает контакты клиента."""
        token = register_and_login()
        c = make_client(token, "Corp")
        make_contact(token, c["id"], "Ivan", "Petrov")
        resp = client.get(f"/api/v1/clients/{c['id']}/contacts", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_client_deals(self):
        """GET /clients/{id}/deals возвращает сделки клиента."""
        token = register_and_login()
        c = make_client(token, "Corp")
        make_deal(token, c["id"], "Deal 1")
        resp = client.get(f"/api/v1/clients/{c['id']}/deals", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: КОНТАКТЫ
# ══════════════════════════════════════════════════════════════════════════════

class TestContacts:

    def test_create_contact(self):
        """Создание контакта для клиента."""
        token = register_and_login()
        c = make_client(token)
        resp = client.post("/api/v1/contacts", json={
            "client_id": c["id"], "first_name": "Иван", "last_name": "Петров",
            "email": "ivan@corp.ru", "phone": "+7 495 000-00-00",
            "position": "CEO", "is_primary": True
        }, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["first_name"] == "Иван"
        assert resp.json()["is_primary"] is True

    def test_create_contact_minimal(self):
        """Создание контакта с минимальными полями."""
        token = register_and_login()
        c = make_client(token)
        resp = client.post("/api/v1/contacts", json={
            "client_id": c["id"], "first_name": "A", "last_name": "B"
        }, headers=auth(token))
        assert resp.status_code == 201

    def test_list_contacts(self):
        """Список контактов."""
        token = register_and_login()
        c = make_client(token)
        make_contact(token, c["id"])
        make_contact(token, c["id"], "Petr", "Sidorov")
        resp = client.get("/api/v1/contacts", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_contacts_filter_by_client(self):
        """Фильтрация контактов по клиенту."""
        token = register_and_login()
        c1 = make_client(token, "Corp 1")
        c2 = make_client(token, "Corp 2")
        make_contact(token, c1["id"])
        make_contact(token, c2["id"], "Other", "Person")
        resp = client.get(f"/api/v1/contacts?client_id={c1['id']}", headers=auth(token))
        assert len(resp.json()) == 1

    def test_list_contacts_search(self):
        """Поиск контактов по имени/email."""
        token = register_and_login()
        c = make_client(token)
        make_contact(token, c["id"], "UniqueFirst", "LastName")
        make_contact(token, c["id"], "OtherFirst", "OtherLast")
        resp = client.get("/api/v1/contacts?search=UniqueFirst", headers=auth(token))
        assert len(resp.json()) == 1

    def test_get_contact_by_id(self):
        """Получение контакта по ID."""
        token = register_and_login()
        c = make_client(token)
        contact = make_contact(token, c["id"])
        resp = client.get(f"/api/v1/contacts/{contact['id']}", headers=auth(token))
        assert resp.status_code == 200

    def test_get_nonexistent_contact_returns_404(self):
        """Несуществующий контакт → 404."""
        token = register_and_login()
        resp = client.get("/api/v1/contacts/99999", headers=auth(token))
        assert resp.status_code == 404

    def test_update_contact(self):
        """Обновление контакта."""
        token = register_and_login()
        c = make_client(token)
        contact = make_contact(token, c["id"])
        resp = client.put(f"/api/v1/contacts/{contact['id']}", json={
            "position": "CTO", "is_primary": True
        }, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["position"] == "CTO"

    def test_delete_contact(self):
        """Удаление контакта."""
        token = register_and_login()
        c = make_client(token)
        contact = make_contact(token, c["id"])
        resp = client.delete(f"/api/v1/contacts/{contact['id']}", headers=auth(token))
        assert resp.status_code == 204

    def test_viewer_cannot_create_contact(self):
        """Viewer не может создавать контакты → 403."""
        register_and_login()
        viewer_token = register_and_login("v@test.com", "pass", "viewer")
        resp = client.post("/api/v1/contacts", json={
            "client_id": 1, "first_name": "A", "last_name": "B"
        }, headers=auth(viewer_token))
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: СДЕЛКИ
# ══════════════════════════════════════════════════════════════════════════════

class TestDeals:

    def test_create_deal_auto_probability_qualification(self):
        """Создание сделки на стадии qualification → probability=10."""
        token = register_and_login()
        c = make_client(token)
        resp = make_deal(token, c["id"], stage="qualification")
        assert resp["probability"] == 10

    def test_create_deal_auto_probability_negotiation(self):
        """Создание сделки на стадии negotiation → probability=75."""
        token = register_and_login()
        c = make_client(token)
        resp = make_deal(token, c["id"], stage="negotiation")
        assert resp["probability"] == 75

    def test_create_deal_auto_probability_closed_won(self):
        """Создание сделки closed_won → probability=100."""
        token = register_and_login()
        c = make_client(token)
        resp = make_deal(token, c["id"], stage="closed_won")
        assert resp["probability"] == 100

    def test_create_deal_auto_probability_closed_lost(self):
        """Создание сделки closed_lost → probability=0."""
        token = register_and_login()
        c = make_client(token)
        resp = make_deal(token, c["id"], stage="closed_lost")
        assert resp["probability"] == 0

    def test_create_deal_zero_amount(self):
        """Граничный случай: сделка с нулевой суммой."""
        token = register_and_login()
        c = make_client(token)
        resp = make_deal(token, c["id"], amount=0)
        assert resp["amount"] == 0.0

    def test_create_deal_very_large_amount(self):
        """Граничный случай: сделка с очень большой суммой."""
        token = register_and_login()
        c = make_client(token)
        resp = make_deal(token, c["id"], amount=999_999_999)
        assert resp["amount"] == 999_999_999.0

    def test_update_deal_stage_updates_probability(self):
        """Смена стадии сделки автоматически обновляет вероятность."""
        token = register_and_login()
        c = make_client(token)
        d = make_deal(token, c["id"], stage="qualification")
        resp = client.put(f"/api/v1/deals/{d['id']}", json={"stage": "proposal"}, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["probability"] == 50

    def test_update_deal_to_closed_won_sets_close_date(self):
        """Закрытие сделки как выигранной устанавливает actual_close_date."""
        token = register_and_login()
        c = make_client(token)
        d = make_deal(token, c["id"])
        resp = client.put(f"/api/v1/deals/{d['id']}", json={"stage": "closed_won"}, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["actual_close_date"] == date.today().isoformat()

    def test_update_deal_to_closed_lost_sets_close_date(self):
        """Закрытие сделки как проигранной устанавливает actual_close_date."""
        token = register_and_login()
        c = make_client(token)
        d = make_deal(token, c["id"])
        resp = client.put(f"/api/v1/deals/{d['id']}", json={"stage": "closed_lost"}, headers=auth(token))
        assert resp.json()["actual_close_date"] == date.today().isoformat()

    def test_list_deals_filter_by_stage(self):
        """Фильтрация сделок по стадии."""
        token = register_and_login()
        c = make_client(token)
        make_deal(token, c["id"], "D1", stage="proposal")
        make_deal(token, c["id"], "D2", stage="negotiation")
        resp = client.get("/api/v1/deals?stage=proposal", headers=auth(token))
        assert len(resp.json()) == 1

    def test_list_deals_filter_by_client(self):
        """Фильтрация сделок по клиенту."""
        token = register_and_login()
        c1 = make_client(token, "Corp 1")
        c2 = make_client(token, "Corp 2")
        make_deal(token, c1["id"], "D1")
        make_deal(token, c2["id"], "D2")
        resp = client.get(f"/api/v1/deals?client_id={c1['id']}", headers=auth(token))
        assert len(resp.json()) == 1

    def test_get_deal_by_id(self):
        """Получение сделки по ID."""
        token = register_and_login()
        c = make_client(token)
        d = make_deal(token, c["id"])
        resp = client.get(f"/api/v1/deals/{d['id']}", headers=auth(token))
        assert resp.status_code == 200

    def test_get_nonexistent_deal_returns_404(self):
        """Несуществующая сделка → 404."""
        token = register_and_login()
        resp = client.get("/api/v1/deals/99999", headers=auth(token))
        assert resp.status_code == 404

    def test_delete_deal_by_admin(self):
        """Админ может удалить сделку."""
        token = register_and_login()
        c = make_client(token)
        d = make_deal(token, c["id"])
        resp = client.delete(f"/api/v1/deals/{d['id']}", headers=auth(token))
        assert resp.status_code == 204

    def test_delete_deal_by_manager_returns_403(self):
        """Менеджер не может удалять сделки → 403."""
        admin_token = register_and_login()
        mgr_token = register_and_login("mgr@test.com", "pass", "manager")
        c = make_client(admin_token)
        d = make_deal(admin_token, c["id"])
        resp = client.delete(f"/api/v1/deals/{d['id']}", headers=auth(mgr_token))
        assert resp.status_code == 403

    def test_pipeline_contains_all_stages(self):
        """Воронка всегда содержит все 6 стадий."""
        token = register_and_login()
        resp = client.get("/api/v1/deals/pipeline", headers=auth(token))
        assert resp.status_code == 200
        stages = list(resp.json().keys())
        expected = ["qualification", "needs_analysis", "proposal", "negotiation", "closed_won", "closed_lost"]
        for s in expected:
            assert s in stages

    def test_pipeline_counts_deals_correctly(self):
        """Воронка правильно считает количество сделок по стадиям."""
        token = register_and_login()
        c = make_client(token)
        make_deal(token, c["id"], "D1", stage="proposal")
        make_deal(token, c["id"], "D2", stage="proposal")
        make_deal(token, c["id"], "D3", stage="negotiation")
        resp = client.get("/api/v1/deals/pipeline", headers=auth(token))
        assert resp.json()["proposal"]["count"] == 2
        assert resp.json()["negotiation"]["count"] == 1

    def test_viewer_cannot_create_deal(self):
        """Viewer не может создавать сделки → 403."""
        register_and_login()
        viewer_token = register_and_login("v@test.com", "pass", "viewer")
        resp = client.post("/api/v1/deals", json={
            "title": "X", "client_id": 1
        }, headers=auth(viewer_token))
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: ЗАДАЧИ
# ══════════════════════════════════════════════════════════════════════════════

class TestTasks:

    def test_create_task_minimal(self):
        """Создание задачи с минимальными полями."""
        token = register_and_login()
        resp = client.post("/api/v1/tasks", json={"title": "Позвонить клиенту"}, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["status"] == "open"
        assert resp.json()["priority"] == "medium"

    def test_create_task_linked_to_client_and_deal(self):
        """Задача может быть привязана к клиенту и сделке одновременно."""
        token = register_and_login()
        c = make_client(token)
        d = make_deal(token, c["id"])
        resp = client.post("/api/v1/tasks", json={
            "title": "Подготовить КП",
            "client_id": c["id"],
            "deal_id": d["id"],
            "priority": "high",
            "task_type": "proposal"
        }, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["client_id"] == c["id"]
        assert resp.json()["deal_id"] == d["id"]

    def test_create_task_without_links(self):
        """Задача без привязки к клиенту и сделке."""
        token = register_and_login()
        resp = client.post("/api/v1/tasks", json={"title": "Самостоятельная задача"}, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["client_id"] is None
        assert resp.json()["deal_id"] is None

    def test_create_task_with_past_due_date(self):
        """Граничный случай: задача с просроченной датой создаётся без ошибки."""
        token = register_and_login()
        past_date = (date.today() - timedelta(days=30)).isoformat()
        resp = client.post("/api/v1/tasks", json={
            "title": "Просроченная задача", "due_date": past_date
        }, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["due_date"] == past_date

    def test_update_task_status_to_done_sets_completed_at(self):
        """При переводе задачи в done устанавливается completed_at."""
        token = register_and_login()
        t = make_task(token)
        resp = client.put(f"/api/v1/tasks/{t['id']}", json={"status": "done"}, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["completed_at"] is not None

    def test_list_tasks_filter_by_status(self):
        """Фильтрация задач по статусу."""
        token = register_and_login()
        make_task(token, "Open Task")
        t2 = make_task(token, "Done Task")
        client.put(f"/api/v1/tasks/{t2['id']}", json={"status": "done"}, headers=auth(token))
        resp = client.get("/api/v1/tasks?status=open", headers=auth(token))
        assert all(t["status"] == "open" for t in resp.json())

    def test_list_tasks_filter_overdue(self):
        """Фильтрация просроченных задач."""
        token = register_and_login()
        past = (date.today() - timedelta(days=1)).isoformat()
        future = (date.today() + timedelta(days=1)).isoformat()
        make_task(token, "Overdue", due_date=past)
        make_task(token, "Future", due_date=future)
        resp = client.get("/api/v1/tasks?overdue_only=true", headers=auth(token))
        assert len(resp.json()) == 1
        assert resp.json()[0]["title"] == "Overdue"

    def test_list_tasks_filter_by_priority(self):
        """Фильтрация задач по приоритету."""
        token = register_and_login()
        make_task(token, "Urgent Task", priority="urgent")
        make_task(token, "Low Task", priority="low")
        resp = client.get("/api/v1/tasks?priority=urgent", headers=auth(token))
        assert len(resp.json()) == 1

    def test_get_task_by_id(self):
        """Получение задачи по ID."""
        token = register_and_login()
        t = make_task(token)
        resp = client.get(f"/api/v1/tasks/{t['id']}", headers=auth(token))
        assert resp.status_code == 200

    def test_get_nonexistent_task_returns_404(self):
        """Несуществующая задача → 404."""
        token = register_and_login()
        resp = client.get("/api/v1/tasks/99999", headers=auth(token))
        assert resp.status_code == 404

    def test_delete_task(self):
        """Удаление задачи."""
        token = register_and_login()
        t = make_task(token)
        resp = client.delete(f"/api/v1/tasks/{t['id']}", headers=auth(token))
        assert resp.status_code == 204

    def test_viewer_cannot_create_task(self):
        """Viewer не может создавать задачи → 403."""
        register_and_login()
        viewer_token = register_and_login("v@test.com", "pass", "viewer")
        resp = client.post("/api/v1/tasks", json={"title": "X"}, headers=auth(viewer_token))
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: АНАЛИТИКА
# ══════════════════════════════════════════════════════════════════════════════

class TestAnalytics:

    def test_summary_empty_database(self):
        """Summary при пустой БД возвращает нули, не падает."""
        token = register_and_login()
        resp = client.get("/api/v1/analytics/summary", headers=auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["clients"]["total"] == 0
        assert data["deals"]["total"] == 0
        assert data["deals"]["win_rate_pct"] == 0.0
        assert data["tasks"]["open"] == 0

    def test_summary_with_data(self):
        """Summary корректно считает KPI при наличии данных."""
        token = register_and_login()
        c = make_client(token)
        make_deal(token, c["id"], "Won", stage="closed_won", amount=100000)
        make_deal(token, c["id"], "Lost", stage="closed_lost", amount=50000)
        make_deal(token, c["id"], "Open", stage="proposal", amount=75000)
        resp = client.get("/api/v1/analytics/summary", headers=auth(token))
        data = resp.json()
        assert data["deals"]["won"] == 1
        assert data["deals"]["lost"] == 1
        assert data["deals"]["open"] == 1
        assert data["deals"]["win_rate_pct"] == 50.0
        assert data["deals"]["total_won_value"] == 100000.0

    def test_summary_win_rate_no_closed_deals(self):
        """Win rate = 0 когда нет закрытых сделок (нет деления на ноль)."""
        token = register_and_login()
        c = make_client(token)
        make_deal(token, c["id"], stage="proposal")
        resp = client.get("/api/v1/analytics/summary", headers=auth(token))
        assert resp.json()["deals"]["win_rate_pct"] == 0.0

    def test_pipeline_funnel_all_stages_present(self):
        """Pipeline funnel всегда содержит все 6 стадий."""
        token = register_and_login()
        resp = client.get("/api/v1/analytics/pipeline-funnel", headers=auth(token))
        assert resp.status_code == 200
        stages = [item["stage"] for item in resp.json()]
        for s in ["qualification", "needs_analysis", "proposal", "negotiation", "closed_won", "closed_lost"]:
            assert s in stages

    def test_pipeline_funnel_correct_amounts(self):
        """Pipeline funnel правильно суммирует суммы сделок."""
        token = register_and_login()
        c = make_client(token)
        make_deal(token, c["id"], "D1", stage="proposal", amount=30000)
        make_deal(token, c["id"], "D2", stage="proposal", amount=20000)
        resp = client.get("/api/v1/analytics/pipeline-funnel", headers=auth(token))
        proposal = next(item for item in resp.json() if item["stage"] == "proposal")
        assert proposal["count"] == 2
        assert proposal["total_amount"] == 50000.0

    def test_deals_by_month_default(self):
        """Deals by month работает с параметрами по умолчанию."""
        token = register_and_login()
        resp = client.get("/api/v1/analytics/deals-by-month", headers=auth(token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_deals_by_month_min_months(self):
        """Deals by month с минимальным параметром months=1."""
        token = register_and_login()
        resp = client.get("/api/v1/analytics/deals-by-month?months=1", headers=auth(token))
        assert resp.status_code == 200

    def test_deals_by_month_max_months(self):
        """Deals by month с максимальным параметром months=24."""
        token = register_and_login()
        resp = client.get("/api/v1/analytics/deals-by-month?months=24", headers=auth(token))
        assert resp.status_code == 200

    def test_clients_by_status(self):
        """Clients by status возвращает правильные группы."""
        token = register_and_login()
        make_client(token, "L1", status="lead")
        make_client(token, "L2", status="lead")
        make_client(token, "A1", status="active")
        resp = client.get("/api/v1/analytics/clients-by-status", headers=auth(token))
        assert resp.status_code == 200
        result = {item["status"]: item["count"] for item in resp.json()}
        assert result["lead"] == 2
        assert result["active"] == 1

    def test_manager_performance_admin_sees_all(self):
        """Администратор видит статистику всех менеджеров."""
        admin_token = register_and_login()
        register_and_login("mgr@test.com", "pass", "manager")
        resp = client.get("/api/v1/analytics/manager-performance", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_manager_performance_manager_sees_only_self(self):
        """Менеджер видит только свою статистику."""
        register_and_login()
        mgr_token = register_and_login("mgr@test.com", "pass", "manager")
        resp = client.get("/api/v1/analytics/manager-performance", headers=auth(mgr_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ══════════════════════════════════════════════════════════════════════════════
# ТЕСТЫ: ADMIN PANEL
# ══════════════════════════════════════════════════════════════════════════════

class TestAdmin:

    def test_admin_can_list_users(self):
        """Администратор может получить список пользователей."""
        token = register_and_login()
        resp = client.get("/api/v1/admin/users", headers=auth(token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_manager_cannot_list_users(self):
        """Менеджер не имеет доступа к панели администратора → 403."""
        register_and_login()
        mgr_token = register_and_login("mgr@test.com", "pass", "manager")
        resp = client.get("/api/v1/admin/users", headers=auth(mgr_token))
        assert resp.status_code == 403

    def test_admin_can_create_user(self):
        """Администратор может создать пользователя через admin panel."""
        token = register_and_login()
        resp = client.post("/api/v1/admin/users", json={
            "email": "new@test.com", "full_name": "New User",
            "password": "newpass123", "role": "viewer"
        }, headers=auth(token))
        assert resp.status_code == 201
        assert resp.json()["role"] == "viewer"

    def test_admin_cannot_create_duplicate_email(self):
        """Дублирование email через admin panel → 400."""
        token = register_and_login()
        client.post("/api/v1/admin/users", json={
            "email": "dup@test.com", "full_name": "User",
            "password": "pass", "role": "manager"
        }, headers=auth(token))
        resp = client.post("/api/v1/admin/users", json={
            "email": "dup@test.com", "full_name": "User2",
            "password": "pass", "role": "manager"
        }, headers=auth(token))
        assert resp.status_code == 400

    def test_admin_can_update_user(self):
        """Администратор может изменить роль пользователя."""
        token = register_and_login()
        new_user = client.post("/api/v1/admin/users", json={
            "email": "upd@test.com", "full_name": "Upd",
            "password": "pass", "role": "viewer"
        }, headers=auth(token)).json()
        resp = client.put(f"/api/v1/admin/users/{new_user['id']}", json={
            "role": "manager"
        }, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["role"] == "manager"

    def test_admin_can_deactivate_user(self):
        """Администратор может деактивировать пользователя."""
        token = register_and_login()
        new_user = client.post("/api/v1/admin/users", json={
            "email": "deact@test.com", "full_name": "Deact",
            "password": "pass", "role": "manager"
        }, headers=auth(token)).json()
        resp = client.put(f"/api/v1/admin/users/{new_user['id']}", json={
            "is_active": False
        }, headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_admin_cannot_delete_self(self):
        """Администратор не может удалить самого себя → 400."""
        token = register_and_login()
        me = client.get("/api/v1/auth/me", headers=auth(token)).json()
        resp = client.delete(f"/api/v1/admin/users/{me['id']}", headers=auth(token))
        assert resp.status_code == 400

    def test_admin_can_delete_other_user(self):
        """Администратор может удалить другого пользователя."""
        token = register_and_login()
        new_user = client.post("/api/v1/admin/users", json={
            "email": "del@test.com", "full_name": "Del",
            "password": "pass", "role": "manager"
        }, headers=auth(token)).json()
        resp = client.delete(f"/api/v1/admin/users/{new_user['id']}", headers=auth(token))
        assert resp.status_code == 204

    def test_admin_update_nonexistent_user_returns_404(self):
        """Обновление несуществующего пользователя → 404."""
        token = register_and_login()
        resp = client.put("/api/v1/admin/users/99999", json={"role": "viewer"}, headers=auth(token))
        assert resp.status_code == 404

    def test_admin_delete_nonexistent_user_returns_404(self):
        """Удаление несуществующего пользователя → 404."""
        token = register_and_login()
        resp = client.delete("/api/v1/admin/users/99999", headers=auth(token))
        assert resp.status_code == 404
