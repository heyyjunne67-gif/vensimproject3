from typing import Dict, List, Tuple, Any
from pathlib import Path
import re
import tempfile
import warnings
import pandas as pd
import numpy as np

from .config import settings
from .utils import file_exists

try:
    import pysd
except Exception:
    pysd = None

warnings.filterwarnings("ignore", category=UserWarning, module=r"pysd\.py_backend\.lookups")
warnings.filterwarnings("ignore", category=UserWarning, module=r"pysd\.py_backend\.statefuls")


def _patch_pysd_count_calls_once() -> None:
    if pysd is None:
        return
    try:
        from pysd.py_backend import model as pysd_model
        if getattr(pysd_model, "_safe_count_calls_patched", False):
            return

        original = pysd_model.Model._count_calls

        def safe_count_calls(self, element):
            try:
                return original(self, element)
            except Exception:
                return 1

        pysd_model.Model._count_calls = safe_count_calls
        setattr(pysd_model, "_safe_count_calls_patched", True)
    except Exception:
        return


def _patch_pysd_hardcoded_lookups_once() -> None:
    if pysd is None:
        return
    try:
        from pysd.py_backend import lookups as pysd_lookups
        if getattr(pysd_lookups, "_safe_hardcoded_lookups_patched", False):
            return

        original = pysd_lookups.HardcodedLookups.initialize

        def _dedupe_xy(x_vals, y_vals):
            x_list = list(x_vals)
            y_list = list(np.asarray(y_vals))
            keep_idx: List[int] = []
            seen = set()
            for i, xv in enumerate(x_list):
                if xv in seen:
                    continue
                seen.add(xv)
                keep_idx.append(i)

            new_x = [x_list[i] for i in keep_idx]
            if y_list:
                new_y = [y_list[i] if i < len(y_list) else y_list[-1] for i in keep_idx]
            else:
                new_y = y_list
            return new_x, new_y

        def safe_initialize(self):
            try:
                return original(self)
            except Exception as exc:
                if "uniquely valued Index objects" not in str(exc):
                    raise

                sanitized_values = []
                for x_vals, y_vals, coords in self.values:
                    new_x, new_y = _dedupe_xy(x_vals, y_vals)
                    sanitized_values.append((new_x, new_y, coords))

                self.values = sanitized_values
                return original(self)

        pysd_lookups.HardcodedLookups.initialize = safe_initialize
        setattr(pysd_lookups, "_safe_hardcoded_lookups_patched", True)
    except Exception:
        return


TOTAL_HERD_KEY = "total_ghg"
OUTPUT_KEYS = [
    "total_ghg",
    "energy_ghg",
    "transport_ghg",
    "agri_ghg",
    "forest_sink",
]

# UI нэр (output_key) → Vensim variable нэр (солих боломжтой)
VARIABLE_MAP_DEFAULT: Dict[str, str] = {
    "total_ghg": "Нийт хүлэмжийн хий",
    "energy_ghg": "Эрчим хүчний Хүлэмжийн хий",
    "transport_ghg": "Тээврийн салбарын хүлэмжийн хий",
    "agri_ghg": "ХАА салбараас гарах хүлэмжийн хий",
    "forest_sink": "Ойн хүлэмжийн хийн шингээлт",
}

# Slider key → Vensim parameter нэр (солих боломжтой)
PARAM_MAP_DEFAULT: Dict[str, str] = {
    "repro_rate": "Бэлчээрийн малын нөхөн үржих хувь хэмжээ",
    "slaughter_share": "Хэрэгцээнд нядалсан малын эзлэх хувь",
    "initial_herd": "Бэлчээрийн малын анхны тоо толгой",
    "sold_used_share": "Борлуулсан болон хүнсэнд хэрэглэсэн малын хувь хэмжээ",
    "disaster_impact": "Байгалийн гамшгийн бэлчээрийн мал сүргийн нөхөн төлжих нөлөө",
    "disaster_first_year": "Байгалийн гамшиг тохиолдсон анхны жил",
    "disaster_freq": "Байгалийн гамшгийн давтамж",
}


class ModelEngine:
    def __init__(self):
        self.model: Any = None
        self.model_ready: bool = False
        self.load_error: str | None = None
        self.time_unit_label: str = "TIME"
        self.variable_map = dict(VARIABLE_MAP_DEFAULT)
        self.param_map = dict(PARAM_MAP_DEFAULT)

        self._baseline_df: pd.DataFrame | None = None
        self._baseline_time: List[float] = []
        self._time_range: Tuple[float | None, float | None] = (None, None)
        self._available_subscripts: Dict[str, List[Dict[str, Any]]] = {}
        self.sim_time_step: float = float(getattr(settings, "SIM_TIME_STEP", 1.0) or 0.0)

    def load(self) -> None:
        self.model = None
        self._baseline_df = None
        self._baseline_time = []
        self._time_range = (None, None)
        self.model_ready = False
        self.load_error = None

        if pysd is None:
            self.load_error = "PySD is not installed or failed to import."
            return

        _patch_pysd_count_calls_once()
        _patch_pysd_hardcoded_lookups_once()

        if not file_exists(settings.MODEL_PATH):
            self.load_error = f"Model file not found: {settings.MODEL_PATH}"
            return

        try:
            model_path = settings.MODEL_PATH
            suffix = Path(model_path).suffix.lower()
            if suffix == ".py":
                self.model = self._load_python_model_with_fallback(model_path)
            else:
                self.model = self._load_vensim_model_with_fallback(model_path)
            # time unit label (best-effort)
            time_obj = getattr(self.model, "time", None)
            units = getattr(time_obj, "units", None)
            self.time_unit_label = str(units) if units is not None else "TIME"

            # baseline run (only chart-relevant columns for speed)
            baseline_cols = self._requested_output_columns()
            self._baseline_df = self._run_model(
                return_columns=baseline_cols,
                return_timestamps=self._requested_timestamps(),
                initial_condition="original",
                reload=True,
            )
            if self._baseline_df is None:
                raise RuntimeError("Model run returned None")
            self._baseline_time = self._extract_time(self._baseline_df)
            if self._baseline_time:
                self._time_range = (float(self._baseline_time[0]), float(self._baseline_time[-1]))
            self.model_ready = True

            # subscripts detect using get_coords (PySD docs) :contentReference[oaicite:7]{index=7}
            self._available_subscripts = self._detect_subscripts()

        except Exception as exc:
            self.load_error = f"Model load failed: {exc}"
            self.model_ready = False

    def _load_python_model_with_fallback(self, model_path: str):
        if pysd is None:
            raise RuntimeError("PySD is unavailable")
        source = Path(model_path).read_text(encoding="utf-8")
        patched = self._sanitize_lookup_coordinate_keys(source)
        patched = self._inject_runtime_stubs(patched)

        if patched == source:
            return pysd.load(model_path)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as tmp:
            tmp.write(patched)
            patched_path = tmp.name

        return pysd.load(patched_path)

    def _load_vensim_model_with_fallback(self, model_path: str):
        if pysd is None:
            raise RuntimeError("PySD is unavailable")
        prepared_model_path = self._prepare_vensim_model_path(model_path)
        try:
            return pysd.read_vensim(prepared_model_path)
        except Exception:
            # Some .mdl files translate but fail during model initialization.
            # In that case, force translation only, then sanitize and load the generated .py.
            translated = pysd.read_vensim(prepared_model_path, initialize=False)
            py_model_file = getattr(translated, "py_model_file", None)
            if py_model_file and file_exists(py_model_file):
                return self._load_python_model_with_fallback(py_model_file)
            raise

    def _prepare_vensim_model_path(self, model_path: str) -> str:
        """
        Some user-provided .mdl files declare UTF-8 but include a few broken bytes
        or superscript digits in identifiers, which can break PySD parsing.
        Normalize only when needed and keep the original file untouched.
        """
        raw = Path(model_path).read_bytes()
        decoded = raw.decode("utf-8", errors="replace")
        sanitized = decoded.translate(
            str.maketrans(
                {
                    "²": "2",
                    "³": "3",
                    "₀": "0",
                    "₁": "1",
                    "₂": "2",
                    "₃": "3",
                    "₄": "4",
                    "₅": "5",
                    "₆": "6",
                    "₇": "7",
                    "₈": "8",
                    "₉": "9",
                }
            )
        )
        # Some exported lookups contain stray "\" tokens around spaces, e.g.
        # "1.23\ )" or "(\ 2021,-1)", which break PySD eval parsing.
        sanitized = re.sub(r"\\\s+\)", ")", sanitized)
        sanitized = re.sub(r"\(\s*\\\s*", "(", sanitized)
        sanitized = re.sub(r"\\\s+", " ", sanitized)

        try:
            original = raw.decode("utf-8")
        except UnicodeDecodeError:
            original = None

        if original == sanitized:
            return model_path

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mdl", encoding="utf-8", delete=False) as tmp:
            tmp.write(sanitized)
            return tmp.name

    def _inject_runtime_stubs(self, source: str) -> str:
        patched = source

        if "def not_implemented_function(" not in patched:
            anchor = "from pysd import Component\n"
            if anchor in patched:
                stub = (
                    "\n"
                    "def not_implemented_function(*args, **kwargs):\n"
                    "    return 0\n"
                )
                patched = patched.replace(anchor, anchor + stub, 1)

        alias_marker = '_subscript_dict.setdefault("арван найман нас хүртлэх хүүхэд", ["Нас 0"])'
        component_anchor = "component = Component()\n"
        if alias_marker not in patched and component_anchor in patched:
            alias_patch = (
                '\n_subscript_dict.setdefault("арван найман нас хүртлэх хүүхэд", ["Нас 0"])\n'
                'if "Төрөх насныхан" not in _subscript_dict:\n'
                '    _subscript_dict["Төрөх насныхан"] = _subscript_dict.get("Төрөх насныхан!", _subscript_dict.get("Нас", []))\n'
            )
            patched = patched.replace(component_anchor, component_anchor + alias_patch, 1)

        return patched

    def _sanitize_lookup_coordinate_keys(self, source: str) -> str:
        lines = source.splitlines(keepends=True)
        out: List[str] = []
        in_lookup_block = False
        paren_depth = 0

        aliases = [
            "арван найман нас хүртлэх хүүхэд",
            "Төрөх насныхан",
            "Арван зургаагаас дээш насныхан",
        ]

        for line in lines:
            if not in_lookup_block and (
                "HardcodedLookups(" in line
                or (".add(" in line and "_hardcodedlookup" in line)
            ):
                in_lookup_block = True

            if in_lookup_block:
                for alias in aliases:
                    alias_escaped = alias.encode("unicode_escape").decode("ascii")
                    line = line.replace(f'"{alias}":', '"Нас":')
                    line = line.replace(f'"{alias_escaped}":', '"Нас":')

                line = line.replace('"Ð°Ñ€Ð²Ð°Ð½ Ð½Ð°Ð¹Ð¼Ð°Ð½ Ð½Ð°Ñ\x81 Ñ…Ò¯Ñ€Ñ‚Ð»Ñ\x8dÑ… Ñ…Ò¯Ò¯Ñ…Ñ\x8dÐ´":', '"Нас":')

                paren_depth += line.count("(") - line.count(")")
                if paren_depth <= 0:
                    in_lookup_block = False
                    paren_depth = 0

            out.append(line)

        return "".join(out)

    def _extract_time(self, df: pd.DataFrame | None) -> List[float]:
        if df is None:
            return []
        try:
            return [float(x) for x in df.index.values.tolist()]
        except Exception:
            return []

    def _detect_subscripts(self) -> Dict[str, List[Dict[str, Any]]]:
        out: Dict[str, List[Dict[str, Any]]] = {}
        if self.model is None:
            return out

        for out_key, vensim_name in self.variable_map.items():
            if out_key == TOTAL_HERD_KEY:
                out[out_key] = []
                continue
            dims_list: List[Dict[str, Any]] = []
            try:
                coords_raw = self.model.get_coords(vensim_name)  # returns dict dim->values :contentReference[oaicite:8]{index=8}
                coords: Dict[str, Any] = {}
                if isinstance(coords_raw, dict):
                    coords = coords_raw
                elif isinstance(coords_raw, tuple) and coords_raw:
                    first = coords_raw[0]
                    if isinstance(first, dict):
                        coords = first
                # coords might be {} for scalar
                for dim_name, values in coords.items():
                    # values can be list/Index
                    dims_list.append({"name": str(dim_name), "values": [str(v) for v in list(values)]})
            except Exception:
                dims_list = []
            out[out_key] = dims_list
        return out

    def get_available_subscripts(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._available_subscripts

    def get_time_range(self) -> Tuple[float | None, float | None]:
        return self._time_range

    def status(self) -> Dict[str, Any]:
        start, end = self.get_time_range()
        return {
            "model_ready": self.model_ready,
            "model_error": self.load_error,
            "time_range": {"start": start, "end": end},
        }

    def get_time_unit_label(self) -> str:
        return self.time_unit_label

    def get_baseline_filtered(self, subscripts: Dict[str, Dict[str, str]]) -> Tuple[List[float], Dict[str, List[float]]]:
        if self._baseline_df is None:
            raise RuntimeError(self.load_error or "Baseline is unavailable.")

        time = self._baseline_time
        baseline: Dict[str, List[float]] = {}
        for k in OUTPUT_KEYS:
            if k == TOTAL_HERD_KEY:
                baseline[k] = self._extract_total_series(self.variable_map.get(k, k), self._baseline_df)
            else:
                baseline[k] = self._extract_series(k, self.variable_map.get(k, k), self._baseline_df, subscripts.get(k, {}))
        return time, baseline

    def simulate(self, params: Dict[str, float], subscripts: Dict[str, Dict[str, str]]) -> Tuple[List[float], Dict[str, List[float]], Dict[str, List[float]]]:
        # baseline
        time, baseline = self.get_baseline_filtered(subscripts)

        # simulation
        if self.model is None or pysd is None:
            raise RuntimeError(self.load_error or "Model is unavailable for simulation.")

        # Map slider keys -> vensim param names
        overrides = {}
        for slider_key, val in params.items():
            resolved_name = self._resolve_param_name(slider_key)
            if resolved_name is None:
                continue
            overrides[resolved_name] = val

        # IMPORTANT: PySD params override via run(params=...) :contentReference[oaicite:9]{index=9}
        df_sim = self._run_model(
            params=overrides,
            return_columns=self._requested_output_columns(),
            return_timestamps=self._requested_timestamps(),
            initial_condition="original",
            reload=True,
        )

        sim: Dict[str, List[float]] = {}
        for k in OUTPUT_KEYS:
            if k == TOTAL_HERD_KEY:
                sim[k] = self._extract_total_series(self.variable_map.get(k, k), df_sim)
            else:
                sim[k] = self._extract_series(k, self.variable_map.get(k, k), df_sim, subscripts.get(k, {}))
        return time, baseline, sim

    def _normalize_component_name(self, value: str) -> str:
        normalized = " ".join(str(value).strip().split())
        while len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"\"", "'"}:
            normalized = normalized[1:-1].strip()
            normalized = " ".join(normalized.split())
        return normalized.casefold()

    def _component_name_variants(self, value: str) -> List[str]:
        base = str(value or "")
        variants = {base}
        if "хэрэглэсэн" in base:
            variants.add(base.replace("хэрэглэсэн", "хэрэглсэн"))
        if "Хэрэглэсэн" in base:
            variants.add(base.replace("Хэрэглэсэн", "Хэрэглсэн"))
        if "хэрэглсэн" in base:
            variants.add(base.replace("хэрэглсэн", "хэрэглэсэн"))
        if "Хэрэглсэн" in base:
            variants.add(base.replace("Хэрэглсэн", "Хэрэглэсэн"))
        return list(variants)

    def _resolve_param_name(self, slider_key: str) -> str | None:
        """
        Resolve frontend slider key to a model component name accepted by PySD.
        Priority:
        1) slider key itself (usually Py Name for dynamic sliders)
        2) explicit map value (usually real Vensim name)
        3) normalized text match against model namespace keys
        """
        mapped_name = self.param_map.get(slider_key, slider_key)

        if self.model is None:
            return mapped_name or slider_key

        namespace = getattr(self.model, "_namespace", None)
        if not isinstance(namespace, dict) or not namespace:
            return slider_key or mapped_name

        candidates = [slider_key]
        if mapped_name and mapped_name not in candidates:
            candidates.append(mapped_name)

        expanded_candidates: List[str] = []
        for candidate in candidates:
            for variant in self._component_name_variants(candidate):
                if variant not in expanded_candidates:
                    expanded_candidates.append(variant)

        for candidate in expanded_candidates:
            if candidate in namespace:
                return candidate

        normalized_namespace = {
            self._normalize_component_name(name): name
            for name in namespace.keys()
            if isinstance(name, str)
        }
        namespace_values = {
            str(value)
            for value in namespace.values()
            if isinstance(value, str)
        }

        for candidate in expanded_candidates:
            norm = self._normalize_component_name(candidate)
            if norm in normalized_namespace:
                return normalized_namespace[norm]
            if candidate in namespace_values:
                return candidate

        return None

    def resolve_param_name(self, slider_key: str) -> str | None:
        return self._resolve_param_name(slider_key)

    def _as_float_list(self, values: Any) -> List[float]:
        try:
            numeric = pd.to_numeric(pd.Series(list(values)), errors="coerce").fillna(0.0)
            return numeric.astype(float).tolist()
        except Exception:
            return []

    def _extract_total_series(self, vensim_var: str, df: pd.DataFrame | None) -> List[float]:
        if df is None:
            return []
        if vensim_var in df.columns:
            return self._as_float_list(df[vensim_var].values)
        if TOTAL_HERD_KEY in df.columns:
            return self._as_float_list(df[TOTAL_HERD_KEY].values)
        candidates = [c for c in df.columns if str(c).startswith(f"{vensim_var}[")]
        if candidates:
            totals = df[candidates].sum(axis=1)
            return self._as_float_list(totals.values)
        return [0.0 for _ in range(len(df.index))]

    def _extract_series(self, out_key: str, vensim_var: str, df: pd.DataFrame | None, subsel: Dict[str, str]) -> List[float]:
        """
        PySD output columns ихэвчлэн:
        - scalar: "Var"
        - subscript: "Var[Dim1,Dim2]" маягийн хэлбэртэй байх нь түгээмэл.
        Энэ функц нь хамгийн боломжит байдлаар сонгосон subscript-д таарсан series-ийг олно.
        Олдохгүй бол scalar fallback.
        """
        if df is None:
            return []
        # 1) direct column
        if vensim_var in df.columns:
            return self._as_float_list(df[vensim_var].values)

        # 2) try bracket matching
        candidates = [c for c in df.columns if str(c).startswith(f"{vensim_var}[")]
        if not candidates:
            if out_key in df.columns:
                return self._as_float_list(df[out_key].values)
            return [0.0 for _ in range(len(df.index))]

        # ensure deterministic ordering across runs
        candidates = sorted(candidates, key=lambda c: str(c))

        if not subsel:
            # no selection -> first candidate
            col = candidates[0]
            return self._as_float_list(df[col].values)

        # subsel dict: dim->value, but column string contains only values order.
        # We'll match values existence in bracket part.
        def score(colname: str) -> int:
            inside = colname.split("[", 1)[1].rstrip("]")
            parts = [p.strip() for p in inside.split(",")]
            s = 0
            for _, v in subsel.items():
                if str(v) in parts:
                    s += 1
            return s

        best = max(candidates, key=lambda c: (score(c), str(c)))
        return self._as_float_list(df[best].values)

    def applied_subscripts_per_output(self, subscripts: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        applied = {}
        for k in OUTPUT_KEYS:
            applied[k] = {} if k == TOTAL_HERD_KEY else subscripts.get(k, {})
        return applied

    def _requested_output_columns(self) -> List[str]:
        cols: List[str] = []
        for k in OUTPUT_KEYS:
            name = self.variable_map.get(k, k)
            if name and name not in cols:
                cols.append(name)
        return cols

    def _requested_timestamps(self) -> List[float] | None:
        if self.model is None:
            return None
        try:
            t = self.model.time
            start = float(t.initial_time())
            end = float(t.final_time())
            saveper = float(t.saveper())
            if saveper <= 0:
                saveper = 1.0
            return np.arange(start, end + saveper * 0.5, saveper, dtype=float).tolist()
        except Exception:
            return None

    def _run_model(self, **kwargs):
        """
        Run model in fast yearly step mode by default.
        Fallback to model defaults if the model cannot run with custom time_step.
        """
        if self.model is None:
            raise RuntimeError("Model is not loaded")

        def run_with_column_fallback(call_kwargs: Dict[str, Any]):
            try:
                return self.model.run(**call_kwargs)
            except Exception:
                # If requested columns do not exist in this model, retry with all columns.
                if "return_columns" in call_kwargs:
                    retry_kwargs = dict(call_kwargs)
                    retry_kwargs.pop("return_columns", None)
                    return self.model.run(**retry_kwargs)
                raise

        if self.sim_time_step > 0:
            fast_kwargs = dict(kwargs)
            fast_kwargs.setdefault("time_step", self.sim_time_step)
            fast_kwargs.setdefault("saveper", self.sim_time_step)
            try:
                return run_with_column_fallback(fast_kwargs)
            except Exception:
                # Some translated models are sensitive to custom step settings.
                # Fall back to the model-defined step to preserve correctness.
                pass

        return run_with_column_fallback(kwargs)
