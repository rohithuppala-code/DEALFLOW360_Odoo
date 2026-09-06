from fastapi import APIRouter, Query
from sqlalchemy import or_

from app.core.dependencies import CurrentUser, DbSession, require_roles
from app.core.exceptions import AppError
from app.core.security import hash_password
from datetime import date

from app.models.audit import AuditLog
from app.models.catalog import PriceList, PriceListItem, Product, ProductCategory, ProductVariant
from app.models.customer import Customer, CustomerTier
from app.models.enums import (
    BillingInterval,
    CategoryKind,
    ConditionType,
    ProductType,
    RecommendationType,
    RuleActionType,
    RuleType,
    Severity,
    UserRole,
)
from app.models.fulfillment import Inventory, Warehouse
from app.models.governance import ApprovalChain, ApprovalRule, DiscountRule
from app.models.intelligence import RecommendationRule, RuleAction, RuleCondition, RuleDefinition, SystemSetting
from app.models.billing import SubscriptionPlan
from app.models.user import User
from app.schemas.common import (
    ApprovalRuleWriteIn,
    CategoryIn,
    DiscountRuleIn,
    InventoryIn,
    PlanIn,
    PriceListIn,
    PriceListItemIn,
    ProductIn,
    RecRuleIn,
    RuleDefIn,
    TierIn,
    UserIn,
    VariantIn,
    WarehouseIn,
)
from app.events.bus import audit
from app.services.access import ensure_customer_for_user
from app.services.serialize import product_out, user_public
from app.services.settings import set_setting
from app.utils.pagination import paginate
from app.utils.response import ok, page

router = APIRouter()


def _admin(user: CurrentUser):
    if user.role != UserRole.ADMIN:
        raise AppError("FORBIDDEN", "Admin only.", 403)


@router.get("/users")
def users(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
    q: str | None = None,
):
    _admin(user)
    query = db.query(User).order_by(User.id)
    if q:
        query = query.filter(or_(User.name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page([user_public(u) for u in items], total, p, ps)
    return ok([user_public(u) for u in query.all()])


@router.post("/users")
def create_user(payload: UserIn, db: DbSession, user: CurrentUser):
    _admin(user)
    role = UserRole(payload.role)
    u = User(
        name=payload.name,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password or "Demo@123"),
        role=role,
        is_active=payload.is_active,
        customer_id=payload.customer_id,
    )
    db.add(u)
    db.flush()
    if role == UserRole.CUSTOMER:
        ensure_customer_for_user(db, u)
    db.commit()
    db.refresh(u)
    return ok(user_public(u), "User created")


@router.put("/users/{user_id}")
def update_user(user_id: int, payload: UserIn, db: DbSession, user: CurrentUser):
    _admin(user)
    u = db.get(User, user_id)
    if not u:
        raise AppError("NOT_FOUND", "User not found.", 404)
    u.name = payload.name
    u.email = payload.email.lower()
    u.role = UserRole(payload.role)
    u.is_active = payload.is_active
    u.customer_id = payload.customer_id
    if u.role == UserRole.CUSTOMER:
        ensure_customer_for_user(db, u)
    if payload.password:
        u.password_hash = hash_password(payload.password)
    db.commit()
    return ok(user_public(u))


@router.get("/discount-rules")
def discount_rules(db: DbSession, user: CurrentUser):
    _admin(user)
    rows = db.query(DiscountRule).all()
    return ok(
        [
            {
                "id": r.id,
                "name": r.name,
                "customer_tier_id": r.customer_tier_id,
                "tier": r.tier.name if r.tier else None,
                "category_id": r.category_id,
                "category": r.category.name if r.category else None,
                "product_id": r.product_id,
                "max_discount_percent": float(r.max_discount_percent),
                "severity": r.severity.value,
                "requires_approval": r.requires_approval,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    )


@router.post("/discount-rules")
def create_discount_rule(payload: DiscountRuleIn, db: DbSession, user: CurrentUser):
    _admin(user)
    r = DiscountRule(
        name=payload.name,
        customer_tier_id=payload.customer_tier_id,
        category_id=payload.category_id,
        product_id=payload.product_id,
        max_discount_percent=payload.max_discount_percent,
        severity=Severity(payload.severity),
        requires_approval=payload.requires_approval,
        is_active=payload.is_active,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return ok({"id": r.id}, "Rule saved")


@router.put("/discount-rules/{rule_id}")
def update_discount_rule(rule_id: int, payload: DiscountRuleIn, db: DbSession, user: CurrentUser):
    _admin(user)
    r = db.get(DiscountRule, rule_id)
    if not r:
        raise AppError("NOT_FOUND", "Rule not found.", 404)
    r.name = payload.name
    r.customer_tier_id = payload.customer_tier_id
    r.category_id = payload.category_id
    r.product_id = payload.product_id
    r.max_discount_percent = payload.max_discount_percent
    r.severity = Severity(payload.severity)
    r.requires_approval = payload.requires_approval
    r.is_active = payload.is_active
    db.commit()
    return ok({"id": r.id})


@router.get("/rules")
def business_rules(db: DbSession, user: CurrentUser):
    _admin(user)
    rows = db.query(RuleDefinition).order_by(RuleDefinition.priority).all()
    return ok(
        [
            {
                "id": r.id,
                "name": r.name,
                "description": r.description,
                "rule_type": r.rule_type.value,
                "is_active": r.is_active,
                "priority": r.priority,
                "conditions": [
                    {"id": c.id, "field": c.field, "operator": c.operator, "value": c.value, "logical_operator": c.logical_operator}
                    for c in r.conditions
                ],
                "actions": [{"id": a.id, "action_type": a.action_type.value, "action_value": a.action_value} for a in r.actions],
            }
            for r in rows
        ]
    )


@router.post("/rules")
def create_rule(payload: RuleDefIn, db: DbSession, user: CurrentUser):
    _admin(user)
    r = RuleDefinition(
        name=payload.name,
        description=payload.description,
        rule_type=RuleType(payload.rule_type),
        is_active=payload.is_active,
        priority=payload.priority,
    )
    db.add(r)
    db.flush()
    for c in payload.conditions:
        db.add(
            RuleCondition(
                rule_id=r.id,
                field=c["field"],
                operator=c["operator"],
                value=str(c["value"]),
                logical_operator=c.get("logical_operator") or "AND",
            )
        )
    for a in payload.actions:
        db.add(RuleAction(rule_id=r.id, action_type=RuleActionType(a["action_type"]), action_value=str(a["action_value"])))
    db.commit()
    return ok({"id": r.id}, "Rule saved")


@router.get("/warehouses")
def warehouses(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
    q: str | None = None,
):
    if user.role not in (UserRole.ADMIN, UserRole.OPERATIONS):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    query = db.query(Warehouse).order_by(Warehouse.id)
    if q:
        query = query.filter(or_(Warehouse.name.ilike(f"%{q}%"), Warehouse.code.ilike(f"%{q}%"), Warehouse.city.ilike(f"%{q}%")))
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": w.id,
                    "name": w.name,
                    "code": w.code,
                    "city": w.city,
                    "address": w.address,
                    "shipping_zone": w.shipping_zone,
                    "handling_cost": float(w.handling_cost),
                    "reliability_score": float(w.reliability_score),
                    "avg_lead_days": w.avg_lead_days,
                }
                for w in items
            ],
            total,
            p,
            ps,
        )
    rows = query.all()
    return ok(
        [
            {
                "id": w.id,
                "name": w.name,
                "code": w.code,
                "city": w.city,
                "address": w.address,
                "shipping_zone": w.shipping_zone,
                "handling_cost": float(w.handling_cost),
                "reliability_score": float(w.reliability_score),
                "avg_lead_days": w.avg_lead_days,
            }
            for w in rows
        ]
    )


@router.get("/inventory")
def inventory(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    if user.role not in (UserRole.ADMIN, UserRole.OPERATIONS, UserRole.SALES_MANAGER):
        raise AppError("FORBIDDEN", "Not allowed.", 403)
    query = db.query(Inventory).order_by(Inventory.id)
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": r.id,
                    "warehouse": r.warehouse.name if r.warehouse else None,
                    "warehouse_id": r.warehouse_id,
                    "product": r.product.name if r.product else None,
                    "product_id": r.product_id,
                    "available_qty": r.available_qty,
                    "reserved_qty": r.reserved_qty,
                    "free": r.available_qty - r.reserved_qty,
                    "reorder_level": r.reorder_level,
                    "expected_replenishment": str(r.expected_replenishment) if r.expected_replenishment else None,
                }
                for r in items
            ],
            total,
            p,
            ps,
        )
    rows = query.all()
    return ok(
        [
            {
                "id": r.id,
                "warehouse": r.warehouse.name if r.warehouse else None,
                "warehouse_id": r.warehouse_id,
                "product": r.product.name if r.product else None,
                "product_id": r.product_id,
                "available_qty": r.available_qty,
                "reserved_qty": r.reserved_qty,
                "free": r.available_qty - r.reserved_qty,
                "reorder_level": r.reorder_level,
                "expected_replenishment": str(r.expected_replenishment) if r.expected_replenishment else None,
            }
            for r in rows
        ]
    )


@router.get("/settings")
def settings(db: DbSession, user: CurrentUser):
    _admin(user)
    rows = db.query(SystemSetting).all()
    return ok([{"key": r.key, "value": r.value_json, "description": r.description} for r in rows])


@router.put("/settings/{key}")
def update_setting(key: str, payload: dict, db: DbSession, user: CurrentUser):
    _admin(user)
    value = payload.get("value") if "value" in payload else payload
    row = set_setting(db, key, value, payload.get("description"))
    audit(db, user.id, "SETTING_UPDATE", "setting", None, new_value={"key": key, "value": value})
    db.commit()
    return ok({"key": key, "value": row.value_json})


@router.get("/price-lists")
def price_lists(db: DbSession, user: CurrentUser):
    _admin(user)
    rows = db.query(PriceList).all()
    return ok(
        [
            {
                "id": p.id,
                "name": p.name,
                "currency": p.currency,
                "customer_tier_id": p.customer_tier_id,
                "is_active": p.is_active,
                "items": [
                    {
                        "id": i.id,
                        "product_id": i.product_id,
                        "product": i.product.name if i.product else None,
                        "unit_price": float(i.unit_price),
                        "min_quantity": i.min_quantity,
                    }
                    for i in p.items
                ],
            }
            for p in rows
        ]
    )


@router.get("/subscription-plans")
def plans(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    query = db.query(SubscriptionPlan).order_by(SubscriptionPlan.name)
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "billing_interval": p.billing_interval.value,
                    "price": float(p.price),
                    "setup_fee": float(p.setup_fee),
                    "trial_days": p.trial_days,
                    "cost": float(p.cost or 0),
                }
                for p in items
            ],
            total,
            p,
            ps,
        )
    rows = query.all()
    return ok(
        [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "billing_interval": p.billing_interval.value,
                "price": float(p.price),
                "setup_fee": float(p.setup_fee),
                "trial_days": p.trial_days,
                "cost": float(p.cost or 0),
            }
            for p in rows
        ]
    )


@router.get("/approval-chains")
def chains(db: DbSession, user: CurrentUser):
    _admin(user)
    rows = db.query(ApprovalChain).all()
    return ok(
        [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "is_active": c.is_active,
                "rules": [
                    {
                        "id": r.id,
                        "condition_type": r.condition_type.value,
                        "condition_value": r.condition_value,
                        "required_role": r.required_role.value,
                        "sequence": r.sequence,
                    }
                    for r in c.rules
                ],
            }
            for c in rows
        ]
    )


@router.post("/approval-chains/{chain_id}/rules")
def add_approval_rule(chain_id: int, payload: ApprovalRuleWriteIn, db: DbSession, user: CurrentUser):
    _admin(user)
    chain = db.get(ApprovalChain, chain_id)
    if not chain:
        raise AppError("NOT_FOUND", "Approval chain not found.", 404)
    r = ApprovalRule(
        approval_chain_id=chain.id,
        condition_type=ConditionType(payload.condition_type),
        condition_value=str(payload.condition_value),
        required_role=UserRole(payload.required_role),
        sequence=payload.sequence,
    )
    db.add(r)
    audit(db, user.id, "APPROVAL_RULE_CREATE", "approval_rule", None, new_value=payload.model_dump())
    db.commit()
    db.refresh(r)
    return ok({"id": r.id}, "Approval rule saved")


@router.put("/approval-chains/{chain_id}/rules/{rule_id}")
def update_approval_rule(chain_id: int, rule_id: int, payload: ApprovalRuleWriteIn, db: DbSession, user: CurrentUser):
    _admin(user)
    r = db.get(ApprovalRule, rule_id)
    if not r or r.approval_chain_id != chain_id:
        raise AppError("NOT_FOUND", "Rule not found.", 404)
    r.condition_type = ConditionType(payload.condition_type)
    r.condition_value = str(payload.condition_value)
    r.required_role = UserRole(payload.required_role)
    r.sequence = payload.sequence
    audit(db, user.id, "APPROVAL_RULE_UPDATE", "approval_rule", r.id, new_value=payload.model_dump())
    db.commit()
    return ok({"id": r.id})


@router.delete("/approval-chains/{chain_id}/rules/{rule_id}")
def delete_approval_rule(chain_id: int, rule_id: int, db: DbSession, user: CurrentUser):
    _admin(user)
    r = db.get(ApprovalRule, rule_id)
    if not r or r.approval_chain_id != chain_id:
        raise AppError("NOT_FOUND", "Rule not found.", 404)
    db.delete(r)
    audit(db, user.id, "APPROVAL_RULE_DELETE", "approval_rule", rule_id)
    db.commit()
    return ok(None, "Rule removed")


@router.get("/products")
def admin_products(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
    q: str | None = None,
):
    _admin(user)
    from sqlalchemy.orm import joinedload, selectinload

    query = db.query(Product).options(joinedload(Product.category), selectinload(Product.variants)).order_by(Product.name)
    if q:
        query = query.filter(or_(Product.name.ilike(f"%{q}%"), Product.sku.ilike(f"%{q}%")))
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page([product_out(x) for x in items], total, p, ps)
    rows = query.all()
    return ok([product_out(p) for p in rows])


@router.post("/products")
def create_product(payload: ProductIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = Product(
        sku=payload.sku.strip().upper(),
        name=payload.name.strip(),
        description=payload.description,
        category_id=payload.category_id,
        product_type=ProductType(payload.product_type),
        base_price=payload.base_price,
        cost_price=payload.cost_price,
        weight=payload.weight,
        is_active=payload.is_active,
        subscription_plan_id=payload.subscription_plan_id,
        perceived_value=payload.perceived_value,
    )
    db.add(p)
    db.flush()
    audit(db, user.id, "PRODUCT_CREATE", "product", p.id, new_value={"sku": p.sku})
    db.commit()
    db.refresh(p)
    return ok(product_out(p), "Product created")


@router.put("/products/{product_id}")
def update_product(product_id: int, payload: ProductIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = db.get(Product, product_id)
    if not p:
        raise AppError("NOT_FOUND", "Product not found.", 404)
    p.sku = payload.sku.strip().upper()
    p.name = payload.name.strip()
    p.description = payload.description
    p.category_id = payload.category_id
    p.product_type = ProductType(payload.product_type)
    p.base_price = payload.base_price
    p.cost_price = payload.cost_price
    p.weight = payload.weight
    p.is_active = payload.is_active
    p.subscription_plan_id = payload.subscription_plan_id
    p.perceived_value = payload.perceived_value
    audit(db, user.id, "PRODUCT_UPDATE", "product", p.id, new_value={"sku": p.sku, "active": p.is_active})
    db.commit()
    db.refresh(p)
    return ok(product_out(p), "Product saved")


@router.post("/products/{product_id}/variants")
def add_variant(product_id: int, payload: VariantIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = db.get(Product, product_id)
    if not p:
        raise AppError("NOT_FOUND", "Product not found.", 404)
    v = ProductVariant(
        product_id=p.id,
        sku=payload.sku.strip().upper(),
        name=payload.name.strip(),
        price_adjustment=payload.price_adjustment,
        cost_adjustment=payload.cost_adjustment,
        is_active=payload.is_active,
        attributes_json=payload.attributes_json,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return ok({"id": v.id}, "Variant saved")


@router.put("/products/{product_id}/variants/{variant_id}")
def update_variant(product_id: int, variant_id: int, payload: VariantIn, db: DbSession, user: CurrentUser):
    _admin(user)
    v = db.get(ProductVariant, variant_id)
    if not v or v.product_id != product_id:
        raise AppError("NOT_FOUND", "Variant not found.", 404)
    v.sku = payload.sku.strip().upper()
    v.name = payload.name.strip()
    v.price_adjustment = payload.price_adjustment
    v.cost_adjustment = payload.cost_adjustment
    v.is_active = payload.is_active
    v.attributes_json = payload.attributes_json
    db.commit()
    return ok({"id": v.id})


@router.post("/categories")
def create_category(payload: CategoryIn, db: DbSession, user: CurrentUser):
    _admin(user)
    c = ProductCategory(name=payload.name.strip(), kind=CategoryKind(payload.kind), description=payload.description)
    db.add(c)
    db.commit()
    db.refresh(c)
    return ok({"id": c.id, "name": c.name, "kind": c.kind.value}, "Category created")


@router.put("/categories/{category_id}")
def update_category(category_id: int, payload: CategoryIn, db: DbSession, user: CurrentUser):
    _admin(user)
    c = db.get(ProductCategory, category_id)
    if not c:
        raise AppError("NOT_FOUND", "Category not found.", 404)
    c.name = payload.name.strip()
    c.kind = CategoryKind(payload.kind)
    c.description = payload.description
    db.commit()
    return ok({"id": c.id})


@router.get("/tiers")
def list_tiers(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    _admin(user)
    query = db.query(CustomerTier).order_by(CustomerTier.id)
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "default_discount_limit": float(t.default_discount_limit),
                    "risk_multiplier": float(t.risk_multiplier),
                }
                for t in items
            ],
            total,
            p,
            ps,
        )
    rows = query.all()
    return ok(
        [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "default_discount_limit": float(t.default_discount_limit),
                "risk_multiplier": float(t.risk_multiplier),
            }
            for t in rows
        ]
    )


@router.post("/tiers")
def create_tier(payload: TierIn, db: DbSession, user: CurrentUser):
    _admin(user)
    t = CustomerTier(
        name=payload.name.strip(),
        description=payload.description,
        default_discount_limit=payload.default_discount_limit,
        risk_multiplier=payload.risk_multiplier,
    )
    db.add(t)
    audit(db, user.id, "TIER_CREATE", "customer_tier", None, new_value=payload.model_dump())
    db.commit()
    db.refresh(t)
    return ok({"id": t.id}, "Tier saved")


@router.put("/tiers/{tier_id}")
def update_tier(tier_id: int, payload: TierIn, db: DbSession, user: CurrentUser):
    _admin(user)
    t = db.get(CustomerTier, tier_id)
    if not t:
        raise AppError("NOT_FOUND", "Tier not found.", 404)
    t.name = payload.name.strip()
    t.description = payload.description
    t.default_discount_limit = payload.default_discount_limit
    t.risk_multiplier = payload.risk_multiplier
    audit(db, user.id, "TIER_UPDATE", "customer_tier", t.id, new_value=payload.model_dump())
    db.commit()
    return ok({"id": t.id})


@router.post("/price-lists")
def create_price_list(payload: PriceListIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = PriceList(name=payload.name, currency=payload.currency, customer_tier_id=payload.customer_tier_id, is_active=payload.is_active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return ok({"id": p.id}, "Price list created")


@router.put("/price-lists/{list_id}")
def update_price_list(list_id: int, payload: PriceListIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = db.get(PriceList, list_id)
    if not p:
        raise AppError("NOT_FOUND", "Price list not found.", 404)
    p.name = payload.name
    p.currency = payload.currency
    p.customer_tier_id = payload.customer_tier_id
    p.is_active = payload.is_active
    db.commit()
    return ok({"id": p.id})


@router.post("/price-lists/{list_id}/items")
def add_price_item(list_id: int, payload: PriceListItemIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = db.get(PriceList, list_id)
    if not p:
        raise AppError("NOT_FOUND", "Price list not found.", 404)
    item = PriceListItem(
        price_list_id=p.id,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        unit_price=payload.unit_price,
        min_quantity=payload.min_quantity,
        max_quantity=payload.max_quantity,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ok({"id": item.id}, "Price saved")


@router.put("/price-lists/{list_id}/items/{item_id}")
def update_price_item(list_id: int, item_id: int, payload: PriceListItemIn, db: DbSession, user: CurrentUser):
    _admin(user)
    item = db.get(PriceListItem, item_id)
    if not item or item.price_list_id != list_id:
        raise AppError("NOT_FOUND", "Item not found.", 404)
    item.product_id = payload.product_id
    item.variant_id = payload.variant_id
    item.unit_price = payload.unit_price
    item.min_quantity = payload.min_quantity
    item.max_quantity = payload.max_quantity
    db.commit()
    return ok({"id": item.id})


@router.post("/warehouses")
def create_warehouse(payload: WarehouseIn, db: DbSession, user: CurrentUser):
    _admin(user)
    w = Warehouse(
        name=payload.name,
        code=payload.code.strip().upper(),
        city=payload.city,
        address=payload.address,
        shipping_zone=payload.shipping_zone,
        handling_cost=payload.handling_cost,
        reliability_score=payload.reliability_score,
        avg_lead_days=payload.avg_lead_days,
    )
    db.add(w)
    audit(db, user.id, "WAREHOUSE_CREATE", "warehouse", None, new_value={"code": w.code})
    db.commit()
    db.refresh(w)
    return ok({"id": w.id}, "Warehouse created")


@router.put("/warehouses/{warehouse_id}")
def update_warehouse(warehouse_id: int, payload: WarehouseIn, db: DbSession, user: CurrentUser):
    _admin(user)
    w = db.get(Warehouse, warehouse_id)
    if not w:
        raise AppError("NOT_FOUND", "Warehouse not found.", 404)
    w.name = payload.name
    w.code = payload.code.strip().upper()
    w.city = payload.city
    w.address = payload.address
    w.shipping_zone = payload.shipping_zone
    w.handling_cost = payload.handling_cost
    w.reliability_score = payload.reliability_score
    w.avg_lead_days = payload.avg_lead_days
    audit(db, user.id, "WAREHOUSE_UPDATE", "warehouse", w.id, new_value={"handling_cost": payload.handling_cost})
    db.commit()
    return ok({"id": w.id})


@router.post("/inventory")
def upsert_inventory(payload: InventoryIn, db: DbSession, user: CurrentUser):
    _admin(user)
    row = (
        db.query(Inventory)
        .filter(Inventory.warehouse_id == payload.warehouse_id, Inventory.product_id == payload.product_id, Inventory.variant_id.is_(None))
        .first()
    )
    replen = date.fromisoformat(payload.expected_replenishment) if payload.expected_replenishment else None
    if row:
        row.available_qty = payload.available_qty
        row.reserved_qty = payload.reserved_qty
        row.reorder_level = payload.reorder_level
        row.expected_replenishment = replen
    else:
        row = Inventory(
            warehouse_id=payload.warehouse_id,
            product_id=payload.product_id,
            available_qty=payload.available_qty,
            reserved_qty=payload.reserved_qty,
            reorder_level=payload.reorder_level,
            expected_replenishment=replen,
        )
        db.add(row)
    db.flush()
    audit(db, user.id, "INVENTORY_UPSERT", "inventory", row.id, new_value=payload.model_dump())
    db.commit()
    return ok({"id": row.id}, "Inventory saved")


@router.post("/subscription-plans")
def create_plan(payload: PlanIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = SubscriptionPlan(
        name=payload.name,
        description=payload.description,
        billing_interval=BillingInterval(payload.billing_interval),
        price=payload.price,
        setup_fee=payload.setup_fee,
        trial_days=payload.trial_days,
        cost=payload.cost,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return ok({"id": p.id}, "Plan created")


@router.put("/subscription-plans/{plan_id}")
def update_plan(plan_id: int, payload: PlanIn, db: DbSession, user: CurrentUser):
    _admin(user)
    p = db.get(SubscriptionPlan, plan_id)
    if not p:
        raise AppError("NOT_FOUND", "Plan not found.", 404)
    p.name = payload.name
    p.description = payload.description
    p.billing_interval = BillingInterval(payload.billing_interval)
    p.price = payload.price
    p.setup_fee = payload.setup_fee
    p.trial_days = payload.trial_days
    p.cost = payload.cost
    db.commit()
    return ok({"id": p.id})


@router.get("/recommendations")
def list_recs(db: DbSession, user: CurrentUser):
    _admin(user)
    rows = db.query(RecommendationRule).order_by(RecommendationRule.priority.desc()).all()
    return ok(
        [
            {
                "id": r.id,
                "product_id": r.product_id,
                "product": r.product.name if r.product else None,
                "recommended_product_id": r.recommended_product_id,
                "recommended": r.recommended_product.name if r.recommended_product else None,
                "recommendation_type": r.recommendation_type.value,
                "reason": r.reason,
                "priority": r.priority,
                "confidence": r.confidence,
                "is_active": r.is_active,
            }
            for r in rows
        ]
    )


@router.post("/recommendations")
def create_rec(payload: RecRuleIn, db: DbSession, user: CurrentUser):
    _admin(user)
    r = RecommendationRule(
        product_id=payload.product_id,
        recommended_product_id=payload.recommended_product_id,
        recommendation_type=RecommendationType(payload.recommendation_type),
        reason=payload.reason,
        priority=payload.priority,
        confidence=payload.confidence,
        is_active=payload.is_active,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return ok({"id": r.id}, "Recommendation saved")


@router.put("/recommendations/{rule_id}")
def update_rec(rule_id: int, payload: RecRuleIn, db: DbSession, user: CurrentUser):
    _admin(user)
    r = db.get(RecommendationRule, rule_id)
    if not r:
        raise AppError("NOT_FOUND", "Rule not found.", 404)
    r.product_id = payload.product_id
    r.recommended_product_id = payload.recommended_product_id
    r.recommendation_type = RecommendationType(payload.recommendation_type)
    r.reason = payload.reason
    r.priority = payload.priority
    r.confidence = payload.confidence
    r.is_active = payload.is_active
    db.commit()
    return ok({"id": r.id})


@router.get("/audit")
def audit_log(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
    limit: int = 80,
):
    _admin(user)
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": r.id,
                    "action": r.action,
                    "entity_type": r.entity_type,
                    "entity_id": r.entity_id,
                    "user": r.user.name if r.user else None,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "new_value": r.new_value_json,
                }
                for r in items
            ],
            total,
            p,
            ps,
        )
    rows = query.limit(min(limit, 200)).all()
    return ok(
        [
            {
                "id": r.id,
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "user": r.user.name if r.user else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "new_value": r.new_value_json,
            }
            for r in rows
        ]
    )


@router.get("/customers")
def admin_customers(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
    q: str | None = None,
):
    _admin(user)
    from app.services.access import reconcile_all_customer_users
    from app.services.serialize import customer_out

    reconcile_all_customer_users(db)
    query = db.query(Customer).order_by(Customer.name)
    if q:
        like = f"%{q}%"
        query = query.filter(Customer.name.ilike(like) | Customer.code.ilike(like) | Customer.email.ilike(like))
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page([customer_out(c) for c in items], total, p, ps)
    rows = query.all()
    return ok([customer_out(c) for c in rows])

