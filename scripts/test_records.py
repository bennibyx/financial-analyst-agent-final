import requests

BASE = "http://localhost:8000"
fails = 0


def check(label, ok, detail=""):
    global fails
    fails += 0 if ok else 1
    print(("PASS " if ok else "FAIL ") + label + (f"  ({detail})" if detail and not ok else ""))


def get(path, **params):
    return requests.get(f"{BASE}{path}", params=params, timeout=30)


c = get("/companies").json()["items"]
check("companies: NVDA with 3 periods", len(c) == 1 and c[0]["periods"] == ["Q4 FY26", "Q1 FY27", "Q2 FY27"], c)

m = get("/metrics", metric="revenue").json()["items"]
check("metrics: revenue in 3 periods, chronological", [i["period"] for i in m] == ["Q4 FY26", "Q1 FY27", "Q2 FY27"], m)
check("metrics: all revenue in USD_million", all(i["unit"] == "USD_million" for i in m))

m = get("/metrics", metric="free_cash_flow", period="Q2 fiscal 2027").json()["items"]
check("metrics: period spelling normalised + conflict flagged",
      len(m) == 1 and m[0]["conflict"] and len(m[0]["alternatives"]) >= 1, m)

m = get("/metrics", metric="gross_margin_non_gaap", period="Q2 FY27").json()["items"]
check("metrics: metric alias gross_margin_non_gaap", len(m) == 1 and m[0]["basis"] == "non-GAAP", m)

m = get("/metrics", company="NVDA").json()["items"]
keys = [(i["metric"], i["period"]) for i in m]
check("metrics: one record per metric and period (no duplicates)", len(keys) == len(set(keys)), len(keys))

check("metrics: repeat call gives the same result", get("/metrics").json() == get("/metrics").json())

j = get("/compare", period_a="Q4 FY26", period_b="Q1 FY27").json()
rev = next(r for r in j["rows"] if r["metric"] == "revenue")
check("compare: revenue Q4 FY26 -> Q1 FY27", rev["change"] == 13615.0 and rev["change_pct"] == 20.02, rev)
check("compare: rounding note for transcript values", any("rounded" in n for n in j["notes"]), j["notes"])

j = get("/compare", period_a="Q1 FY27", period_b="Q2 FY27").json()
gm = next(r for r in j["rows"] if r["metric"] == "gross_margin")
check("compare: margins use percentage points, no percent",
      gm["change_unit"] == "percentage_points" and gm["change_pct"] is None, gm)

j = get("/compare", period_a="Q1 FY27", period_b="Q3 FY27").json()
check("compare: missing period explained", any("Q3 FY27" in n for n in j["notes"]), j["notes"])

for label, params, code in (
    ("same period", dict(period_a="Q1 FY27", period_b="Q1 FY27"), "same_period"),
    ("invalid period", dict(period_a="Q1 FY27", period_b="banana"), "invalid_period"),
    ("unknown company", dict(period_a="Q1 FY27", period_b="Q2 FY27", company="nope"), "company_not_found"),
):
    r = get("/compare", **params)
    check(f"error: {label}", r.status_code in (404, 422) and r.json()["error"]["code"] == code, r.text[:120])

print(f"\nSUMMARY: {'ALL PASSED' if fails == 0 else str(fails) + ' FAILED'}")
