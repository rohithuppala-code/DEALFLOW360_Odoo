import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8000/api"


def req(method, path, token=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(r) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw}


def login(email):
    st, body = req("POST", "/auth/login", body={"email": email, "password": "Demo@123"})
    assert st == 200, body
    return body["data"]["access_token"], body["data"]["user"]


def main():
    sales_tok, sales = login("sales@demo.com")
    print("LOGIN sales", sales["role"])
    st, dash = req("GET", "/dashboard/summary", sales_tok)
    print("DASH", st, {k: dash["data"][k] for k in ["pipeline", "at_risk", "pending_approvals", "active_deals", "mrr"]})

    st, quotes = req("GET", "/quotes?q=Q-2026-0042", sales_tok)
    items = quotes["data"]["items"]
    qid = items[0]["id"]
    print("QUOTE", items[0]["quote_number"], "id", qid, "status", items[0]["status"], "risk", items[0].get("risk_score"))

    st, q = req("GET", f"/quotes/{qid}", sales_tok)
    print("GET quote", st, "risk", q["data"].get("risk_score"), "health", q["data"].get("deal_health_score"))
    factors = q["data"].get("risk_factors") or []
    print("FACTORS", [(f["type"], round(f["severity"], 1), f["message"][:90]) for f in factors[:6]])
    lines = q["data"]["lines"]
    svc = next(l for l in lines if "Implementation" in (l.get("product") or {}).get("name", ""))
    print("SERVICE disc", svc["discount_percent"], "line", svc["id"])

    st, cop = req("GET", f"/quotes/{qid}/copilot", sales_tok)
    print("COPILOT", st, cop.get("data", {}).get("headline"), "actions", len((cop.get("data") or {}).get("actions") or []))

    st, sim = req(
        "POST",
        f"/quotes/{qid}/simulate",
        sales_tok,
        {"line_discounts": {str(svc["id"]): 14}, "add_premium_support": True, "consolidate_warehouse": True},
    )
    print("SIM", st, (sim.get("data") or {}).get("deltas") if st == 200 else sim)

    st, recs = req("GET", f"/quotes/{qid}/recommendations", sales_tok)
    print("RECS", st, [r.get("product_name") for r in recs.get("data") or []])
    if recs.get("data"):
        rid = recs["data"][0]["id"]
        st, _ = req("POST", f"/quotes/{qid}/recommendations/{rid}/apply", sales_tok)
        print("APPLY REC", st)

    st, ff = req("POST", f"/quotes/{qid}/fulfillment/optimize", sales_tok)
    cur = ((ff.get("data") or {}).get("current") or {}).get("shipments")
    rec = ((ff.get("data") or {}).get("recommended") or {}).get("shipments")
    print("FULFILL OPT", st, "from", cur, "to", rec, "savings", (ff.get("data") or {}).get("savings"))
    st, _ = req("POST", f"/quotes/{qid}/fulfillment/apply", sales_tok)
    print("FULFILL APPLY", st)

    st, sub = req("POST", f"/quotes/{qid}/submit", sales_tok)
    print("SUBMIT", st, (sub.get("data") or {}).get("status"), (sub.get("data") or {}).get("approval_status"), sub.get("error"))

    mgr_tok, _ = login("manager@demo.com")
    fin_tok, _ = login("finance@demo.com")

    def approve_open(token, label):
        st, inbox = req("GET", "/approvals", token)
        print(label, "INBOX", st, len(inbox.get("data") or []))
        for row in inbox.get("data") or []:
            if row.get("quote", {}).get("id") == qid:
                st, appr = req("POST", f"/approvals/{row['id']}/approve", token, {"comment": f"{label} approved"})
                print(label, "APPROVE", st, (appr.get("data") or {}).get("status"), appr.get("error"))
                return True
        return False

    approve_open(mgr_tok, "MGR")
    approve_open(fin_tok, "FIN")

    st, q = req("GET", f"/quotes/{qid}", sales_tok)
    print("AFTER APPROVAL", q["data"]["status"], q["data"]["approval_status"])
    st, sent = req("POST", f"/quotes/{qid}/send", sales_tok)
    print("SEND", st, sent.get("message") or sent.get("error"), (sent.get("data") or {}).get("status"))

    cust_tok, _ = login("customer@acme.com")
    st, cq = req("GET", f"/quotes/{qid}", cust_tok)
    print("CUSTOMER GET", st, "has cost", "cost_total" in (cq.get("data") or {}), "has risk", "risk_score" in (cq.get("data") or {}))
    svc_id = None
    for ln in (cq.get("data") or {}).get("lines") or []:
        if ln.get("product") and "Implementation" in ln["product"]["name"]:
            svc_id = ln["id"]
    st, neg = req(
        "POST",
        f"/quotes/{qid}/negotiation",
        cust_tok,
        {"request_type": "DISCOUNT", "line_id": svc_id, "requested_value": "20", "reason": "Need a better service rate"},
    )
    print("NEGOTIATE", st, ((neg.get("data") or {}).get("analysis") or {}).get("counteroffer", {}).get("headline") if st == 200 else neg)
    nid = ((neg.get("data") or {}).get("negotiation") or {}).get("id")
    print("NEG ID", nid)
    if nid:
        st, acc = req("POST", f"/negotiations/{nid}/accept", cust_tok)
        print("ACCEPT COUNTER", st, (acc.get("data") or {}).get("status") if st == 200 else acc.get("error"), (acc.get("data") or {}).get("approval_status"))

    st, q = req("GET", f"/quotes/{qid}", sales_tok)
    print("AFTER NEGO", q["data"]["status"], q["data"]["approval_status"], "risk", q["data"].get("risk_score"))

    approve_open(mgr_tok, "MGR2")
    approve_open(fin_tok, "FIN2")

    st, q = req("GET", f"/quotes/{qid}", sales_tok)
    print("PRE CONFIRM", q["data"]["status"], q["data"]["approval_status"])
    st, conf = req("POST", f"/quotes/{qid}/confirm", sales_tok)
    print("CONFIRM", st, (conf.get("data") or {}).get("order_number") if st == 200 else conf.get("error"))
    st, q = req("GET", f"/quotes/{qid}", sales_tok)
    print("FINAL", q["data"]["status"])
    st, dash2 = req("GET", "/dashboard/summary", sales_tok)
    print("DASH2", {k: dash2["data"][k] for k in ["pipeline", "confirmed_revenue", "mrr"]})
    print("DONE")


if __name__ == "__main__":
    main()
