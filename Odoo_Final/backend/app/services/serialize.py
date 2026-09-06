from decimal import Decimal

from app.core.permissions import can_see_internal, is_customer
from app.models.quote import Quote
from app.models.user import User


def dec(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def user_public(u: User) -> dict:
    cname = None
    if getattr(u, "customer", None):
        cname = u.customer.name
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role.value,
        "is_active": u.is_active,
        "customer_id": u.customer_id,
        "customer_name": cname,
    }


def customer_out(c) -> dict:
    has_portal = False
    if c is not None and "portal_users" in c.__dict__:
        has_portal = any(getattr(u, "is_active", True) for u in (c.portal_users or []))
    return {
        "id": c.id,
        "name": c.name,
        "code": c.code,
        "email": c.email,
        "phone": c.phone,
        "industry": c.industry,
        "tier": {"id": c.tier.id, "name": c.tier.name, "default_discount_limit": float(c.tier.default_discount_limit)}
        if c.tier
        else None,
        "customer_tier_id": c.customer_tier_id,
        "credit_limit": float(c.credit_limit or 0),
        "payment_terms": c.payment_terms,
        "status": c.status.value if c.status else None,
        "city": c.city,
        "sales_rep_id": c.sales_rep_id,
        "has_portal": has_portal,
    }


def product_out(p) -> dict:
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "description": p.description,
        "product_type": p.product_type.value,
        "base_price": float(p.base_price),
        "cost_price": float(p.cost_price),
        "weight": float(p.weight or 0),
        "is_active": p.is_active,
        "category": {"id": p.category.id, "name": p.category.name, "kind": p.category.kind.value} if p.category else None,
        "subscription_plan_id": p.subscription_plan_id,
        "variants": [
            {
                "id": v.id,
                "sku": v.sku,
                "name": v.name,
                "price_adjustment": float(v.price_adjustment),
                "is_active": v.is_active,
            }
            for v in (p.variants or [])
        ],
    }


def quote_line_out(ln, viewer: User | None) -> dict:
    hide = viewer is not None and is_customer(viewer)
    data = {
        "id": ln.id,
        "product_id": ln.product_id,
        "variant_id": ln.variant_id,
        "description": ln.description,
        "quantity": ln.quantity,
        "unit_price": float(ln.unit_price),
        "discount_percent": float(ln.discount_percent),
        "discount_amount": float(ln.discount_amount),
        "net_amount": float(ln.net_amount),
        "warehouse_id": ln.warehouse_id,
        "delivery_date": str(ln.delivery_date) if ln.delivery_date else None,
        "is_freebie": ln.is_freebie,
        "product": {
            "id": ln.product.id,
            "name": ln.product.name,
            "sku": ln.product.sku,
            "product_type": ln.product.product_type.value,
            "category": ln.product.category.name if ln.product.category else None,
            "category_id": ln.product.category_id,
        }
        if ln.product
        else None,
    }
    if not hide:
        data.update(
            {
                "unit_cost": float(ln.unit_cost),
                "total_cost": float(ln.total_cost),
                "gross_profit": float(ln.gross_profit),
                "margin_percent": float(ln.margin_percent),
            }
        )
    return data


def quote_out(q: Quote, viewer: User | None, extra: dict | None = None, compact: bool = False) -> dict:
    from app.services.workflow import build_workflow

    hide = viewer is not None and is_customer(viewer)
    data = {
        "id": q.id,
        "quote_number": q.quote_number,
        "customer_id": q.customer_id,
        "title": q.title,
        "status": q.status.value,
        "currency": q.currency,
        "subtotal": float(q.subtotal),
        "discount_total": float(q.discount_total),
        "tax_total": float(q.tax_total),
        "shipping_total": float(q.shipping_total),
        "total": float(q.total),
        "approval_status": q.approval_status.value,
        "negotiation_status": q.negotiation_status.value,
        "payment_terms": q.payment_terms,
        "notes": None if hide else q.notes,
        "expires_at": str(q.expires_at) if q.expires_at else None,
        "promised_delivery_date": str(q.promised_delivery_date) if q.promised_delivery_date else None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        "sent_to_customer_at": q.sent_to_customer_at.isoformat() if q.sent_to_customer_at else None,
        "customer": customer_out(q.customer) if q.customer else None,
        "sales_rep": {"id": q.sales_rep.id, "name": q.sales_rep.name} if q.sales_rep and not hide else None,
        "lines": [] if compact else [quote_line_out(ln, viewer) for ln in q.lines],
        "shipment_count": q.shipment_count,
    }
    if not hide:
        data.update(
            {
                "cost_total": float(q.cost_total),
                "gross_profit": float(q.gross_profit),
                "gross_margin_percent": float(q.gross_margin_percent),
                "risk_score": float(q.risk_score),
                "deal_health_score": float(q.deal_health_score),
                "delivery_risk_score": float(q.delivery_risk_score or 0),
                "risk_factors": []
                if compact
                else [
                    {
                        "id": f.id,
                        "type": f.factor_type,
                        "severity": float(f.severity),
                        "message": f.message,
                        "metadata": f.metadata_json,
                    }
                    for f in (q.risk_factors or [])
                ],
            }
        )
    if extra:
        if hide:
            extra = {k: v for k, v in extra.items() if k in {"billing", "negotiation", "timeline_public"}}
        data.update(extra)
    if not hide:
        intel = (extra or {}).get("intelligence") if extra else None
        data["workflow"] = build_workflow(q, intel if isinstance(intel, dict) else None, viewer=viewer)
        pending_app = next(
            (r for r in getattr(q, "approval_requests", []) if getattr(r.status, "value", str(r.status)) == "PENDING"),
            None,
        )
        if pending_app:
            from app.api.approvals import _can_act
            data["current_approval"] = {
                "id": pending_app.id,
                "status": getattr(pending_app.status, "value", str(pending_app.status)),
                "reason": pending_app.reason,
                "risk_score": float(pending_app.risk_score or 0),
                "can_act": _can_act(viewer, pending_app) if viewer else False,
                "steps": [
                    {
                        "id": s.id,
                        "role": getattr(s.role, "value", str(s.role)),
                        "sequence": s.sequence,
                        "status": getattr(s.status, "value", str(s.status)),
                        "comment": s.comment,
                    }
                    for s in getattr(pending_app, "steps", [])
                ],
            }
        else:
            data["current_approval"] = None
    return data
