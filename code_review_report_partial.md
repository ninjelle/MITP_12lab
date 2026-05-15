# Отчёт: исправления AI-сгенерированного кода CRM

---

## Исправление 1 — Мёртвый код: неиспользуемый enum-класс

**Файл:** `app/models/client.py`

**Что сгенерировал ИИ:**
```python
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
import enum

class ClientStatus(str, enum.Enum):
    lead = "lead"
    prospect = "prospect"
    active = "active"
    inactive = "inactive"
    churned = "churned"

class Client(Base):
    status = Column(String(50), default="lead")  # String, а не Enum!
```

**В чём проблема:**
Объявлен класс `ClientStatus` как Python enum, но колонка `status` в модели всё равно объявлена как `Column(String, ...)`, а не `Column(Enum(ClientStatus), ...)`. Класс нигде не используется — это мёртвый код. Импорты `Enum` из sqlalchemy и `import enum` из stdlib тоже висят впустую. Без ограничения на уровне БД в поле `status` можно записать любую произвольную строку.

**Как исправил:**
```python
# Было:
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
import enum

class ClientStatus(str, enum.Enum):
    lead = "lead"
    ...

# Стало:
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
# import enum — удалён
# class ClientStatus — удалён
```

---

## Исправление 2 — Устаревший путь импорта SQLAlchemy

**Файл:** `app/core/database.py`

**Что сгенерировал ИИ:**
```python
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
```

**В чём проблема:**
`sqlalchemy.ext.declarative.declarative_base` был перемещён в `sqlalchemy.orm` начиная с SQLAlchemy 2.0. Старый путь импорта выдаёт предупреждение `MovedIn20Warning` при каждом запуске приложения и тестов. Это технический долг — при обновлении до SQLAlchemy 3.x старый путь будет удалён и приложение сломается.

**Как исправил:**
```python
# Было:
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Стало:
from sqlalchemy.orm import sessionmaker, declarative_base
```

---

## Исправление 3 — Неиспользуемый импорт и магическая константа

**Файл:** `app/core/security.py`

**Что сгенерировал ИИ:**
```python
from fastapi import Depends, HTTPException, status

def decode_token(token: str) -> dict:
    ...
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        ...
    )
```

**В чём проблема:**
Импортируется весь модуль `status` из fastapi, но используется только в одном месте — `status.HTTP_401_UNAUTHORIZED`. При этом значение константы всем известно: это просто `401`. Везде в остальном коде проекта числовые коды используются напрямую (`401`, `403`, `404`). Использование `status.HTTP_401_UNAUTHORIZED` только в одном месте создаёт непоследовательность стиля и тянет лишний импорт.

**Как исправил:**
```python
# Было:
from fastapi import Depends, HTTPException, status
...
raise HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
)

# Стало:
from fastapi import Depends, HTTPException
...
raise HTTPException(
    status_code=401,
    detail="Invalid or expired token",
)
```

---

## Исправление 4 — Ленивый импорт внутри тела функции

**Файл:** `app/core/security.py`

**Что сгенерировал ИИ:**
```python
def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    from app.models.user import User   # импорт внутри функции!
    payload = decode_token(credentials.credentials)
    ...
```

**В чём проблема:**
Импорт `User` внутри тела функции выполняется при каждом HTTP-запросе, требующем аутентификации. Единственное оправданное применение такого паттерна — разрыв циклических импортов. Здесь цикла нет: `security.py` не импортируется из `models/user.py`. Это антипаттерн, который скрывает зависимости модуля и затрудняет анализ кода.

**Как исправил:**
```python
# Было: импорт внутри функции
def get_current_user(...):
    from app.models.user import User
    ...

# Стало: импорт на уровне модуля
from app.models.user import User  # в начале файла

def get_current_user(...):
    # from app.models.user import User — удалён
    ...
```

---

## Исправление 5 — Неиспользуемые импорты в роутере сделок

**Файл:** `app/api/v1/deals.py`

**Что сгенерировал ИИ:**
```python
from sqlalchemy import func
from datetime import datetime
```

**В чём проблема:**
`func` из sqlalchemy импортируется, но нигде в файле не используется — ни в одном запросе нет агрегатных функций. `datetime` тоже импортируется, но в коде используется только `date` (для `date.today()`), а не `datetime`. Оба импорта — лишний шум, который вводит читателя в заблуждение: создаётся ощущение что где-то используется агрегация или работа со временем.

**Как исправил:**
```python
# Было:
from sqlalchemy import func       # нигде не используется
from datetime import datetime     # используется только date, не datetime

# Стало:
# from sqlalchemy import func — удалён полностью
from datetime import date         # только то, что реально нужно
```

---

## Итоговая таблица

| # | Файл | Категория | Проблема | Коммит |
|---|------|-----------|----------|--------|
| 1 | `models/client.py` | Мёртвый код | `ClientStatus` enum объявлен но не используется, лишние импорты | `fix: remove unused ClientStatus enum and dead imports from client model` |
| 2 | `core/database.py` | Устаревший API | Старый путь импорта `declarative_base` из SQLAlchemy 1.x | `fix: replace deprecated declarative_base import path for SQLAlchemy 2.0` |
| 3 | `core/security.py` | Нарушение стиля | Импорт `status` ради одной константы, непоследовательность с остальным кодом | `fix: remove unused status import, replace HTTP_401_UNAUTHORIZED with literal 401` |
| 4 | `core/security.py` | Нарушение стиля | Импорт `User` внутри тела функции без необходимости | `fix: move User import to module level, remove lazy import from function body` |
| 5 | `api/v1/deals.py` | Мёртвый код | `func` не используется, `datetime` импортирован вместо нужного `date` | `fix: remove unused func import and replace datetime with date in deals router` |
