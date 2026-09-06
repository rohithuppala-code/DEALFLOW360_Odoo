"""PostgreSQL-backed system settings used by engines (not hardcoded in UI)."""

from sqlalchemy.orm import Session

from app.models.intelligence import SystemSetting

DEFAULTS: dict[str, object] = {
    "billing.default_tax_percent": 18,
    "billing.proration": {"monthly_days": 30, "quarterly_days": 90, "yearly_days": 365},
    "billing.cancellation": {"credit_unused": True, "min_days": 0},
    "recommendations.min_margin_percent": 0,
    "approvals.risk_threshold": 70,
    "shipping_matrix": {
        "Ahmedabad|Ahmedabad": 80,
        "Mumbai|Mumbai": 80,
        "Bangalore|Bangalore": 80,
        "Ahmedabad|Mumbai": 250,
        "Mumbai|Ahmedabad": 250,
        "Ahmedabad|Bangalore": 450,
        "Bangalore|Ahmedabad": 450,
        "Mumbai|Bangalore": 400,
        "Bangalore|Mumbai": 400,
    },
    "shipping_default": 500,
}


def get_setting(db: Session | None, key: str, default=None):
    if db is None:
        return DEFAULTS.get(key) if default is None else default
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None or row.value_json is None:
        return DEFAULTS.get(key) if default is None else default
    val = row.value_json
    if isinstance(val, dict) and "value" in val and len(val) <= 2:
        return val.get("value")
    return val


def set_setting(db: Session, key: str, value, description: str | None = None) -> SystemSetting:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None:
        row = SystemSetting(key=key, value_json=value, description=description)
        db.add(row)
    else:
        row.value_json = value
        if description:
            row.description = description
    db.flush()
    return row


def negotiation_approval_plan(exceeds_discount: bool, blended_risk: float, threshold: float) -> dict:
    """Pure routing used by customer negotiation → approval."""
    risk_high = float(blended_risk) > float(threshold)
    if not exceeds_discount and not risk_high:
        return {"required": False, "roles": [], "risk_high": False}
    roles = ["SALES_MANAGER"]
    if risk_high:
        roles.append("FINANCE")
    return {"required": True, "roles": roles, "risk_high": risk_high}


def risk_threshold(db: Session | None) -> float:
    """Admin-configured blended-risk line. Above this, Finance is required after the manager."""
    raw = get_setting(db, "approvals.risk_threshold", 70)
    try:
        if isinstance(raw, dict):
            raw = raw.get("value", 70)
        return float(raw)
    except (TypeError, ValueError):
        return 70.0


def shipping_base(db: Session | None, from_city: str, to_city: str) -> float:
    matrix = get_setting(db, "shipping_matrix") or {}
    try:
        fallback = float(get_setting(db, "shipping_default", 500) or 500)
    except (TypeError, ValueError):
        fallback = 500.0
    if isinstance(matrix, dict):
        for key in (f"{from_city}|{to_city}", f"{from_city},{to_city}"):
            if key in matrix:
                return float(matrix[key])
        nested = matrix.get(from_city)
        if isinstance(nested, dict) and to_city in nested:
            return float(nested[to_city])
    return fallback
