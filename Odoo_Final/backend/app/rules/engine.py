from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.intelligence import RuleDefinition
from app.utils.money import D


OPS = {
    "=": lambda a, b: str(a) == str(b),
    "!=": lambda a, b: str(a) != str(b),
    ">": lambda a, b: D(a) > D(b),
    "<": lambda a, b: D(a) < D(b),
    ">=": lambda a, b: D(a) >= D(b),
    "<=": lambda a, b: D(a) <= D(b),
    "IN": lambda a, b: str(a) in [x.strip() for x in str(b).split(",")],
    "NOT_IN": lambda a, b: str(a) not in [x.strip() for x in str(b).split(",")],
}


def evaluate_rules(db: Session, context: dict) -> list[dict]:
    """Evaluate active configurable rules against a quote context."""
    rules = db.query(RuleDefinition).filter(RuleDefinition.is_active.is_(True)).order_by(RuleDefinition.priority).all()
    fired: list[dict] = []
    for rule in rules:
        if _matches(rule, context):
            fired.append(
                {
                    "id": rule.id,
                    "name": rule.name,
                    "rule_type": rule.rule_type,
                    "actions": [
                        {"type": a.action_type, "value": a.action_value} for a in rule.actions
                    ],
                }
            )
    return fired


def _matches(rule: RuleDefinition, context: dict) -> bool:
    if not rule.conditions:
        return False
    result = True
    first = True
    for cond in rule.conditions:
        op = OPS.get(cond.operator)
        if not op:
            continue
        field_val = _resolve(context, cond.field)
        try:
            current = op(field_val, cond.value)
        except Exception:
            current = False
        if first:
            result = current
            first = False
        elif (cond.logical_operator or "AND").upper() == "OR":
            result = result or current
        else:
            result = result and current
    return result


def _resolve(context: dict, field: str):
    cur = context
    for part in field.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    if isinstance(cur, Decimal):
        return cur
    return cur
