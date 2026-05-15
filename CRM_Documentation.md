# CRM для отдела продаж — Полная документация

## Оглавление
1. [Структура проекта](#структура)
2. [Описание каждого файла](#файлы)
3. [Установка и запуск](#запуск)
4. [Работа с API](#api)
5. [Роли и права доступа](#роли)
6. [Аналитика и отчёты](#аналитика)
7. [Тесты](#тесты)
8. [FAQ и типичные ошибки](#faq)

---

## 1. Структура проекта {#структура}

```
crm/
├── app/
│   ├── __init__.py
│   ├── main.py                  ← точка входа FastAPI
│   ├── core/
│   │   ├── config.py            ← настройки приложения
│   │   ├── database.py          ← подключение к БД (SQLAlchemy)
│   │   └── security.py          ← JWT, хэширование паролей, зависимости
│   ├── models/
│   │   ├── __init__.py          ← импорт всех моделей
│   │   ├── user.py              ← пользователи системы
│   │   ├── client.py            ← клиенты (основная сущность)
│   │   ├── contact.py           ← контактные лица клиента
│   │   ├── deal.py              ← сделки + воронка продаж
│   │   └── task.py              ← задачи
│   ├── schemas/
│   │   ├── user.py              ← Pydantic-схемы для User
│   │   ├── client.py            ← Pydantic-схемы для Client
│   │   ├── contact.py           ← Pydantic-схемы для Contact
│   │   ├── deal.py              ← Pydantic-схемы для Deal
│   │   └── task.py              ← Pydantic-схемы для Task
│   └── api/v1/
│       ├── __init__.py          ← сборка всех роутеров
│       ├── auth.py              ← /auth/register, /auth/login, /auth/me
│       ├── clients.py           ← CRUD клиентов
│       ├── contacts.py          ← CRUD контактных лиц
│       ├── deals.py             ← CRUD сделок + /pipeline
│       ├── tasks.py             ← CRUD задач
│       ├── analytics.py         ← /analytics/summary + отчёты
│       └── admin.py             ← управление пользователями (admin only)
├── tests/
│   └── test_api.py              ← интеграционные тесты
├── seed.py                      ← демо-данные для старта
├── requirements.txt             ← зависимости Python
├── pytest.ini                   ← настройки pytest
└── .env.example                 ← шаблон переменных окружения
```

---

## 2. Описание каждого файла {#файлы}

### `requirements.txt`
Список всех Python-зависимостей:
- **fastapi** — веб-фреймворк, создаёт REST API
- **uvicorn** — ASGI-сервер для запуска FastAPI
- **sqlalchemy** — ORM для работы с базой данных
- **alembic** — миграции базы данных
- **python-jose** — создание и проверка JWT-токенов
- **passlib[bcrypt]** — хэширование паролей через bcrypt
- **pydantic / pydantic-settings** — валидация данных и настройки
- **aiosqlite** — асинхронный драйвер SQLite
- **pytest / httpx** — тесты

---

### `app/main.py` — точка входа

Создаёт объект `FastAPI`, подключает:
- CORS Middleware (разрешает запросы с любых доменов)
- Все роутеры через `api_router`
- При запуске автоматически создаёт таблицы в БД (`Base.metadata.create_all`)

```python
# Запускается так:
uvicorn app.main:app --reload
```

---

### `app/core/config.py` — настройки

Читает переменные из файла `.env`. Ключевые параметры:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./crm.db` | Строка подключения к БД |
| `SECRET_KEY` | `super-secret-key-...` | Ключ для подписи JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` (24ч) | Время жизни токена |

**Важно:** В продакшене обязательно смените `SECRET_KEY` на случайную строку ≥32 символов!

---

### `app/core/database.py` — подключение к БД

Создаёт три ключевых объекта:
- `engine` — соединение с базой данных
- `SessionLocal` — фабрика сессий SQLAlchemy
- `get_db()` — зависимость FastAPI, открывает сессию на время запроса и закрывает после

---

### `app/core/security.py` — безопасность

Содержит все функции безопасности:

| Функция | Назначение |
|---|---|
| `get_password_hash(password)` | Хэширует пароль через bcrypt |
| `verify_password(plain, hashed)` | Сравнивает пароль с хэшем |
| `create_access_token(data)` | Создаёт JWT-токен |
| `decode_token(token)` | Декодирует JWT, бросает 401 если невалидный |
| `get_current_user` | Зависимость FastAPI — извлекает текущего юзера из Bearer-токена |
| `get_current_admin` | Зависимость — только для роли `admin`, иначе 403 |

---

### `app/models/user.py` — модель пользователя

Таблица `users`. Поля:

| Поле | Тип | Описание |
|---|---|---|
| `id` | int PK | Идентификатор |
| `email` | str unique | Email (логин) |
| `full_name` | str | Полное имя |
| `hashed_password` | str | Хэш пароля |
| `role` | str | `admin` / `manager` / `viewer` |
| `is_active` | bool | Активен ли аккаунт |

---

### `app/models/client.py` — основная сущность

Таблица `clients`. Клиент = компания/организация.

Статусы клиента (`status`):
- `lead` → новый лид (ещё не квалифицирован)
- `prospect` → есть потенциал, ведётся работа
- `active` → активный клиент
- `inactive` → неактивный
- `churned` → ушедший

Связи:
- **один-ко-многим** с `Contact` — у клиента много контактных лиц
- **один-ко-многим** с `Deal` — у клиента много сделок
- **один-ко-многим** с `Task` — у клиента много задач
- **многие-к-одному** с `User` — за клиентом закреплён менеджер

---

### `app/models/contact.py` — контактные лица

Таблица `contacts`. Контакт — конкретный человек в компании-клиенте.

Поле `is_primary = True` означает основной контакт клиента.

---

### `app/models/deal.py` — сделки и воронка

Таблица `deals`. Сделка проходит через стадии воронки:

```
qualification → needs_analysis → proposal → negotiation → closed_won
                                                         ↘ closed_lost
```

Автоматическая вероятность по стадии:

| Стадия | Вероятность |
|---|---|
| qualification | 10% |
| needs_analysis | 25% |
| proposal | 50% |
| negotiation | 75% |
| closed_won | 100% |
| closed_lost | 0% |

---

### `app/models/task.py` — задачи

Таблица `tasks`. Задача может быть привязана к клиенту И/ИЛИ к сделке.

Типы задач: `follow_up`, `call`, `meeting`, `email`, `demo`, `proposal`, `other`

Приоритеты: `low`, `medium`, `high`, `urgent`

Статусы: `open`, `in_progress`, `done`, `cancelled`

При переводе в статус `done` автоматически ставится `completed_at = now()`.

---

### `app/schemas/` — Pydantic-схемы

Каждая сущность имеет 3-4 схемы:

| Схема | Назначение |
|---|---|
| `*Base` | Общие поля |
| `*Create` | Данные для создания (POST) |
| `*Update` | Данные для обновления (PUT) — все поля опциональны |
| `*Out` | Ответ API (включает `id`, `created_at`) |

---

### `app/api/v1/auth.py` — аутентификация

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/v1/auth/register` | Регистрация. Первый юзер автоматически становится admin |
| POST | `/api/v1/auth/login` | Логин, возвращает JWT-токен |
| GET | `/api/v1/auth/me` | Профиль текущего пользователя |

---

### `app/api/v1/clients.py` — CRUD клиентов

| Метод | URL | Права | Описание |
|---|---|---|---|
| GET | `/api/v1/clients` | все | Список (manager видит только своих) |
| POST | `/api/v1/clients` | manager, admin | Создать клиента |
| GET | `/api/v1/clients/{id}` | все | Детали клиента |
| PUT | `/api/v1/clients/{id}` | manager (свои), admin | Обновить |
| DELETE | `/api/v1/clients/{id}` | admin only | Удалить |
| GET | `/api/v1/clients/{id}/contacts` | все | Контакты клиента |
| GET | `/api/v1/clients/{id}/deals` | все | Сделки клиента |

Поддерживаемые query-параметры для списка:
- `search=текст` — поиск по названию
- `status=lead` — фильтр по статусу
- `manager_id=3` — фильтр по менеджеру
- `skip=0&limit=50` — пагинация

---

### `app/api/v1/deals.py` — сделки

Дополнительно к стандартному CRUD:

**GET `/api/v1/deals/pipeline`** — воронка продаж:
```json
{
  "qualification": { "count": 3, "total_amount": 75000, "deals": [...] },
  "proposal": { "count": 1, "total_amount": 150000, "deals": [...] },
  ...
}
```

При изменении стадии (`stage`) вероятность (`probability`) обновляется автоматически.
При переводе в `closed_won`/`closed_lost` автоматически ставится `actual_close_date`.

---

### `app/api/v1/analytics.py` — аналитика

| URL | Описание |
|---|---|
| `GET /api/v1/analytics/summary` | KPI-дашборд: клиенты, сделки, задачи, win rate |
| `GET /api/v1/analytics/pipeline-funnel` | Количество и сумма по каждой стадии воронки |
| `GET /api/v1/analytics/deals-by-month?months=6` | Динамика закрытых сделок по месяцам |
| `GET /api/v1/analytics/clients-by-status` | Распределение клиентов по статусам |
| `GET /api/v1/analytics/manager-performance` | KPI по каждому менеджеру (admin видит всех) |

---

### `app/api/v1/admin.py` — администрирование

Все роуты требуют роль `admin`.

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/v1/admin/users` | Список всех пользователей |
| POST | `/api/v1/admin/users` | Создать пользователя |
| PUT | `/api/v1/admin/users/{id}` | Изменить пользователя (в т.ч. смена пароля) |
| DELETE | `/api/v1/admin/users/{id}` | Удалить (нельзя удалить себя) |

---

### `seed.py` — демо-данные

Создаёт 4 пользователей, 5 клиентов, 5 контактов, 6 сделок, 5 задач.

---

### `tests/test_api.py` — тесты

Покрывают: регистрацию, логин, CRUD клиентов, создание сделок, аналитику, проверку прав доступа.

---

## 3. Установка и запуск {#запуск}

### Шаг 1 — клонируйте / скопируйте проект

```bash
# Предполагается что папка crm/ уже есть
cd crm
```

### Шаг 2 — создайте виртуальное окружение

```bash
python -m venv venv

# Linux / macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### Шаг 3 — установите зависимости

```bash
pip install -r requirements.txt
```

### Шаг 4 — настройте переменные окружения

```bash
cp .env.example .env
# Откройте .env и при необходимости измените SECRET_KEY
```

### Шаг 5 — запустите приложение

```bash
uvicorn app.main:app --reload
```

Таблицы создадутся автоматически при первом запуске.

### Шаг 6 (опционально) — загрузите демо-данные

```bash
python seed.py
```

Вывод:
```
✅ Demo data seeded successfully!

Login credentials:
  admin@crm.com   / admin123   (role: admin)
  alice@crm.com   / manager123 (role: manager)
  bob@crm.com     / manager123 (role: manager)
  viewer@crm.com  / viewer123  (role: viewer)
```

---

## 4. Работа с API {#api}

После запуска откройте интерактивную документацию:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Получить токен (cURL)

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@crm.com", "password": "admin123"}'
```

Ответ:
```json
{"access_token": "eyJhbGciOiJIUzI1...", "token_type": "bearer"}
```

### Использовать токен в запросах

```bash
TOKEN="eyJhbGciOiJIUzI1..."

# Список клиентов
curl http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer $TOKEN"

# Создать клиента
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "New Corp", "industry": "IT", "status": "lead"}'

# Воронка продаж
curl http://localhost:8000/api/v1/deals/pipeline \
  -H "Authorization: Bearer $TOKEN"

# KPI-дашборд
curl http://localhost:8000/api/v1/analytics/summary \
  -H "Authorization: Bearer $TOKEN"
```

### Пример: создать сделку и продвинуть по воронке

```bash
# 1. Создать сделку
curl -X POST http://localhost:8000/api/v1/deals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title": "Большой контракт", "client_id": 1, "stage": "qualification", "amount": 100000}'

# 2. Продвинуть на следующую стадию (вероятность обновится автоматически)
curl -X PUT http://localhost:8000/api/v1/deals/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage": "proposal"}'
# → probability станет 50 автоматически

# 3. Закрыть сделку как выигранную
curl -X PUT http://localhost:8000/api/v1/deals/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage": "closed_won"}'
# → actual_close_date = сегодня, probability = 100
```

---

## 5. Роли и права доступа {#роли}

| Действие | viewer | manager | admin |
|---|:---:|:---:|:---:|
| Просмотр клиентов | ✅ (все) | ✅ (только своих) | ✅ (все) |
| Создание/редактирование клиентов | ❌ | ✅ (только своих) | ✅ |
| Удаление клиентов | ❌ | ❌ | ✅ |
| Создание сделок/задач | ❌ | ✅ | ✅ |
| Удаление сделок | ❌ | ❌ | ✅ |
| Аналитика | ✅ (своя) | ✅ (своя) | ✅ (все) |
| Manager performance (все) | ❌ | ❌ | ✅ |
| Управление пользователями | ❌ | ❌ | ✅ |

**Первый зарегистрированный пользователь** автоматически получает роль `admin`.

---

## 6. Аналитика и отчёты {#аналитика}

### `/analytics/summary` — KPI дашборд
```json
{
  "clients": { "total": 5 },
  "deals": {
    "total": 6, "open": 4, "won": 1, "lost": 1,
    "win_rate_pct": 50.0,
    "total_pipeline_value": 352000.0,
    "total_won_value": 320000.0,
    "weighted_pipeline": 128750.0
  },
  "tasks": { "open": 3, "overdue": 1 }
}
```

### `/analytics/pipeline-funnel` — воронка
```json
[
  {"stage": "qualification", "count": 1, "total_amount": 22000.0},
  {"stage": "needs_analysis", "count": 1, "total_amount": 95000.0},
  {"stage": "proposal",       "count": 1, "total_amount": 150000.0},
  ...
]
```

### `/analytics/deals-by-month?months=6` — динамика
```json
[
  {"month": "2025-04", "won": 1, "lost": 1, "won_value": 320000, "lost_value": 15000}
]
```

---

## 7. Тесты {#тесты}

```bash
# Запустить все тесты
pytest tests/ -v

# С покрытием (нужен pytest-cov)
pip install pytest-cov
pytest tests/ --cov=app --cov-report=term-missing
```

Тесты используют отдельную SQLite базу `test_crm.db`, которая создаётся и удаляется автоматически для каждого теста.

---

## 8. FAQ и типичные ошибки {#faq}

### ❓ `403 Forbidden` при запросе к `/api/v1/clients`
Забыли передать заголовок `Authorization: Bearer <token>`. FastAPI использует HTTPBearer — если заголовок отсутствует, возвращается 403 (не 401).

### ❓ `401 Invalid or expired token`
Токен истёк (по умолчанию живёт 24 часа). Залогиньтесь снова через `/auth/login`.

### ❓ `400 Email already registered`
При вызове `/auth/register` с уже существующим email. Используйте другой email или `/auth/login`.

### ❓ Как переключиться с SQLite на PostgreSQL?
В `.env` измените:
```
DATABASE_URL=postgresql://user:password@localhost:5432/crm_db
```
И установите psycopg2:
```bash
pip install psycopg2-binary
```

### ❓ Как сбросить базу данных?
```bash
rm crm.db        # удалить базу
uvicorn app.main:app --reload  # пересоздастся при запуске
python seed.py   # загрузить демо-данные заново
```

### ❓ Как менеджер видит только своих клиентов?
Система автоматически фильтрует. Если `current_user.role == "manager"`, к запросу добавляется условие `WHERE assigned_manager_id = current_user.id`. Администратор видит всё.

### ❓ Как создать миграцию (Alembic)?
```bash
alembic init alembic
# В alembic/env.py указать target_metadata = Base.metadata
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

---

## Переменные окружения (полный список)

| Переменная | Тип | По умолчанию | Описание |
|---|---|---|---|
| `APP_NAME` | str | `CRM Sales` | Название приложения |
| `DEBUG` | bool | `true` | Режим отладки |
| `DATABASE_URL` | str | `sqlite:///./crm.db` | Строка подключения |
| `SECRET_KEY` | str | `super-secret-...` | Ключ JWT (менять!) |
| `ALGORITHM` | str | `HS256` | Алгоритм JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | int | `1440` | Время жизни токена |
