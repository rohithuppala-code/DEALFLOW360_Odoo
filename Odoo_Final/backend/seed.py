"""Idempotent demo seed for DealFlow360."""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

sys.path.insert(0, os.path.dirname(__file__))

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app import models  # noqa: F401
from app.models.billing import Invoice, InvoiceLine, Payment, Subscription, SubscriptionPlan
from app.models.catalog import PriceList, PriceListItem, Product, ProductCategory, ProductVariant
from app.models.customer import Customer, CustomerTier
from app.models.enums import (
    ApprovalStatus,
    BillingInterval,
    BillingType,
    CategoryKind,
    ConditionType,
    CustomerStatus,
    EventType,
    InvoiceStatus,
    NegotiationStatus,
    PaymentStatus,
    ProductType,
    QuoteStatus,
    RecommendationType,
    RuleActionType,
    RuleType,
    Severity,
    SubscriptionStatus,
    UserRole,
)
from app.models.fulfillment import Inventory, Warehouse
from app.models.governance import ApprovalChain, ApprovalRule, DiscountRule
from app.models.intelligence import RecommendationRule, RuleAction, RuleCondition, RuleDefinition, SystemSetting
from app.models.ops import Order
from app.models.quote import Quote, QuoteLine
from app.models.timeline import DealEvent, Notification
from app.models.user import User
from app.services.quote import quote_engine
from app.utils.money import D

DEMO = get_settings().demo_password


def get_or_create(db: Session, model, defaults: dict | None = None, **kwargs):
    row = db.query(model).filter_by(**kwargs).first()
    if row:
        return row, False
    params = {**kwargs, **(defaults or {})}
    row = model(**params)
    db.add(row)
    db.flush()
    return row, True


def seed_tiers(db: Session) -> dict[str, CustomerTier]:
    spec = [
        ("Bronze", "Emerging accounts", 5, 1.4),
        ("Silver", "Established mid-market", 10, 1.15),
        ("Gold", "Strategic accounts", 12, 1.0),
        ("Platinum", "Enterprise strategic", 18, 0.7),
    ]
    out = {}
    for name, desc, limit, mult in spec:
        t, _ = get_or_create(
            db,
            CustomerTier,
            {"description": desc, "default_discount_limit": limit, "risk_multiplier": mult},
            name=name,
        )
        out[name] = t
    return out


def seed_users(db: Session, customers: dict[str, Customer]) -> dict[str, User]:
    pw = hash_password(DEMO)
    spec = [
        ("Priya Sharma", "sales@demo.com", UserRole.SALES_REP, None),
        ("Rahul Mehta", "manager@demo.com", UserRole.SALES_MANAGER, None),
        ("Ananya Iyer", "finance@demo.com", UserRole.FINANCE, None),
        ("Vikram Patel", "ops@demo.com", UserRole.OPERATIONS, None),
        ("Neha Kapoor", "customer@acme.com", UserRole.CUSTOMER, "Acme Corporation"),
        ("System Admin", "admin@demo.com", UserRole.ADMIN, None),
        ("Arjun Nair", "sales2@demo.com", UserRole.SALES_REP, None),
    ]
    users = {}
    for name, email, role, cust_name in spec:
        cid = customers[cust_name].id if cust_name else None
        u, created = get_or_create(
            db,
            User,
            {"name": name, "password_hash": pw, "role": role, "is_active": True, "customer_id": cid},
            email=email,
        )
        if not created:
            u.password_hash = pw
            u.role = role
            u.customer_id = cid
            u.is_active = True
        users[email] = u
    db.flush()
    return users


def seed_customers(db: Session, tiers: dict[str, CustomerTier], sales_id: int) -> dict[str, Customer]:
    spec = [
        ("Acme Corporation", "ACME", "gold.ops@acme.test", "Manufacturing", "Gold", 2500000, 30, "Ahmedabad"),
        ("Globex Industries", "GLOBEX", "buyer@globex.test", "Industrial", "Platinum", 8000000, 45, "Mumbai"),
        ("Nova Retail", "NOVA", "proc@novaretail.test", "Retail", "Silver", 1200000, 30, "Bangalore"),
        ("Vertex Systems", "VERTEX", "it@vertex.test", "Technology", "Gold", 3000000, 30, "Mumbai"),
        ("Zenith Technologies", "ZENITH", "ops@zenith.test", "IT Services", "Bronze", 400000, 15, "Ahmedabad"),
        ("Helios Manufacturing", "HELIOS", "buy@helios.test", "Manufacturing", "Gold", 2200000, 30, "Ahmedabad"),
        ("Orion Health", "ORION", "cio@orionhealth.test", "Healthcare", "Platinum", 5000000, 45, "Bangalore"),
        ("Pinnacle Logistics", "PINN", "fleet@pinnacle.test", "Logistics", "Silver", 900000, 30, "Mumbai"),
        ("Nimbus Software", "NIMBUS", "cto@nimbus.test", "SaaS", "Gold", 1800000, 30, "Bangalore"),
        ("Aether Capital", "AETHER", "it@aether.test", "Financial Services", "Platinum", 6000000, 60, "Mumbai"),
    ]
    out = {}
    for name, code, email, industry, tier, credit, terms, city in spec:
        c, _ = get_or_create(
            db,
            Customer,
            {
                "name": name,
                "email": email,
                "industry": industry,
                "customer_tier_id": tiers[tier].id,
                "credit_limit": credit,
                "payment_terms": terms,
                "status": CustomerStatus.ACTIVE,
                "city": city,
                "sales_rep_id": sales_id,
                "avg_accept_days": 2 if tier in ("Gold", "Platinum") else 5,
                "historical_avg_discount": 8 if tier != "Platinum" else 12,
            },
            code=code,
        )
        out[name] = c
    db.flush()
    return out


def seed_catalog(db: Session) -> dict[str, Product]:
    cats = {}
    for name, kind, desc in [
        ("Hardware", CategoryKind.HARDWARE, "Laptops, servers, networking"),
        ("Accessories", CategoryKind.ACCESSORY, "Docks, peripherals"),
        ("Services", CategoryKind.SERVICE, "Implementation, installation, warranty"),
        ("Subscriptions", CategoryKind.SUBSCRIPTION, "Support, analytics, backup, CRM"),
        ("Software", CategoryKind.SOFTWARE, "Licensed software"),
    ]:
        c, _ = get_or_create(db, ProductCategory, {"kind": kind, "description": desc}, name=name)
        cats[name] = c

    plans = {}
    for name, interval, price, setup, trial, cost in [
        ("Premium Support Monthly", BillingInterval.MONTHLY, 25000, 0, 0, 8000),
        ("Analytics Add-on Monthly", BillingInterval.MONTHLY, 18000, 0, 0, 5000),
        ("Cloud Backup Monthly", BillingInterval.MONTHLY, 8000, 0, 0, 2500),
        ("CRM Enterprise Monthly", BillingInterval.MONTHLY, 45000, 15000, 14, 12000),
    ]:
        p, _ = get_or_create(
            db,
            SubscriptionPlan,
            {
                "description": name,
                "billing_interval": interval,
                "price": price,
                "setup_fee": setup,
                "trial_days": trial,
                "cost": cost,
            },
            name=name,
        )
        plans[name] = p

    products_spec = [
        ("LAP-PRO", "Laptop Pro", "Hardware", ProductType.ONE_TIME, 72000, 52000, 1.8, 72000, None, "Flagship business laptop"),
        ("LAP-AIR", "Laptop Air", "Hardware", ProductType.ONE_TIME, 58000, 42000, 1.2, 58000, None, "Ultralight knowledge-worker laptop"),
        ("SRV-ENT", "Enterprise Server", "Hardware", ProductType.ONE_TIME, 285000, 198000, 18, 285000, None, "Rack server for branch compute"),
        ("NET-SW", "Network Switch", "Hardware", ProductType.ONE_TIME, 45000, 31000, 3.5, 45000, None, "48-port managed switch"),
        ("DOCK-01", "Docking Station", "Accessories", ProductType.ONE_TIME, 12500, 7200, 0.8, 12500, None, "Universal USB-C dock"),
        ("WAR-PREM", "Premium Warranty", "Services", ProductType.SERVICE, 18000, 6000, 0, 18000, None, "3-year onsite premium warranty"),
        ("IMP-01", "Implementation Service", "Services", ProductType.SERVICE, 80000, 28000, 0, 80000, None, "Enterprise rollout & configuration"),
        ("INST-01", "Installation Service", "Services", ProductType.SERVICE, 15000, 5000, 0, 24000, None, "On-site installation & imaging"),
        ("SUP-PREM", "Premium Support", "Subscriptions", ProductType.SUBSCRIPTION, 25000, 8000, 0, 35000, "Premium Support Monthly", "24×7 named support"),
        ("ANL-01", "Analytics Add-on", "Subscriptions", ProductType.SUBSCRIPTION, 18000, 5000, 0, 18000, "Analytics Add-on Monthly", "Deal & usage analytics pack"),
        ("BKP-01", "Cloud Backup", "Subscriptions", ProductType.SUBSCRIPTION, 8000, 2500, 0, 8000, "Cloud Backup Monthly", "Encrypted cloud backup"),
        ("CRM-ENT", "CRM Enterprise", "Subscriptions", ProductType.SUBSCRIPTION, 45000, 12000, 0, 45000, "CRM Enterprise Monthly", "Full CRM workspace"),
    ]
    products = {}
    for sku, name, cat, ptype, price, cost, weight, perceived, plan_name, desc in products_spec:
        p, _ = get_or_create(
            db,
            Product,
            {
                "category_id": cats[cat].id,
                "name": name,
                "description": desc,
                "product_type": ptype,
                "base_price": price,
                "cost_price": cost,
                "weight": weight,
                "is_active": True,
                "subscription_plan_id": plans[plan_name].id if plan_name else None,
                "perceived_value": perceived,
            },
            sku=sku,
        )
        products[sku] = p

    get_or_create(
        db,
        ProductVariant,
        {
            "product_id": products["LAP-PRO"].id,
            "name": "16GB / 512GB",
            "attributes_json": {"ram": "16GB", "storage": "512GB"},
            "price_adjustment": 0,
            "cost_adjustment": 0,
            "is_active": True,
        },
        sku="LAP-PRO-16-512",
    )
    get_or_create(
        db,
        ProductVariant,
        {
            "product_id": products["LAP-PRO"].id,
            "name": "32GB / 1TB",
            "attributes_json": {"ram": "32GB", "storage": "1TB"},
            "price_adjustment": 14000,
            "cost_adjustment": 9000,
            "is_active": True,
        },
        sku="LAP-PRO-32-1T",
    )
    return products


def seed_price_lists(db: Session, tiers: dict, products: dict):
    for tname, discount in [("Gold", 0.02), ("Platinum", 0.04), ("Silver", 0.0), ("Bronze", 0.0)]:
        pl, _ = get_or_create(
            db, PriceList, {"currency": "INR", "customer_tier_id": tiers[tname].id, "is_active": True}, name=f"{tname} List"
        )
        for p in products.values():
            existing = (
                db.query(PriceListItem)
                .filter(PriceListItem.price_list_id == pl.id, PriceListItem.product_id == p.id)
                .first()
            )
            if existing:
                continue
            db.add(
                PriceListItem(
                    price_list_id=pl.id,
                    product_id=p.id,
                    unit_price=round(float(p.base_price) * (1 - discount), 2),
                    min_quantity=1,
                )
            )


def seed_discount_rules(db: Session, tiers: dict, cats: dict):
    hardware = db.query(ProductCategory).filter(ProductCategory.name == "Hardware").first()
    services = db.query(ProductCategory).filter(ProductCategory.name == "Services").first()
    accessories = db.query(ProductCategory).filter(ProductCategory.name == "Accessories").first()
    spec = [
        ("Gold Hardware ≤ 15%", "Gold", hardware, 15),
        ("Gold Services ≤ 10%", "Gold", services, 10),
        ("Platinum Hardware ≤ 20%", "Platinum", hardware, 20),
        ("Platinum Services ≤ 15%", "Platinum", services, 15),
        ("Silver Hardware ≤ 10%", "Silver", hardware, 10),
        ("Silver Services ≤ 7%", "Silver", services, 7),
        ("Bronze Hardware ≤ 5%", "Bronze", hardware, 5),
        ("Bronze Services ≤ 3%", "Bronze", services, 3),
        ("Gold Accessories ≤ 12%", "Gold", accessories, 12),
    ]
    for name, tname, cat, mx in spec:
        get_or_create(
            db,
            DiscountRule,
            {
                "customer_tier_id": tiers[tname].id,
                "category_id": cat.id if cat else None,
                "max_discount_percent": mx,
                "severity": Severity.HIGH if mx <= 10 else Severity.MEDIUM,
                "requires_approval": True,
                "is_active": True,
            },
            name=name,
        )


def seed_approvals(db: Session):
    chain, _ = get_or_create(
        db, ApprovalChain, {"description": "Standard commercial governance", "is_active": True}, name="Standard Deal Chain"
    )
    rules = [
        (ConditionType.DISCOUNT_EXCEEDS_TIER, "0", UserRole.SALES_MANAGER, 1),
        (ConditionType.MARGIN_BELOW, "18", UserRole.FINANCE, 2),
        (ConditionType.RISK_ABOVE, "70", UserRole.SALES_MANAGER, 1),
        (ConditionType.RISK_ABOVE, "85", UserRole.FINANCE, 2),
        (ConditionType.DEAL_VALUE_ABOVE, "2500000", UserRole.SALES_MANAGER, 1),
        (ConditionType.PAYMENT_TERMS_ABOVE, "45", UserRole.FINANCE, 2),
    ]
    for ctype, val, role, seq in rules:
        exists = (
            db.query(ApprovalRule)
            .filter(
                ApprovalRule.approval_chain_id == chain.id,
                ApprovalRule.condition_type == ctype,
                ApprovalRule.condition_value == val,
                ApprovalRule.required_role == role,
            )
            .first()
        )
        if not exists:
            db.add(
                ApprovalRule(
                    approval_chain_id=chain.id,
                    condition_type=ctype,
                    condition_value=val,
                    required_role=role,
                    sequence=seq,
                )
            )


def seed_warehouses(db: Session, products: dict):
    spec = [
        ("Ahmedabad DC", "AMD", "Ahmedabad", "WEST", 120, 94, 2),
        ("Mumbai DC", "BOM", "Mumbai", "WEST", 160, 91, 2),
        ("Bangalore DC", "BLR", "Bangalore", "SOUTH", 140, 88, 3),
    ]
    wh = {}
    for name, code, city, zone, handling, rel, lead in spec:
        w, _ = get_or_create(
            db,
            Warehouse,
            {
                "name": name,
                "city": city,
                "address": f"{name}, {city}",
                "shipping_zone": zone,
                "handling_cost": handling,
                "reliability_score": rel,
                "avg_lead_days": lead,
            },
            code=code,
        )
        wh[code] = w

    # Deliberately uneven stock so optimizer has a story
    stock = {
        "AMD": {"LAP-PRO": 14, "LAP-AIR": 20, "SRV-ENT": 2, "NET-SW": 8, "DOCK-01": 0, "WAR-PREM": 99, "IMP-01": 99, "INST-01": 99},
        "BOM": {"LAP-PRO": 4, "LAP-AIR": 10, "SRV-ENT": 3, "NET-SW": 12, "DOCK-01": 20, "WAR-PREM": 99, "IMP-01": 99, "INST-01": 99},
        "BLR": {"LAP-PRO": 2, "LAP-AIR": 6, "SRV-ENT": 8, "NET-SW": 16, "DOCK-01": 8, "WAR-PREM": 99, "IMP-01": 99, "INST-01": 99},
    }
    for code, items in stock.items():
        for sku, qty in items.items():
            p = products.get(sku)
            if not p:
                continue
            row = (
                db.query(Inventory)
                .filter(Inventory.warehouse_id == wh[code].id, Inventory.product_id == p.id, Inventory.variant_id.is_(None))
                .first()
            )
            if row:
                row.available_qty = qty
                continue
            db.add(
                Inventory(
                    warehouse_id=wh[code].id,
                    product_id=p.id,
                    available_qty=qty,
                    reserved_qty=0,
                    reorder_level=3,
                    expected_replenishment=date.today() + timedelta(days=10) if qty < 5 else None,
                )
            )
    return wh


def seed_recommendations(db: Session, products: dict):
    spec = [
        ("LAP-PRO", "WAR-PREM", RecommendationType.UPSELL, 90, "Customers purchasing Laptop Pro frequently add Premium Warranty."),
        ("LAP-PRO", "DOCK-01", RecommendationType.CROSS_SELL, 80, "Docking Station is attached to 64% of Laptop Pro deals."),
        ("LAP-PRO", "SUP-PREM", RecommendationType.CROSS_SELL, 88, "Premium Support lifts renewal and protects hardware margin."),
        ("LAP-AIR", "DOCK-01", RecommendationType.CROSS_SELL, 70, "Knowledge workers typically add a dock."),
        ("SRV-ENT", "BKP-01", RecommendationType.CROSS_SELL, 85, "Servers without Cloud Backup create restore risk."),
        ("CRM-ENT", "ANL-01", RecommendationType.UPSELL, 75, "Analytics Add-on is the natural expansion on CRM Enterprise."),
        ("IMP-01", "INST-01", RecommendationType.BUNDLE, 60, "Installation is often bundled with implementation."),
    ]
    for src, dst, rtype, prio, reason in spec:
        get_or_create(
            db,
            RecommendationRule,
            {
                "recommended_product_id": products[dst].id,
                "recommendation_type": rtype,
                "priority": prio,
                "reason": reason,
                "is_active": True,
                "confidence": prio,
            },
            product_id=products[src].id,
            recommended_product_id=products[dst].id,
        )


def seed_settings_and_rules(db: Session):
    get_or_create(
        db,
        SystemSetting,
        {
            "value_json": {
                "discount_exception": 3.0,
                "discount_exception_cap": 30,
                "low_margin": 2.0,
                "low_margin_cap": 25,
                "target_margin": 18.0,
                "delivery": 1.0,
                "delivery_cap": 15,
                "inventory": 1.0,
                "inventory_cap": 15,
                "negotiation": 5.0,
                "negotiation_cap": 15,
                "customer_bronze": 8,
                "customer_silver": 5,
                "customer_gold": 2,
                "customer_platinum": 0,
                "anomaly_cap": 12,
                "deal_size_cap": 8,
                "payment_terms_cap": 10,
            },
            "description": "Weighted risk scoring configuration",
        },
        key="risk_weights",
    )
    rule, created = get_or_create(
        db,
        RuleDefinition,
        {
            "description": "Gold service discounts above 10% require manager approval and raise risk",
            "rule_type": RuleType.APPROVAL,
            "is_active": True,
            "priority": 10,
        },
        name="Gold service discount governance",
    )
    if created:
        db.add(RuleCondition(rule_id=rule.id, field="customer_tier", operator="=", value="Gold", logical_operator="AND"))
        db.add(RuleCondition(rule_id=rule.id, field="category", operator="=", value="Services", logical_operator="AND"))
        db.add(RuleCondition(rule_id=rule.id, field="discount_percent", operator=">", value="10", logical_operator="AND"))
        db.add(RuleAction(rule_id=rule.id, action_type=RuleActionType.REQUIRE_APPROVAL, action_value="SALES_MANAGER"))
        db.add(RuleAction(rule_id=rule.id, action_type=RuleActionType.RAISE_RISK, action_value="15"))


def _line(db, quote, product, qty, disc):
    quote_engine._upsert_line(
        db,
        quote,
        {"product_id": product.id, "quantity": qty, "discount_percent": disc},
    )


def seed_quotes(db: Session, customers: dict, users: dict, products: dict):
    sales = users["sales@demo.com"]
    sales2 = users["sales2@demo.com"]
    existing = db.query(Quote).filter(Quote.quote_number == "Q-2026-0042").first()
    if existing:
        # still ensure intelligence is current
        quote_engine.recalculate(db, existing)
        return existing

    def make_quote(number, customer, rep, title, status, lines, days_ago=3, extra=None):
        q = Quote(
            quote_number=number,
            customer_id=customer.id,
            sales_rep_id=rep.id,
            status=status,
            currency="INR",
            payment_terms=customer.payment_terms,
            title=title,
            expires_at=date.today() + timedelta(days=18),
            promised_delivery_date=date.today() + timedelta(days=12),
            tax_percent=18,
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        )
        if extra:
            for k, v in extra.items():
                setattr(q, k, v)
        db.add(q)
        db.flush()
        for sku, qty, disc in lines:
            _line(db, q, products[sku], qty, disc)
        db.flush()
        quote_engine.recalculate(db, q)
        from app.services.fulfillment import WarehouseAllocationService

        WarehouseAllocationService().persist_initial(db, q, customer)
        quote_engine.recalculate(db, q)
        db.add(
            DealEvent(
                quote_id=q.id,
                event_type=EventType.QUOTE_CREATED,
                actor_id=rep.id,
                description=f"Quote {number} created",
            )
        )
        return q

    # Hero demo deal — Gold + 12% hardware + 18% service
    hero = make_quote(
        "Q-2026-0042",
        customers["Acme Corporation"],
        sales,
        "Enterprise Hardware + Support",
        QuoteStatus.DRAFT,
        [("LAP-PRO", 10, 12), ("IMP-01", 1, 18), ("DOCK-01", 2, 5)],
        days_ago=1,
    )
    hero.notes = "Strategic laptop refresh for Acme Ahmedabad HQ + plant."

    # Pipeline fillers — mix of statuses, large enough to look like 2+ Cr
    fillers = [
        ("Q-2026-0031", "Globex Industries", sales, "Datacenter refresh", QuoteStatus.PENDING_APPROVAL, [("SRV-ENT", 6, 14), ("BKP-01", 6, 5)], 6),
        ("Q-2026-0034", "Vertex Systems", sales, "Laptop fleet H1", QuoteStatus.APPROVED, [("LAP-PRO", 40, 11), ("DOCK-01", 40, 8), ("WAR-PREM", 40, 5)], 8),
        ("Q-2026-0036", "Nova Retail", sales2, "Store POS rollout", QuoteStatus.NEGOTIATING, [("LAP-AIR", 25, 9), ("NET-SW", 8, 6)], 4),
        ("Q-2026-0038", "Helios Manufacturing", sales, "Plant network", QuoteStatus.DRAFT, [("NET-SW", 20, 8), ("SRV-ENT", 2, 10)], 2),
        ("Q-2026-0039", "Orion Health", sales, "Clinical CRM", QuoteStatus.PENDING_APPROVAL, [("CRM-ENT", 12, 8), ("ANL-01", 12, 5), ("IMP-01", 1, 12)], 5),
        ("Q-2026-0040", "Pinnacle Logistics", sales2, "Dispatch laptops", QuoteStatus.DRAFT, [("LAP-AIR", 18, 7)], 1),
        ("Q-2026-0041", "Nimbus Software", sales, "HQ workstation", QuoteStatus.APPROVED, [("LAP-PRO", 16, 10), ("SUP-PREM", 16, 0)], 7),
        ("Q-2026-0043", "Aether Capital", sales, "Trading floor kit", QuoteStatus.PENDING_APPROVAL, [("LAP-PRO", 30, 16), ("DOCK-01", 30, 10), ("SUP-PREM", 30, 5)], 3),
        ("Q-2026-0044", "Zenith Technologies", sales2, "Starter bundle", QuoteStatus.DRAFT, [("LAP-AIR", 8, 4), ("INST-01", 1, 0)], 1),
        ("Q-2026-0045", "Globex Industries", sales, "Backup expansion", QuoteStatus.NEGOTIATING, [("BKP-01", 40, 10), ("SRV-ENT", 3, 12)], 9),
        ("Q-2026-0028", "Vertex Systems", sales, "Q1 confirmed fleet", QuoteStatus.CONFIRMED, [("LAP-PRO", 20, 8), ("WAR-PREM", 20, 5)], 20),
        ("Q-2026-0025", "Acme Corporation", sales, "Last quarter servers", QuoteStatus.CONFIRMED, [("SRV-ENT", 4, 10), ("IMP-01", 1, 8)], 40),
        ("Q-2026-0022", "Orion Health", sales, "Analytics expansion", QuoteStatus.CONFIRMED, [("ANL-01", 10, 0)], 25),
        ("Q-2026-0020", "Nova Retail", sales2, "Pilot laptops", QuoteStatus.REJECTED, [("LAP-PRO", 6, 22)], 12),
        ("Q-2026-0033", "Helios Manufacturing", sales, "Warranty uplift", QuoteStatus.APPROVED, [("WAR-PREM", 50, 6)], 10),
        ("Q-2026-0037", "Aether Capital", sales, "CRM core", QuoteStatus.DRAFT, [("CRM-ENT", 20, 12), ("IMP-01", 1, 15)], 2),
        ("Q-2026-0029", "Pinnacle Logistics", sales2, "Confirmed switches", QuoteStatus.CONFIRMED, [("NET-SW", 12, 5)], 18),
        ("Q-2026-0030", "Nimbus Software", sales, "Support estate", QuoteStatus.CONFIRMED, [("SUP-PREM", 24, 0)], 15),
        ("Q-2026-0046", "Acme Corporation", sales, "Plant accessories", QuoteStatus.PENDING_APPROVAL, [("DOCK-01", 40, 14)], 2),
        ("Q-2026-0047", "Globex Industries", sales, "Gold servers + impl", QuoteStatus.PENDING_APPROVAL, [("SRV-ENT", 5, 18), ("IMP-01", 1, 16)], 4),
        ("Q-2026-0048", "Vertex Systems", sales, "Air fleet", QuoteStatus.NEGOTIATING, [("LAP-AIR", 35, 12), ("DOCK-01", 35, 9)], 6),
        ("Q-2026-0049", "Orion Health", sales, "Backup + support", QuoteStatus.DRAFT, [("BKP-01", 20, 0), ("SUP-PREM", 8, 0)], 1),
        ("Q-2026-0050", "Zenith Technologies", sales2, "Over-discount attempt", QuoteStatus.PENDING_APPROVAL, [("LAP-PRO", 5, 19), ("IMP-01", 1, 22)], 3),
    ]
    for number, cname, rep, title, status, lines, days in fillers:
        if db.query(Quote).filter(Quote.quote_number == number).first():
            continue
        q = make_quote(number, customers[cname], rep, title, status, lines, days_ago=days)
        if status == QuoteStatus.CONFIRMED:
            q.approval_status = ApprovalStatus.APPROVED
            q.confirmed_at = datetime.utcnow() - timedelta(days=days)
        elif status == QuoteStatus.APPROVED:
            q.approval_status = ApprovalStatus.APPROVED
            q.sent_to_customer_at = datetime.utcnow() - timedelta(days=1)
        elif status == QuoteStatus.PENDING_APPROVAL:
            q.approval_status = ApprovalStatus.PENDING
        elif status == QuoteStatus.NEGOTIATING:
            q.approval_status = ApprovalStatus.APPROVED
            q.negotiation_status = NegotiationStatus.OPEN
            q.sent_to_customer_at = datetime.utcnow() - timedelta(days=2)
        elif status == QuoteStatus.REJECTED:
            q.approval_status = ApprovalStatus.REJECTED

    # Historical low-discount quotes for anomaly baseline
    for i, disc in enumerate([7, 8, 9, 8, 10]):
        num = f"Q-2025-01{i:02d}"
        if db.query(Quote).filter(Quote.quote_number == num).first():
            continue
        q = make_quote(
            num,
            customers["Acme Corporation"],
            sales,
            f"Historical deal {i}",
            QuoteStatus.CONFIRMED,
            [("LAP-AIR", 4, disc)],
            days_ago=80 + i * 10,
        )
        q.approval_status = ApprovalStatus.APPROVED

    db.flush()
    from app.services.approval import approval_svc

    pending = db.query(Quote).filter(Quote.status == QuoteStatus.PENDING_APPROVAL).all()
    for q in pending:
        intel = quote_engine.recalculate(db, q)
        ctx = quote_engine._approval_context(q, intel)
        try:
            approval_svc.submit(db, q, q.sales_rep or sales, ctx)
        except Exception:
            continue
    db.flush()
    return hero


def seed_live_billing(db: Session):
    """Give the control tower real MRR / invoices without confirming the hero deal."""
    from datetime import date

    from app.models.billing import Invoice, InvoiceLine, Subscription
    from app.models.enums import BillingType, InvoiceStatus, ProductType, QuoteStatus, SubscriptionStatus
    from app.services.billing import BillingService, to_mrr

    if db.query(Subscription).count() > 0:
        return
    bill = BillingService()
    confirmed = db.query(Quote).filter(Quote.status == QuoteStatus.CONFIRMED).all()
    for q in confirmed:
        for ln in q.lines:
            if not ln.product or ln.product.product_type != ProductType.SUBSCRIPTION:
                continue
            plan = ln.subscription_plan or ln.product.subscription_plan
            if not plan:
                continue
            db.add(
                Subscription(
                    customer_id=q.customer_id,
                    quote_id=q.id,
                    plan_id=plan.id,
                    product_id=ln.product_id,
                    status=SubscriptionStatus.ACTIVE,
                    start_date=date.today().replace(day=1),
                    billing_interval=plan.billing_interval,
                    quantity=ln.quantity,
                    unit_price=ln.unit_price,
                    discount_percent=ln.discount_percent,
                    next_billing_date=date.today(),
                    mrr=to_mrr(D(ln.unit_price), plan.billing_interval, ln.quantity, D(ln.discount_percent)),
                )
            )
        if db.query(Invoice).filter(Invoice.quote_id == q.id).first():
            continue
        inv = Invoice(
            invoice_number=bill._next_invoice_number(db),
            customer_id=q.customer_id,
            quote_id=q.id,
            status=InvoiceStatus.ISSUED,
            invoice_date=date.today(),
            due_date=date.today(),
            subtotal=q.subtotal,
            discount=q.discount_total,
            tax=q.tax_total,
            total=q.total,
            balance_due=q.total,
        )
        db.add(inv)
        db.flush()
        db.add(
            InvoiceLine(
                invoice_id=inv.id,
                description=q.title or q.quote_number,
                quantity=1,
                unit_price=q.total,
                amount=q.total,
                billing_type=BillingType.ONE_TIME,
            )
        )
    db.flush()


def seed_notifications(db: Session, users: dict):
    if db.query(Notification).count() > 0:
        return
    db.add(
        Notification(
            user_id=users["manager@demo.com"].id,
            type="APPROVAL_NEEDED",
            title="Approvals waiting",
            message="Several deals exceed Gold discount policy and need a manager decision.",
            severity=Severity.HIGH,
            related_entity_type="approval",
        )
    )
    db.add(
        Notification(
            user_id=users["sales@demo.com"].id,
            type="COPILOT",
            title="Acme deal needs attention",
            message="Q-2026-0042 service discount is 8 points above Gold policy.",
            severity=Severity.HIGH,
            related_entity_type="quote",
        )
    )


def main():
    print("Creating schema if needed…")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Seeding tiers…")
        tiers = seed_tiers(db)
        print("Seeding catalog…")
        products = seed_catalog(db)
        print("Seeding price lists / rules / warehouses…")
        seed_price_lists(db, tiers, products)
        cats = {c.name: c for c in db.query(ProductCategory).all()}
        seed_discount_rules(db, tiers, cats)
        seed_approvals(db)
        seed_warehouses(db, products)
        seed_recommendations(db, products)
        seed_settings_and_rules(db)
        db.flush()
        # customers need a sales user — create a stub sales first
        pw = hash_password(DEMO)
        sales, _ = get_or_create(
            db,
            User,
            {"name": "Priya Sharma", "password_hash": pw, "role": UserRole.SALES_REP, "is_active": True},
            email="sales@demo.com",
        )
        print("Seeding customers…")
        customers = seed_customers(db, tiers, sales.id)
        print("Seeding users…")
        users = seed_users(db, customers)
        print("Seeding quotes (this calculates risk / fulfillment)…")
        seed_quotes(db, customers, users, products)
        seed_notifications(db, users)
        seed_live_billing(db)
        db.commit()
        print("\nDealFlow360 seed complete.")
        print(f"Demo password for all users: {DEMO}")
        print("  sales@demo.com       SALES_REP")
        print("  manager@demo.com     SALES_MANAGER")
        print("  finance@demo.com     FINANCE")
        print("  ops@demo.com         OPERATIONS")
        print("  customer@acme.com    CUSTOMER (Acme)")
        print("  admin@demo.com       ADMIN")
        print("Hero deal: Q-2026-0042")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
