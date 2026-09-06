import json
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000/api"


def req(method, path, token=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = Request(BASE + path, data=data, headers=headers, method=method)
    with urlopen(r) as resp:
        return json.loads(resp.read().decode())


tok = req("POST", "/auth/login", body={"email": "sales@demo.com", "password": "Demo@123"})["data"]["access_token"]
quotes = req("GET", "/quotes?q=Q-2026-0042", tok)["data"]["items"][0]
qid = quotes["id"]
q = req("GET", f"/quotes/{qid}", tok)["data"]
print("status", q["status"], "risk", q.get("risk_score"), "margin", q.get("gross_margin_percent"), "health", q.get("deal_health_score"), "shipments", q.get("shipment_count"))
print("factors:")
for f in q.get("risk_factors") or []:
    print(" ", f["type"], f["severity"], f["message"][:100])
ff = req("POST", f"/quotes/{qid}/fulfillment/optimize", tok)["data"]
print("fulfill current", ff["current"]["shipments"], ff["current"]["shipping_cost"], "recommended", ff["recommended"]["shipments"], ff["recommended"]["shipping_cost"], "savings", ff["savings"])
sim = req("POST", f"/quotes/{qid}/simulate", tok, {"line_discounts": {}, "add_premium_support": True, "consolidate_warehouse": True})
print("sim", sim["success"], sim["data"]["deltas"])
dash = req("GET", "/dashboard/summary", tok)["data"]
print("dash pipeline", dash["pipeline"], "at_risk", dash["at_risk"], "pending", dash["pending_approvals"])
