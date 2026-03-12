from typing import Dict, List, Any
import numpy as np


def summarize_series(time: List[float], baseline: List[float], simulation: List[float]) -> Dict[str, Any]:
    b = np.array(baseline, dtype=float)
    s = np.array(simulation, dtype=float)

    def pct(a, b):
        if a == 0:
            return None
        return (b - a) / a * 100.0

    out = {
        "time_start": time[0] if time else None,
        "time_end": time[-1] if time else None,
        "baseline_last": float(b[-1]) if len(b) else None,
        "sim_last": float(s[-1]) if len(s) else None,
        "pct_change_last": pct(float(b[-1]), float(s[-1])) if len(b) and len(s) else None,
        "baseline_min": float(b.min()) if len(b) else None,
        "baseline_max": float(b.max()) if len(b) else None,
        "sim_min": float(s.min()) if len(s) else None,
        "sim_max": float(s.max()) if len(s) else None,
        "baseline_trend": "өсөх" if len(b) >= 2 and b[-1] > b[0] else "буурах/тогтвортой",
        "sim_trend": "өсөх" if len(s) >= 2 and s[-1] > s[0] else "буурах/тогтвортой",
    }
    return out


def build_stats_payload(time: List[float],
                        baseline_by_key: Dict[str, List[float]],
                        sim_by_key: Dict[str, List[float]]) -> Dict[str, Any]:
    stats = {}
    for k in baseline_by_key.keys():
        stats[k] = summarize_series(time, baseline_by_key.get(k, []), sim_by_key.get(k, []))
    return stats
