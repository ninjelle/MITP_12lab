"""
Seed the database with demo data.
Run: python seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, timedelta
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.client import Client
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.task import Task

db = SessionLocal()

# ── Users ────────────────────────────────────────────────────────────────────
admin = User(email="admin@crm.com", full_name="Admin User",
             hashed_password=get_password_hash("admin123"), role="admin")
alice = User(email="alice@crm.com", full_name="Alice Ivanova",
             hashed_password=get_password_hash("manager123"), role="manager")
bob   = User(email="bob@crm.com",   full_name="Bob Petrov",
             hashed_password=get_password_hash("manager123"), role="manager")
viewer = User(email="viewer@crm.com", full_name="View Only",
              hashed_password=get_password_hash("viewer123"), role="viewer")

db.add_all([admin, alice, bob, viewer])
db.commit()

# ── Clients ───────────────────────────────────────────────────────────────────
clients_data = [
    dict(company_name="TechCorp LLC", industry="Software", city="Moscow",     country="Russia",  status="active",   assigned_manager_id=alice.id),
    dict(company_name="GreenEnergy",  industry="Energy",   city="Saint-Petersburg", country="Russia", status="prospect", assigned_manager_id=alice.id),
    dict(company_name="RetailPro",    industry="Retail",   city="Kazan",      country="Russia",  status="lead",     assigned_manager_id=bob.id),
    dict(company_name="FinanceHub",   industry="Finance",  city="Novosibirsk",country="Russia",  status="active",   assigned_manager_id=bob.id),
    dict(company_name="MedSystems",   industry="Healthcare",city="Ekaterinburg",country="Russia", status="inactive", assigned_manager_id=alice.id),
]
clients = []
for d in clients_data:
    c = Client(**d)
    db.add(c)
    clients.append(c)
db.commit()

# ── Contacts ──────────────────────────────────────────────────────────────────
contacts_data = [
    dict(client_id=clients[0].id, first_name="Ivan",   last_name="Sokolov", email="ivan@techcorp.ru",  phone="+7 495 111-22-33", position="CEO",     is_primary=True),
    dict(client_id=clients[0].id, first_name="Maria",  last_name="Orlova",  email="maria@techcorp.ru", phone="+7 495 111-22-44", position="CTO",     is_primary=False),
    dict(client_id=clients[1].id, first_name="Sergey", last_name="Volkov",  email="s.volkov@green.ru", phone="+7 812 222-33-44", position="Director",is_primary=True),
    dict(client_id=clients[2].id, first_name="Anna",   last_name="Kozlova", email="a.kozlova@retail.ru",phone="+7 843 333-44-55",position="Manager", is_primary=True),
    dict(client_id=clients[3].id, first_name="Dmitry", last_name="Novikov", email="d.novikov@fin.ru",  phone="+7 383 444-55-66", position="CFO",     is_primary=True),
]
for d in contacts_data:
    db.add(Contact(**d))
db.commit()

# ── Deals ─────────────────────────────────────────────────────────────────────
today = date.today()
deals_data = [
    dict(title="Enterprise License 2025", client_id=clients[0].id, assigned_manager_id=alice.id,
         stage="proposal", amount=150000, probability=50, expected_close_date=today+timedelta(days=30), source="referral"),
    dict(title="Solar Panel Installation", client_id=clients[1].id, assigned_manager_id=alice.id,
         stage="negotiation", amount=85000, probability=75, expected_close_date=today+timedelta(days=14), source="website"),
    dict(title="POS System Upgrade",      client_id=clients[2].id, assigned_manager_id=bob.id,
         stage="qualification", amount=22000, probability=10, expected_close_date=today+timedelta(days=60), source="cold_call"),
    dict(title="Analytics Platform",      client_id=clients[3].id, assigned_manager_id=bob.id,
         stage="closed_won", amount=320000, probability=100, expected_close_date=today-timedelta(days=10),
         actual_close_date=today-timedelta(days=10), source="referral"),
    dict(title="Cloud Migration",         client_id=clients[0].id, assigned_manager_id=alice.id,
         stage="needs_analysis", amount=95000, probability=25, expected_close_date=today+timedelta(days=45), source="website"),
    dict(title="Legacy Support Contract", client_id=clients[4].id, assigned_manager_id=alice.id,
         stage="closed_lost", amount=15000, probability=0, expected_close_date=today-timedelta(days=20),
         actual_close_date=today-timedelta(days=20), source="inbound"),
]
deals = []
for d in deals_data:
    deal = Deal(**d)
    db.add(deal)
    deals.append(deal)
db.commit()

# ── Tasks ─────────────────────────────────────────────────────────────────────
tasks_data = [
    dict(title="Send commercial proposal",  task_type="email",    priority="high",   status="open",
         due_date=today+timedelta(days=1),  client_id=clients[0].id, deal_id=deals[0].id, assigned_to_id=alice.id, created_by_id=admin.id),
    dict(title="Schedule demo meeting",     task_type="meeting",  priority="high",   status="open",
         due_date=today+timedelta(days=2),  client_id=clients[1].id, deal_id=deals[1].id, assigned_to_id=alice.id, created_by_id=alice.id),
    dict(title="Follow up after call",      task_type="follow_up",priority="medium", status="in_progress",
         due_date=today,                    client_id=clients[2].id, deal_id=deals[2].id, assigned_to_id=bob.id,   created_by_id=bob.id),
    dict(title="Prepare contract draft",    task_type="other",    priority="urgent", status="open",
         due_date=today-timedelta(days=1),  client_id=clients[3].id, deal_id=deals[3].id, assigned_to_id=bob.id,   created_by_id=admin.id),
    dict(title="Quarterly account review",  task_type="call",     priority="low",    status="open",
         due_date=today+timedelta(days=7),  client_id=clients[0].id,                      assigned_to_id=alice.id, created_by_id=alice.id),
]
for d in tasks_data:
    db.add(Task(**d))
db.commit()

db.close()
print("✅ Demo data seeded successfully!")
print("\nLogin credentials:")
print("  admin@crm.com   / admin123   (role: admin)")
print("  alice@crm.com   / manager123 (role: manager)")
print("  bob@crm.com     / manager123 (role: manager)")
print("  viewer@crm.com  / viewer123  (role: viewer)")
