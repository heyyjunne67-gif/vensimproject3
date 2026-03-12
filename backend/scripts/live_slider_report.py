import json
from pathlib import Path
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:8011"
CASES = [
    ("solar_capacity_share", 0.33),
    ("euro5_transition_year", 2035),
    ("tree_survival_rate", 0.75),
]


def post_simulate(payload: dict) -> dict:
    req = Request(
        BASE + "/api/simulate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


rows = []
for key, value in CASES:
    payload = {"params": {key: value}, "subscripts": {}}
    data = post_simulate(payload)
    rows.append(
        {
            "case": key,
            "request": payload,
            "response": {
                "received_params": data.get("received_params", {}),
                "sanitized_params": data.get("sanitized_params", {}),
                "applied_overrides": data.get("applied_overrides", []),
                "ignored_overrides": data.get("ignored_overrides", []),
            },
        }
    )

report = {"base": BASE, "cases": rows}
Path("backend/live_slider_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("ok")
