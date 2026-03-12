from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Dict, Any
import json
import re
from pathlib import Path
import threading
import time
import math

from .config import settings
from .schemas import (
    ConfigPayload,
    SimulateRequest,
    ExplainRequest,
    ExplainResponse,
    SliderDef,
    AvailableSubscripts,
    DimDef,
    SeriesPayload,
    ChatGraphRequest,
    ChatGraphResponse,
)
from .model_engine import ModelEngine, OUTPUT_KEYS
from .stats import build_stats_payload
from .openai_client import openai_explain_mn

app = FastAPI(title="Vensim to Python Web API", version="1.0.0")


def _fix_text(value: Any) -> Any:
    if isinstance(value, str):
        if any(ch in value for ch in ("Ã", "Ð", "Ñ", "â", "�")):
            try:
                return value.encode("latin-1").decode("utf-8")
            except Exception:
                return value
        return value
    if isinstance(value, list):
        return [_fix_text(v) for v in value]
    if isinstance(value, dict):
        return {(_fix_text(k) if isinstance(k, str) else k): _fix_text(v) for k, v in value.items()}
    return value

# CORS :contentReference[oaicite:10]{index=10}
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = ModelEngine()
engine.load()

MODEL_RUN_LOCK = threading.Lock()
SIM_CACHE: Dict[str, Dict[str, Any]] = {}
SIM_CACHE_LOCK = threading.Lock()
SIM_CACHE_MAX_ENTRIES = 24

OUTPUTS_UI_MN = {
    "total_ghg": "Нийт хүлэмжийн хий",
    "energy_ghg": "Эрчим хүчний Хүлэмжийн хий",
    "transport_ghg": "Тээврийн салбарын хүлэмжийн хий",
    "agri_ghg": "ХАА салбараас гарах хүлэмжийн хий",
    "forest_sink": "Ойн хүлэмжийн хий шингээлт",
}

OUTPUTS_UI_EN = {
    "total_ghg": "Total greenhouse gas",
    "energy_ghg": "Energy sector emissions",
    "transport_ghg": "Transport sector emissions",
    "agri_ghg": "Agriculture sector emissions",
    "forest_sink": "Forest sink",
}

PARAM_LABELS_EN = {
    "repro_rate": "Pasture livestock reproduction rate",
    "slaughter_share": "Share of livestock slaughtered for demand",
    "initial_herd": "Initial pasture livestock population",
    "sold_used_share": "Share of livestock sold and consumed",
    "disaster_impact": "Disaster impact on livestock regeneration",
    "disaster_first_year": "First year of disaster occurrence",
    "disaster_freq": "Disaster frequency",
}

DYNAMIC_LABELS_EN_BY_MN = {
    "Нэмэгдэх чадлын хувь нар": "Solar capacity increase share",
    "Нэмэгдэх чадлын хувь салхи": "Wind capacity increase share",
    "Нэмэгдэх чадлын хувь ус": "Hydro capacity increase share",
    "Нэмэгдэх чадлын хувь нүүрс": "Coal capacity increase share",
    "Цахилгаан үйлдвэрлэх боломжит хэмжээ": "Electricity generation potential",
    "Зорчигчийн галт тэргийг цахилгаан халаалтад шилжүүлэх он": "Year to switch passenger trains to electric heating",
    "Борлуулсан болон хүнсэнд хэрэглсэн малын хувь хэмжээ": "Share of livestock sold and consumed",
    "хагас кокжсон түлш хэрэглэх он": "Year to use semi-coked fuel",
    "Эрдэнэбүрэнгийн 90 МВт УЦС төсөл ашиглалтанд орох": "Commissioning year of Erdeneburen 90 MW hydropower project",
    "Шатахууны импорт": "Fuel imports",
    "Цэнэглэх дэд бүтэц": "Charging infrastructure",
    "Төрийн бодлогын боломжит дэмжлэг": "Potential government policy support",
    "Машины үнэ": "Vehicle price",
    "Euro 5 д шилжих хувь": "Share transitioning to Euro 5",
    "Euro 5 д шилжих он": "Year of transition to Euro 5",
    "Нүүрс экспортлох тээврийг авто тээврээс төмөр замын тээвэрт шилжүүлэх хувь": "Share of coal export transport shifted from road to rail",
    "Нүүрс экспортлох тээврийг авто тээврээс төмөр замын тээвэрт шилжүүлэх он": "Year coal export transport shifts from road to rail",
    "Гангийн цогцолбор Дархан үйлдвэрлэл эхлэх он": "Start year of production at Darkhan steel complex",
    "Эрчим хүчний нүүрснээс эцсийн бүтээгдэхүүн гарган авах туршилтын үйлдвэрийн төсөл хэрэгжих он": "Year pilot project starts for producing end products from energy coal",
    "Зэсийн баяжмал хайлуулах, боловсруулах үйлдвэр төсөл хэрэгжих он": "Year copper concentrate smelting and processing project starts",
    "Мод тарих он": "Tree planting year",
    "Амжилттай ургах хувь": "Successful growth rate",
    "1-р арга хэмжээг хэрэгжүүлэх эсэх": "Implement measure 1",
    "2-р арга хэмжээг хэрэгжүүлэх эсэх": "Implement measure 2",
    "3-р арга хэмжээг хэрэгжүүлэх эсэх": "Implement measure 3",
    "4-р арга хэмжээг хэрэгжүүлэх эсэх": "Implement measure 4",
    "Бэлчээрийн усан хангамжийг нэмэгдүүлэх он": "Year to increase pasture water supply",
    "Бодлогын хүү": "Policy interest rate",
    "нүүрсний үнийн өөрчлөлт алдаа": "Coal price change error",
    "Хонины махны гарцын хувь": "Sheep meat yield share",
    "Адууны махны гарцын хувь": "Horse meat yield share",
    "Ямааны махны гарцын хувь": "Goat meat yield share",
    "Тэмээний махны гарцын хувь": "Camel meat yield share",
    "Үхрийн махны гарцын хувь": "Cattle meat yield share",
    "зэс бүтээгдэхүүний үнийн өөрчлөлт": "Copper product price change",
    "Борлуулсан болон хүнсэнд хэрэглэсэн малын хувь хэмжээ": "Share of livestock sold and consumed",
}


def _norm_space_casefold(value: str) -> str:
    normalized = " ".join(str(value).strip().split())
    while len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"\"", "'"}:
        normalized = normalized[1:-1].strip()
        normalized = " ".join(normalized.split())
    return normalized.casefold()


DYNAMIC_LABELS_EN_BY_MN_NORM = {
    _norm_space_casefold(k): v for k, v in DYNAMIC_LABELS_EN_BY_MN.items()
}

AI_SECTOR_OPTIONS_MN = [
    "Хүн ам",
    "Сургууль",
    "Дэд бүтэц",
    "Бэлчээрийн мал",
    "Газар тариалан",
    "ХАА",
    "Эрчим хүч, суурилгасан хүчин чадал",
    "Эрчим хүч үйлдвэрлэл",
    "Эрчим хүч дамжуулалт",
    "Эрчим хүч хэрэглээ",
    "Цахилгаан, хий, ус",
    "Тээврийн хэрэгслийн тоо",
    "Тээврийн ачаа, зорчигч",
    "Тээвэр агуулахын салбар",
    "Алт, Зэс, Нүүрс, Төмрийн хүдэр",
    "Уул уурхай, олборлолт",
    "Цемент, Шохой, Ган",
    "Боловсруулах үйлдвэрлэл",
    "Хог хаягдал",
    "Усан хангамж",
    "Барилга",
    "Бөөний болон жижиглэн",
    "Аялал жуулчлал",
    "Зочид буудал",
    "Мэдээлэл холбоо",
    "Санхүү даатгал",
    "Үл хөдлөх",
    "Шинжлэх ухаан",
    "Удирдлагын болон дэмжлэг",
    "Төрийн удирдлага",
    "Боловсролын салбар",
    "Эрүүл мэнд",
    "Урлаг үзвэр",
    "Бусад үйлчилгээ",
    "Гадаадын хөрөнгө оруулалт",
    "ДНБ",
    "Ажил эрхлэлт",
    "Засгийн газрын орлого",
    "Өрхийн орлого",
    "Ядуурал",
    "Хүрээлэн байгаа орчин",
    "Хөрсний чийгшил",
    "Ойн сангийн талбай",
    "Ойн 1 га талбайн нөөц",
    "Ойн нийт нөөц",
    "Ойн арга хэмжээ",
    "Ойн сан",
    "Хүлэмжийн хий",
    "Цахим хөгжлийн индекс",
    "Хүнсний аюулгүй байдал",
    "Гэмт хэрэг",
    "Бизнесийн орчин",
    "Авилга",
    "Ухаант засаглал",
    "Усны нөөц хэрэглээ",
]

DEFAULT_SLIDERS: list[SliderDef] = [
    SliderDef(
        key="solar_capacity_share",
        label_mn="Нэмэгдэх чадлын хувь нар",
        label_en="Solar energy capacity percentage",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.227,
        as_percent=True,
    ),
    SliderDef(
        key="wind_capacity_share",
        label_mn="Нэмэгдэх чадлын хувь салхи",
        label_en="Wind energy capacity percentage",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.14,
        as_percent=True,
    ),
    SliderDef(
        key="hydro_capacity_share",
        label_mn="Нэмэгдэх чадлын хувь ус",
        label_en="Hydro energy capacity percentage",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.035,
        as_percent=True,
    ),
    SliderDef(
        key="coal_capacity_share",
        label_mn="Нэмэгдэх чадлын хувь нүүрс",
        label_en="Coal energy capacity percentage",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.032,
        as_percent=True,
    ),
    SliderDef(
        key="electricity_potential",
        label_mn="Цахилгаан үйлдвэрлэх боломжит хэмжээ",
        label_en="Electricity generation potential",
        unit_mn="кВтц/тонн",
        unit_en="kWh/ton",
        min=1.0,
        max=100.0,
        step=1.0,
        default=10.0,
        as_percent=False,
    ),
    SliderDef(
        key="train_electrification_year",
        label_mn="Зорчигчийн галт тэргийг цахилгаан халаалтад шилжүүлэх он",
        label_en="Year to transition passenger trains to electric heating",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2100,
        as_percent=False,
    ),
    SliderDef(
        key="livestock_consumption_share",
        label_mn="Борлуулсан болон хүнсэнд хэрэглсэн малын хувь хэмжээ",
        label_en="Share of livestock sold and consumed",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.5,
        as_percent=True,
    ),
    SliderDef(
        key="semi_coke_usage_year",
        label_mn="Хагас кокжсон түлш хэрэглэх он",
        label_en="Year to start using semi-coke fuel",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2100,
        as_percent=False,
    ),
    SliderDef(
        key="erdeneburen_hpp_start_year",
        label_mn="Эрдэнэбүрэнгийн 90 МВт УЦС төсөл ашиглалтанд орох",
        label_en="Erdeneburen 90MW hydropower plant operation year",
        unit_mn="жил",
        unit_en="year",
        min=0.0,
        max=1.0,
        step=1,
        default=0.0,
        as_percent=False,
    ),
    SliderDef(
        key="fuel_import_level",
        label_mn="Шатахууны импорт",
        label_en="Fuel import level",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.1,
        default=0.0,
        as_percent=True,
    ),
    SliderDef(
        key="charging_infrastructure",
        label_mn="Цэнэглэх дэд бүтэц",
        label_en="Charging infrastructure",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.1,
        default=0.0,
        as_percent=True,
    ),
    SliderDef(
        key="government_policy_support",
        label_mn="Төрийн бодлогын боломжит дэмжлэг",
        label_en="Government policy support",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.1,
        default=0.0,
        as_percent=True,
    ),
    SliderDef(
        key="vehicle_price",
        label_mn="Машины үнэ",
        label_en="Vehicle price",
        unit_mn="индекс",
        unit_en="index",
        min=0.0,
        max=1.0,
        step=0.1,
        default=0.0,
        as_percent=False,
    ),
    SliderDef(
        key="euro5_transition_share",
        label_mn="Euro 5 д шилжих хувь",
        label_en="Share of transition to Euro 5",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.5,
        as_percent=True,
    ),
    SliderDef(
        key="euro5_transition_year",
        label_mn="Euro 5 д шилжих он",
        label_en="Year of transition to Euro 5",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2100,
        as_percent=False,
    ),
    SliderDef(
        key="coal_transport_shift_share",
        label_mn="Нүүрс экспортлох тээврийг авто тээврээс төмөр замын тээвэрт шилжүүлэх хувь",
        label_en="Share of coal transport shifted from road to rail",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.5,
        as_percent=True,
    ),
    SliderDef(
        key="coal_transport_shift_year",
        label_mn="Нүүрс экспортлох тээврийг авто тээврээс төмөр замын тээвэрт шилжүүлэх он",
        label_en="Year to shift coal transport from road to rail",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2100,
        as_percent=False,
    ),
    SliderDef(
        key="darkhan_steel_complex_year",
        label_mn="Гангийн цогцолбор Дархан үйлдвэрлэл эхлэх он",
        label_en="Year when Darkhan steel complex begins production",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2100,
        as_percent=False,
    ),
    SliderDef(
        key="coal_final_product_plant_year",
        label_mn="Эрчим хүчний нүүрснээс эцсийн бүтээгдэхүүн гарган авах туршилтын үйлдвэрийн төсөл хэрэгжих он",
        label_en="Year when coal-to-final-product pilot plant is implemented",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2100,
        as_percent=False,
    ),
    SliderDef(
        key="copper_smelter_project_year",
        label_mn="Зэсийн баяжмал хайлуулах, боловсруулах үйлдвэр төсөл хэрэгжих он",
        label_en="Year when copper smelter project is implemented",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2100,
        as_percent=False,
    ),
    SliderDef(
        key="tree_planting_year",
        label_mn="Мод тарих он",
        label_en="Tree planting year",
        unit_mn="жил",
        unit_en="year",
        min=2020,
        max=2100,
        step=1,
        default=2025,
        as_percent=False,
    ),
    SliderDef(
        key="tree_survival_rate",
        label_mn="Амжилттай ургах хувь",
        label_en="Tree survival rate",
        unit_mn="%",
        unit_en="%",
        min=0.0,
        max=1.0,
        step=0.01,
        default=0.6,
        as_percent=True,
    ),
    SliderDef(
        key="policy_measure_1",
        label_mn="1-р арга хэмжээг хэрэгжүүлэх эсэх",
        label_en="Implement policy measure 1",
        unit_mn="boolean",
        unit_en="boolean",
        min=0,
        max=1,
        step=1,
        default=0,
        as_percent=False,
    ),
    SliderDef(
        key="policy_measure_2",
        label_mn="2-р арга хэмжээг хэрэгжүүлэх эсэх",
        label_en="Implement policy measure 2",
        unit_mn="boolean",
        unit_en="boolean",
        min=0,
        max=1,
        step=1,
        default=0,
        as_percent=False,
    ),
    SliderDef(
        key="policy_measure_3",
        label_mn="3-р арга хэмжээг хэрэгжүүлэх эсэх",
        label_en="Implement policy measure 3",
        unit_mn="boolean",
        unit_en="boolean",
        min=0,
        max=1,
        step=1,
        default=0,
        as_percent=False,
    ),
    SliderDef(
        key="policy_measure_4",
        label_mn="4-р арга хэмжээг хэрэгжүүлэх эсэх",
        label_en="Implement policy measure 4",
        unit_mn="boolean",
        unit_en="boolean",
        min=0,
        max=1,
        step=1,
        default=0,
        as_percent=False,
    ),
]

REQUIRED_DYNAMIC_SLIDER_LABELS = [
    "нэмэгдэх чадлын хувь нар",
    "нэмэгдэх чадлын хувь салхи",
    "нэмэгдэх чадлын хувь ус",
    "нэмэгдэх чадлын хувь нүүрс",
    "Цахилгаан үйлдвэрлэх боломжит хэмжээ",
    "Зорчигчийн галт тэргийг цахилгаан халаалтад шилжүүлэх он",
    "Борлуулсан болон хүнсэнд хэрэглсэн малын хувь хэмжээ",
    "Хагас кокжсон түлш хэрэглэх он",
    "Эрдэнэбүрэнгийн 90 МВт УЦС төсөл ашиглалтанд орох",
    "Шатахууны импорт",
    "Цэнэглэх дэд бүтэц",
    "Төрийн бодлогын боломжит дэмжлэг",
    "Машины үнэ",
    "Euro 5 д шилжих хувь",
    "Euro 5 д шилжих он",
    "Нүүрс экспортлох тээврийг авто тээврээс төмөр замын тээвэрт шилжүүлэх хувь",
    "Нүүрс экспортлох тээврийг авто тээврээс төмөр замын тээвэрт шилжүүлэх он",
    "Гангийн цогцолбор Дархан үйлдвэрлэл эхлэх он",
    "Эрчим хүчний нүүрснээс эцсийн бүтээгдэхүүн гарган авах туршилтын үйлдвэрийн төсөл хэрэгжих он",
    "Зэсийн баяжмал хайлуулах, боловсруулах үйлдвэр төсөл хэрэгжих он",
    "Мод тарих он",
    "Амжилттай ургах хувь",
    "1-р арга хэмжээг хэрэгжүүлэх эсэх",
    "2-р арга хэмжээг хэрэгжүүлэх эсэх",
    "3-р арга хэмжээг хэрэгжүүлэх эсэх",
    "4-р арга хэмжээг хэрэгжүүлэх эсэх",
]

EXCLUDED_DYNAMIC_SLIDER_LABEL_PARTS = {
    "биоген биш хувь",
    "шатаах хувь",
    "ландфиллдах хувь",
    "төвлөрсөн системд холбогдсон хувь",
    "хөрөнгийн мэдрэмж",
    "мэдрэмж",
}

REQUIRED_DEFAULT_SLIDER_KEYS: set[str] = set()


def _step_from_limits(min_v: float, max_v: float) -> float:
    span = abs(max_v - min_v)
    if span <= 1:
        return 0.01
    if span <= 10:
        return 0.1
    if span <= 100:
        return 1
    if span <= 1000:
        return 10
    return max(1.0, round(span / 100.0, 2))


def _sanitize_params(raw_params: Dict[str, float]) -> Dict[str, float]:
    if not raw_params:
        return {}

    slider_by_key = {s.key: s for s in SLIDERS}
    cleaned: Dict[str, float] = {}

    for key, value in raw_params.items():
        try:
            v = float(value)
        except Exception:
            continue
        if not math.isfinite(v):
            continue

        slider = slider_by_key.get(key)
        if slider is not None:
            if v < slider.min:
                v = float(slider.min)
            elif v > slider.max:
                v = float(slider.max)

        cleaned[key] = v

    return cleaned


def _build_override_contract(
    raw_params: Dict[str, float],
    safe_params: Dict[str, float],
    baseline: Dict[str, list[float]],
    simulation: Dict[str, list[float]],
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    slider_by_key = {s.key: s for s in SLIDERS}
    applied: list[Dict[str, Any]] = []
    ignored: list[Dict[str, Any]] = []

    for key, raw_value in (raw_params or {}).items():
        if key not in slider_by_key:
            ignored.append({
                "key": key,
                "requested": raw_value,
                "reason": "unknown_slider",
            })
            continue

        if key not in safe_params:
            ignored.append({
                "key": key,
                "requested": raw_value,
                "reason": "invalid_value",
            })
            continue

        resolved_name = engine.resolve_param_name(key)
        if resolved_name is None:
            ignored.append({
                "key": key,
                "requested": raw_value,
                "applied": safe_params[key],
                "reason": "not_mapped_to_model",
            })
            continue

        applied.append({
            "key": key,
            "requested": raw_value,
            "applied": safe_params[key],
            "model_parameter": resolved_name,
        })

    return applied, ignored


def _series_payload_result(
    *,
    time: list[float],
    baseline: Dict[str, list[float]],
    simulation: Dict[str, list[float]],
    received_params: Dict[str, float],
    sanitized_params: Dict[str, float],
    applied_subscripts: Dict[str, Dict[str, str]],
    applied_overrides: list[Dict[str, Any]],
    ignored_overrides: list[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "time": time,
        "baseline": baseline,
        "simulation": simulation,
        "received_params": received_params,
        "sanitized_params": sanitized_params,
        "applied_subscripts": applied_subscripts,
        "applied_overrides": applied_overrides,
        "ignored_overrides": ignored_overrides,
    }


def _make_sim_cache_key(params: Dict[str, float], subscripts: Dict[str, Dict[str, str]]) -> str:
    payload = {
        "params": params or {},
        "subscripts": subscripts or {},
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _cache_get(cache_key: str) -> Dict[str, Any] | None:
    with SIM_CACHE_LOCK:
        item = SIM_CACHE.get(cache_key)
        if item is None:
            return None
        item["last_access"] = time.time()
        return {
            "time": item["time"],
            "baseline": item["baseline"],
            "simulation": item["simulation"],
            "received_params": item.get("received_params", {}),
            "sanitized_params": item.get("sanitized_params", {}),
            "applied_subscripts": item["applied_subscripts"],
            "applied_overrides": item.get("applied_overrides", []),
            "ignored_overrides": item.get("ignored_overrides", []),
        }


def _cache_set(cache_key: str, result: Dict[str, Any]) -> None:
    now = time.time()
    with SIM_CACHE_LOCK:
        SIM_CACHE[cache_key] = {
            "time": result["time"],
            "baseline": result["baseline"],
            "simulation": result["simulation"],
            "received_params": result.get("received_params", {}),
            "sanitized_params": result.get("sanitized_params", {}),
            "applied_subscripts": result["applied_subscripts"],
            "applied_overrides": result.get("applied_overrides", []),
            "ignored_overrides": result.get("ignored_overrides", []),
            "last_access": now,
        }
        if len(SIM_CACHE) > SIM_CACHE_MAX_ENTRIES:
            oldest_key = min(SIM_CACHE, key=lambda k: float(SIM_CACHE[k].get("last_access", 0.0)))
            SIM_CACHE.pop(oldest_key, None)


def _build_sliders_from_python_model(
    model_path: str,
    relevant_output_names: list[str] | None = None,
    max_sliders: int | None = None,
) -> tuple[list[SliderDef], dict[str, str]]:
    src = Path(model_path).read_text(encoding="utf-8")
    num = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
    block_re = re.compile(
        r"@component\.add\((?P<decorator>.*?)\)\s*def\s+(?P<func>[A-Za-z_]\w*)\s*\([^)]*\):(?P<body>.*?)(?=\n@component\.add\(|\Z)",
        re.S,
    )

    sliders: list[SliderDef] = []
    param_map: dict[str, str] = {}
    all_funcs: set[str] = set()
    func_by_name: dict[str, str] = {}
    deps_by_func: dict[str, set[str]] = {}
    dependents_by_func: dict[str, set[str]] = {}
    parsed_slider_rows: list[tuple[str, str, float, float, float]] = []

    def _norm_label(value: str) -> str:
        return _norm_space_casefold(value)

    def _label_en_from_mn(label_mn: str) -> str:
        return DYNAMIC_LABELS_EN_BY_MN_NORM.get(_norm_label(label_mn), label_mn)

    def _fallback_slider_for_label(label: str, idx: int) -> SliderDef:
        label_norm = _norm_label(label)
        key = f"manual_param_{idx + 1}"
        if "эсэх" in label_norm:
            return SliderDef(
                key=key,
                label_mn=label,
                label_en=_label_en_from_mn(label),
                unit_mn="",
                unit_en="",
                min=0.0,
                max=1.0,
                step=1.0,
                default=0.0,
                as_percent=False,
            )
        if "он" in label_norm:
            return SliderDef(
                key=key,
                label_mn=label,
                label_en=_label_en_from_mn(label),
                unit_mn="жил",
                unit_en="year",
                min=2010.0,
                max=2050.0,
                step=1.0,
                default=2030.0,
                as_percent=False,
            )
        if "хувь" in label_norm:
            return SliderDef(
                key=key,
                label_mn=label,
                label_en=_label_en_from_mn(label),
                unit_mn="%",
                unit_en="%",
                min=0.0,
                max=1.0,
                step=0.01,
                default=0.5,
                as_percent=True,
            )
        return SliderDef(
            key=key,
            label_mn=label,
            label_en=_label_en_from_mn(label),
            unit_mn="",
            unit_en="",
            min=0.0,
            max=100.0,
            step=1.0,
            default=0.0,
            as_percent=False,
        )

    required_dynamic_labels_norm = {_norm_label(v) for v in REQUIRED_DYNAMIC_SLIDER_LABELS}
    required_dynamic_order = {
        _norm_label(v): i for i, v in enumerate(REQUIRED_DYNAMIC_SLIDER_LABELS)
    }
    excluded_dynamic_label_parts_norm = {
        _norm_label(v) for v in EXCLUDED_DYNAMIC_SLIDER_LABEL_PARTS
    }

    for m in block_re.finditer(src):
        decorator = m.group("decorator")
        body = m.group("body")
        func_name = m.group("func")
        all_funcs.add(func_name)

        name_m = re.search(r'name\s*=\s*"([^"]+)"', decorator)
        if name_m:
            func_by_name[name_m.group(1).strip()] = func_name

        dep_keys: set[str] = set()
        dep_block_m = re.search(r"depends_on\s*=\s*\{(?P<deps>.*?)\}", decorator, re.S)
        if dep_block_m:
            dep_text = dep_block_m.group("deps")
            for dep_name in re.findall(r'"([A-Za-z_]\w*)"\s*:', dep_text):
                if dep_name not in {"__lookup__", "time"}:
                    dep_keys.add(dep_name)
        deps_by_func[func_name] = dep_keys
        for dep_name in dep_keys:
            dependents_by_func.setdefault(dep_name, set()).add(func_name)

        limits_m = re.search(rf"limits\s*=\s*\(\s*({num})\s*,\s*({num})\s*\)", decorator)
        default_m = re.search(rf"return\s+({num})", body)

        if not name_m or not limits_m or not default_m:
            continue

        try:
            min_v = float(limits_m.group(1))
            max_v = float(limits_m.group(2))
            default_v = float(default_m.group(1))
        except Exception:
            continue

        if min_v == max_v:
            continue

        label = _fix_text(name_m.group(1).strip())
        if default_v < min_v:
            default_v = min_v
        if default_v > max_v:
            default_v = max_v

        parsed_slider_rows.append((func_name, label, min_v, max_v, default_v))

    relevant_funcs: set[str] = set()
    seed_funcs: set[str] = set()
    if relevant_output_names:
        seed_funcs = {func_by_name[name] for name in relevant_output_names if name in func_by_name}
        if seed_funcs:
            stack = list(seed_funcs)
            seen: set[str] = set()
            while stack:
                node = stack.pop()
                if node in seen:
                    continue
                seen.add(node)
                for dep in deps_by_func.get(node, set()):
                    if dep in all_funcs and dep not in seen:
                        stack.append(dep)
            relevant_funcs = seen

    def _coverage_and_distance(start_func: str) -> tuple[int, int]:
        if not seed_funcs:
            return (0, 10**9)
        stack: list[tuple[str, int]] = [(start_func, 0)]
        visited: set[str] = {start_func}
        covered: set[str] = set()
        min_dist: int | None = None

        while stack:
            node, depth = stack.pop()
            if node in seed_funcs:
                covered.add(node)
                if min_dist is None or depth < min_dist:
                    min_dist = depth

            for nxt in dependents_by_func.get(node, set()):
                if relevant_funcs and nxt not in relevant_funcs:
                    continue
                if nxt in visited:
                    continue
                visited.add(nxt)
                stack.append((nxt, depth + 1))

        return (len(covered), min_dist if min_dist is not None else 10**9)

    ranked_rows: list[tuple[int, int, str, str, float, float, float]] = []
    for key, label, min_v, max_v, default_v in parsed_slider_rows:
        label_norm = _norm_label(label)
        if label_norm not in required_dynamic_labels_norm:
            continue
        if any(part in label_norm for part in excluded_dynamic_label_parts_norm):
            continue
        coverage, distance = _coverage_and_distance(key)
        ranked_rows.append((coverage, distance, key, label, min_v, max_v, default_v))

    def _rank_key(row: tuple[int, int, str, str, float, float, float]):
        _, distance, key, label, _, _, _ = row
        label_norm = _norm_label(label)
        if label_norm in required_dynamic_order:
            return (0, required_dynamic_order[label_norm], key)
        return (1, distance, key)

    ranked_rows.sort(key=_rank_key)

    rows_by_label_norm: dict[str, tuple[int, int, str, str, float, float, float]] = {}
    for row in ranked_rows:
        row_norm = _norm_label(row[3])
        if row_norm not in rows_by_label_norm:
            rows_by_label_norm[row_norm] = row

    alias_norm_map: dict[str, list[str]] = {
        _norm_label("Борлуулсан болон хүнсэнд хэрэглсэн малын хувь хэмжээ"): [
            _norm_label("Борлуулсан болон хүнсэнд хэрэглэсэн малын хувь хэмжээ")
        ],
    }

    used_keys: set[str] = set()
    for idx, required_label in enumerate(REQUIRED_DYNAMIC_SLIDER_LABELS):
        required_norm = _norm_label(required_label)
        candidate_norms = [required_norm] + alias_norm_map.get(required_norm, [])

        selected_row = None
        for candidate in candidate_norms:
            row = rows_by_label_norm.get(candidate)
            if row is None:
                continue
            if row[2] in used_keys:
                continue
            selected_row = row
            break

        if selected_row is None:
            fallback = _fallback_slider_for_label(required_label, idx)
            sliders.append(fallback)
            param_map[fallback.key] = required_label
            used_keys.add(fallback.key)
            continue

        _, _, key, _, min_v, max_v, default_v = selected_row
        as_percent = (0.0 <= min_v <= 1.0 and 0.0 <= max_v <= 1.0) or ("хувь" in required_label.lower())
        unit = "%" if as_percent else ""

        sliders.append(
            SliderDef(
                key=key,
                label_mn=required_label,
                label_en=PARAM_LABELS_EN.get(key, _label_en_from_mn(required_label)),
                unit_mn=unit,
                unit_en=unit,
                min=min_v,
                max=max_v,
                step=_step_from_limits(min_v, max_v),
                default=default_v,
                as_percent=as_percent,
            )
        )
        param_map[key] = required_label
        used_keys.add(key)

    return sliders, param_map


SLIDERS: list[SliderDef] = DEFAULT_SLIDERS
engine.param_map = {s.key: s.label_mn for s in DEFAULT_SLIDERS}

if Path(settings.MODEL_PATH).suffix.lower() == ".py":
    try:
        dynamic_sliders_for_mapping, _ = _build_sliders_from_python_model(
            settings.MODEL_PATH,
            relevant_output_names=list(engine.variable_map.values()),
            max_sliders=int(getattr(settings, "DYNAMIC_SLIDER_LIMIT", 24) or 24),
        )
        model_key_by_label_norm = {
            _norm_space_casefold(s.label_mn): s.key
            for s in dynamic_sliders_for_mapping
            if not str(s.key).startswith("manual_param_")
        }

        # Fallback mapping: parse raw model source to bind label -> real function key (e.g. nvs__123)
        src = Path(settings.MODEL_PATH).read_text(encoding="utf-8")
        block_re = re.compile(
            r"@component\.add\((?P<decorator>.*?)\)\s*def\s+(?P<func>[A-Za-z_]\w*)\s*\([^)]*\):",
            re.S,
        )
        for m in block_re.finditer(src):
            name_m = re.search(r'name\s*=\s*"([^"]+)"', m.group("decorator"))
            if not name_m:
                continue
            label_norm = _norm_space_casefold(_fix_text(name_m.group(1).strip()))
            model_key_by_label_norm.setdefault(label_norm, m.group("func"))

        mapped_param_map: dict[str, str] = {}
        for slider in DEFAULT_SLIDERS:
            label_norm = _norm_space_casefold(slider.label_mn)
            resolved_key = model_key_by_label_norm.get(label_norm)
            if resolved_key is None and "хэрэглсэн" in label_norm:
                resolved_key = model_key_by_label_norm.get(label_norm.replace("хэрэглсэн", "хэрэглэсэн"))
            if resolved_key is None and "хэрэглэсэн" in label_norm:
                resolved_key = model_key_by_label_norm.get(label_norm.replace("хэрэглэсэн", "хэрэглсэн"))

            mapped_param_map[slider.key] = resolved_key or slider.label_mn

        engine.param_map = mapped_param_map
    except Exception:
        engine.param_map = {s.key: s.label_mn for s in DEFAULT_SLIDERS}


@app.get("/")
def root():
    return {"message": "Backend ажиллаж байна. /docs дээр API-г шалгана уу."}


@app.get("/api/health")
def health():
    status = engine.status()
    status["ok"] = bool(status.get("model_ready"))
    return status


@app.get("/api/config")
def get_config():
    av = engine.get_available_subscripts()
    av_pyd = AvailableSubscripts(
        outputs={
            k: [DimDef(**d) for d in v] for k, v in av.items()
        }
    )

    status = engine.status()

    payload = ConfigPayload(
        ui_title_mn="Vensim → Python (PySD) Вэб Симуляци",
        ui_subtitle_mn="",
        outputs_ui_mn=OUTPUTS_UI_MN,
        ai_sector_options=AI_SECTOR_OPTIONS_MN,
        sliders=SLIDERS,
        variable_map=engine.variable_map,
        param_map=engine.param_map,
        available_subscripts=av_pyd,
        model_ready=bool(status["model_ready"]),
        model_error=status.get("model_error"),
        time_range=status.get("time_range", {}),
    )
    fixed = _fix_text(payload.model_dump())
    return JSONResponse(content=fixed)


@app.post("/api/simulate")
def simulate(req: SimulateRequest):
    status = engine.status()
    if not status.get("model_ready"):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "MODEL_NOT_READY",
                "message": status.get("model_error") or "Model is not ready.",
            },
        )

    safe_params = _sanitize_params(req.params)
    cache_key = _make_sim_cache_key(safe_params, req.subscripts)
    cached = _cache_get(cache_key)
    if cached is not None:
        return SeriesPayload(**cached)

    with MODEL_RUN_LOCK:
        time, baseline, simulation = engine.simulate(safe_params, req.subscripts)

    applied = engine.applied_subscripts_per_output(req.subscripts)
    applied_overrides, ignored_overrides = _build_override_contract(
        req.params,
        safe_params,
        baseline,
        simulation,
    )

    result = _series_payload_result(
        time=time,
        baseline=baseline,
        simulation=simulation,
        received_params=req.params,
        sanitized_params=safe_params,
        applied_subscripts=applied,
        applied_overrides=applied_overrides,
        ignored_overrides=ignored_overrides,
    )
    _cache_set(cache_key, result)

    return SeriesPayload(**result)


@app.post("/api/reset")
def reset(req: SimulateRequest):
    status = engine.status()
    if not status.get("model_ready"):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "MODEL_NOT_READY",
                "message": status.get("model_error") or "Model is not ready.",
            },
        )

    with MODEL_RUN_LOCK:
        time, baseline = engine.get_baseline_filtered(req.subscripts)
    applied = engine.applied_subscripts_per_output(req.subscripts)

    # reset үед simulation-ийг baseline-тэй адил биш, хоосон болгоно
    simulation = {k: [] for k in OUTPUT_KEYS}

    return SeriesPayload(
        **_series_payload_result(
            time=time,
            baseline=baseline,
            simulation=simulation,
            received_params=req.params,
            sanitized_params={},
            applied_subscripts=applied,
            applied_overrides=[],
            ignored_overrides=[],
        )
    )


@app.post("/api/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest):
    lang = (req.language or "mn").strip().lower()
    is_en = lang.startswith("en")

    if not settings.OPENAI_API_KEY:
        return ExplainResponse(text_mn="AI API key is not configured." if is_en else "AI API key тохируулаагүй байна.")

    all_stats = req.stats or {}
    if req.series is not None:
        all_stats = build_stats_payload(
            req.series.time,
            req.series.baseline,
            req.series.simulation,
        )
    sector_labels = req.sector_labels or {}
    variable_map = req.variable_map or {}
    selected = req.selected_sectors or []
    if not selected:
        selected = AI_SECTOR_OPTIONS_MN[:5]

    if not all_stats:
        return ExplainResponse(text_mn="No sector data available for explanation." if is_en else "Тайлбар гаргах секторын өгөгдөл олдсонгүй.")

    param_label_map = {
        s.key: ((s.label_en or s.label_mn) if is_en else s.label_mn)
        for s in SLIDERS
    }

    changed_params = []
    for key, sim_val in (req.params_used or {}).items():
        base_val = (req.baseline_params or {}).get(key)
        if base_val is None:
            continue
        try:
            delta = float(sim_val) - float(base_val)
        except Exception:
            continue
        if abs(delta) <= 1e-12:
            continue
        changed_params.append({
            "parameter": param_label_map.get(key, key.replace("_", " ").strip().title()),
            "baseline": base_val,
            "simulation": sim_val,
            "delta": delta,
            "direction": "increase" if delta > 0 else "decrease",
        })

    elasticity_by_output: Dict[str, Any] = {}
    for output_key, st in all_stats.items():
        b_last = st.get("baseline_last")
        s_last = st.get("sim_last")
        if b_last in (None, 0) or s_last is None:
            continue
        output_rel = (float(s_last) - float(b_last)) / max(abs(float(b_last)), 1e-9)
        output_elasticities: list[Dict[str, Any]] = []
        for p in changed_params:
            base_param = float(p["baseline"])
            sim_param = float(p["simulation"])
            param_rel = (sim_param - base_param) / max(abs(base_param), 1e-9)
            if abs(param_rel) <= 1e-12:
                continue
            e = output_rel / param_rel
            ae = abs(e)
            if ae > 1:
                influence = "very strong influence" if is_en else "маш хүчтэй нөлөө"
            elif ae >= 0.3:
                influence = "moderate influence" if is_en else "дунд зэргийн нөлөө"
            elif ae >= 0.05:
                influence = "weak influence" if is_en else "сул нөлөө"
            else:
                influence = "negligible influence" if is_en else "бараг нөлөөгүй"
            output_elasticities.append({
                "parameter": p["parameter"],
                "influence": influence,
                "direction": "positive" if e >= 0 else "negative",
            })
        if output_elasticities:
            elasticity_by_output[output_key] = output_elasticities

    negligible_outputs = [
        {
            "output": k,
            "pct_change_last": v.get("pct_change_last"),
        }
        for k, v in all_stats.items()
        if isinstance(v.get("pct_change_last"), (int, float)) and abs(float(v["pct_change_last"])) < 0.1
    ]

    output_labels = {
        "energy_ghg": "Energy sector emissions" if is_en else "Эрчим хүчний салбарын ялгаруулалт",
        "total_ghg": "Total greenhouse gas" if is_en else "Нийт хүлэмжийн хий",
        "transport_ghg": "Transport sector emissions" if is_en else "Тээврийн салбарын ялгаруулалт",
        "forest_sink": "Forest sink" if is_en else "Ойн шингээлт",
        "agri_ghg": "Agriculture sector emissions" if is_en else "Хөдөө аж ахуйн салбарын ялгаруулалт",
    }
    output_labels.update(OUTPUTS_UI_EN if is_en else OUTPUTS_UI_MN)
    output_labels.update(sector_labels)

    def _related_output_keys(sector_name: str) -> list[str]:
        text = (sector_name or "").casefold()
        keys: list[str] = []

        if any(token in text for token in ["эрчим", "цахилгаан", "хий", "ус", "energy", "electric", "power", "gas", "water"]):
            keys.append("energy_ghg")
        if any(token in text for token in ["тээвэр", "логистик", "агуулах", "зорчигч", "transport", "logistics", "warehouse", "passenger"]):
            keys.append("transport_ghg")
        if any(token in text for token in ["хаа", "мал", "тариалан", "хүнс", "agri", "agriculture", "livestock", "food", "crop"]):
            keys.append("agri_ghg")
        if any(token in text for token in ["ойн", "ой ", "нөөц", "мод", "forest", "tree", "sink"]):
            keys.append("forest_sink")

        keys.append("total_ghg")

        dedup: list[str] = []
        for key in keys:
            if key in all_stats and key not in dedup:
                dedup.append(key)

        if not dedup:
            dedup = [k for k in all_stats.keys() if k in OUTPUTS_UI_MN]
        return dedup[:3]

    sectors_context = []
    for sector_name in selected:
        related = _related_output_keys(sector_name)
        indicators = []
        for key in related:
            if key not in all_stats:
                continue
            indicators.append({
                "name": output_labels.get(key, key),
                "stats": all_stats[key],
                "sensitivity": elasticity_by_output.get(key, []),
                "model_variable_label": variable_map.get(key) or engine.variable_map.get(key, ""),
            })

        sectors_context.append({
            "sector_name": sector_name,
            "indicators": indicators,
        })

    negligible_context = [
        {
            "indicator": output_labels.get(item["output"], item["output"]),
            "explain_hint": "weak system linkage or delayed long-term effect" if is_en else "системийн хамаарал сул эсвэл удаан хугацааны хоцрогдолтой нөлөө",
        }
        for item in negligible_outputs
    ]

    prompt = f"""
You are a system dynamics analytical report generator.

Your task is to explain greenhouse gas simulation results clearly,
professionally, and analytically for non-technical decision makers.

CRITICAL RULES:
1) NEVER expose internal variable names such as energy_ghg, total_ghg, transport_ghg,
   forest_sink, nvs__861, nvs__1099, or any raw model codes.
2) Always convert variable names into clean human labels:
   - energy_ghg → "{output_labels.get("energy_ghg", "Energy sector emissions")}"
   - total_ghg → "{output_labels.get("total_ghg", "Total greenhouse gas")}"
   - transport_ghg → "{output_labels.get("transport_ghg", "Transport sector emissions")}"
   - forest_sink → "{output_labels.get("forest_sink", "Forest sink")}"
3) Structure the explanation in 4 logical layers:
   I. Mathematical Interpretation
   II. System (Vensim) Interpretation
   III. Quantitative Interpretation
   IV. Sensitivity (Elasticity) Interpretation
4) If a variable has near-zero change, explain as weak linkage or delayed effect.
5) Do NOT present raw debugging fields like baseline_last, sim_last, pct_change_last.
   Convert them into narrative sentences.
6) The explanation must read like a policy or research report, not log output.

Tone:
Professional, analytical, structured, clear. Never technical-debug style.

Output language: {"English" if is_en else "Монгол хэл"}.

=== Context ===
{"Selected sectors" if is_en else "Сонгосон секторууд"}:
{json.dumps(sectors_context, ensure_ascii=False, indent=2)}

{"Changed parameters (human-readable)" if is_en else "Өөрчлөгдсөн параметрүүд (human-readable)"}:
{json.dumps(changed_params, ensure_ascii=False, indent=2)}

{"Low-impact indicators" if is_en else "Нөлөө бага үзүүлэлтүүд"}:
{json.dumps(negligible_context, ensure_ascii=False, indent=2)}
""".strip()

    try:
        text_mn = openai_explain_mn(prompt)
        return ExplainResponse(text_mn=text_mn)
    except Exception as e:
        if is_en:
            return ExplainResponse(text_mn=f"Failed to generate AI explanation: {e}")
        return ExplainResponse(text_mn=f"AI тайлбар үүсгэхэд алдаа гарлаа: {e}")


CHAT_SYSTEM_PROMPT = """
You are an analytical assistant explaining system dynamics simulation results to end users.

CRITICAL RULES:
1) NEVER expose internal variable names such as technical IDs, backend keys, raw model codes, or identifiers like nvs__861.
2) Always use human-readable parameter names.
3) If a parameter name looks technical/auto-generated (e.g., contains "__" or coded numeric suffixes), map to a friendly label or omit it.
4) Write for non-technical users. Avoid raw deltas without explanation.
5) When identifying the most impactful parameter, explain why the effect is strongest and whether it is positive/negative.
6) If multiple parameters changed, group logically and mention only meaningful ones.
7) If a parameter has negligible effect, explicitly say it did not meaningfully affect the result.
8) Use structure: most influential parameter, direction (increase/decrease), short reasoning, optional comparison.
9) Never hallucinate data; use only provided context.
10) If the requested time is out of range, state the valid time range only.

Response style:
- Clear, professional, human-readable.
- Use the language requested by the payload language field.
""".strip()


def _looks_technical_identifier(name: str) -> bool:
    value = str(name or "").strip()
    if not value:
        return True
    lowered = value.casefold()
    if "__" in value:
        return True
    if re.fullmatch(r"nvs__\d+", lowered):
        return True
    if re.fullmatch(r"[a-z]{1,6}\d{3,}", lowered):
        return True
    if re.fullmatch(r"[a-z0-9_]+", lowered) and re.search(r"_\d+$", lowered):
        return True
    return False


def _to_friendly_label(name: Any) -> str | None:
    raw = str(name or "").strip()
    if not raw:
        return None
    if _looks_technical_identifier(raw):
        return None

    cleaned = raw.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\b\d+\b", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return None

    if re.fullmatch(r"[A-Za-z ]+", cleaned):
        cleaned = " ".join(part.capitalize() for part in cleaned.split())
    return cleaned


def _pct_delta(b: float, s: float) -> float:
    denom = max(abs(b), 1e-9)
    return (s - b) / denom * 100.0


def _contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[\u0400-\u04FF]", str(text or "")))


def _find_time_index(time_list: list, target: Any) -> int | None:
    for i, t in enumerate(time_list):
        if str(t) == str(target):
            return i
        try:
            if float(t) == float(target):
                return i
        except Exception:
            continue
    return None


def _resolve_time_value(time_list: list, target: Any) -> tuple[Any, int | None, bool]:
    idx = _find_time_index(time_list, target)
    if idx is not None:
        return time_list[idx], idx, True
    try:
        target_num = float(target)
    except Exception:
        return None, None, False
    best_idx = None
    best_diff = None
    for i, t in enumerate(time_list):
        try:
            diff = abs(float(t) - target_num)
        except Exception:
            continue
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_idx = i
    if best_idx is None:
        return None, None, False
    return time_list[best_idx], best_idx, False


def _extract_year_from_question(question: str) -> str | None:
    m = re.search(r"\b(19|20)\d{2}\b", question)
    return m.group(0) if m else None


def _extract_year_range(question: str) -> tuple[str, str] | None:
    m = re.search(r"\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})\b", question)
    if not m:
        return None
    return m.group(1), m.group(2)


def _strict_time_error(series_time: list[Any], requested: Any) -> Dict[str, Any]:
    if not series_time:
        return {
            "code": "TIME_RANGE_UNAVAILABLE",
            "message": "Simulation time range is unavailable.",
            "valid_time_range": {"start": None, "end": None},
            "requested": requested,
        }
    return {
        "code": "TIME_OUT_OF_RANGE",
        "message": "Requested time is outside the simulation range.",
        "valid_time_range": {"start": series_time[0], "end": series_time[-1]},
        "requested": requested,
    }


def _calc_growth_pct(values: list[float], time: list, start: Any, end: Any) -> float | None:
    start_idx = _find_time_index(time, start)
    end_idx = _find_time_index(time, end)
    if start_idx is None or end_idx is None:
        return None
    try:
        start_val = values[start_idx]
        end_val = values[end_idx]
        if start_val is None or end_val is None:
            return None
        return _pct_delta(start_val, end_val)
    except Exception:
        return None


def _build_chat_context(req: ChatGraphRequest) -> Dict[str, Any]:
    series_context = []
    for s in req.series:
        if not s.time:
            continue

        last_idx = len(s.time) - 1
        b_last = s.baseline_values[last_idx] if len(s.baseline_values) > last_idx else None
        s_last = s.sim_values[last_idx] if len(s.sim_values) > last_idx else None

        delta_last = (s_last - b_last) if (b_last is not None and s_last is not None) else None
        pct_last = _pct_delta(b_last, s_last) if (b_last is not None and s_last is not None) else None

        selected_tp = req.run_meta.selected_time_point
        sel_idx = _find_time_index(s.time, selected_tp) if selected_tp is not None else None
        sel_baseline = None
        sel_sim = None
        sel_delta = None
        sel_pct = None
        if sel_idx is not None:
            if len(s.baseline_values) > sel_idx:
                sel_baseline = s.baseline_values[sel_idx]
            if len(s.sim_values) > sel_idx:
                sel_sim = s.sim_values[sel_idx]
            if sel_baseline is not None and sel_sim is not None:
                sel_delta = sel_sim - sel_baseline
                sel_pct = _pct_delta(sel_baseline, sel_sim)

        series_context.append({
            "series_key": s.series_key,
            "title": s.title,
            "unit": s.unit,
            "time_start": s.time[0],
            "time_end": s.time[-1],
            "baseline_last": b_last,
            "sim_last": s_last,
            "delta_last": delta_last,
            "pct_last": pct_last,
            "selected_time_point": selected_tp,
            "selected_time_baseline": sel_baseline,
            "selected_time_sim": sel_sim,
            "selected_time_delta": sel_delta,
            "selected_time_pct": sel_pct,
            "time": s.time,
            "baseline_values": s.baseline_values,
            "sim_values": s.sim_values,
        })

    params_union = set(req.params.baseline_params.keys()) | set(req.params.sim_params.keys())
    param_changes = []
    changed_only = []
    omitted_technical_params = 0
    for k in sorted(params_union):
        friendly = _to_friendly_label(k)
        if friendly is None:
            omitted_technical_params += 1
            continue
        b = req.params.baseline_params.get(k)
        s = req.params.sim_params.get(k)
        if b is None and s is None:
            continue
        delta = None
        try:
            if b is not None and s is not None:
                delta = s - b
        except Exception:
            delta = None
        param_changes.append({
            "param": friendly,
            "baseline": b,
            "sim": s,
            "delta": delta,
        })
        if delta not in (None, 0):
            changed_only.append({
                "param": friendly,
                "baseline": b,
                "sim": s,
                "delta": delta,
            })

    run_meta_raw = req.run_meta.model_dump()
    run_meta_changed = run_meta_raw.get("changed_params") or []
    sanitized_changed: list[Dict[str, Any]] = []
    for row in run_meta_changed:
        key = row.get("key") if isinstance(row, dict) else None
        friendly = _to_friendly_label(key)
        if friendly is None:
            continue
        sanitized_changed.append({
            "param": friendly,
            "baseline": row.get("baseline") if isinstance(row, dict) else None,
            "sim": row.get("sim") if isinstance(row, dict) else None,
            "delta": row.get("delta") if isinstance(row, dict) else None,
        })
    run_meta_raw["changed_params"] = sanitized_changed

    year = _extract_year_from_question(req.question)
    year_lookup = []
    year_missing = False
    if year:
        for s in req.series:
            idx = _find_time_index(s.time, year)
            if idx is None:
                year_missing = True
                year_lookup.append({
                    "series_key": s.series_key,
                    "title": s.title,
                    "year": year,
                    "available": False,
                })
            else:
                b_val = s.baseline_values[idx] if len(s.baseline_values) > idx else None
                s_val = s.sim_values[idx] if len(s.sim_values) > idx else None
                delta = (s_val - b_val) if (b_val is not None and s_val is not None) else None
                pct = _pct_delta(b_val, s_val) if (b_val is not None and s_val is not None) else None
                year_lookup.append({
                    "series_key": s.series_key,
                    "title": s.title,
                    "year": year,
                    "available": True,
                    "baseline": b_val,
                    "sim": s_val,
                    "delta": delta,
                    "pct": pct,
                })

    return {
        "question": req.question,
        "run_meta": run_meta_raw,
        "series": series_context,
        "param_changes": param_changes,
        "changed_params": changed_only,
        "omitted_technical_params": omitted_technical_params,
        "year_lookup": year_lookup,
        "year_missing": year_missing,
    }


@app.post("/api/chat_graph", response_model=ChatGraphResponse)
def chat_graph(req: ChatGraphRequest):
    lang = (req.language or "mn").strip().lower()
    is_en = lang.startswith("en")
    question_lower = (req.question or "").strip().lower()

    if req.series:
        primary_time = req.series[0].time
        selected_tp = req.run_meta.selected_time_point
        if selected_tp is not None and _find_time_index(primary_time, selected_tp) is None:
            return ChatGraphResponse(error=_strict_time_error(primary_time, selected_tp))

        year = _extract_year_from_question(req.question)
        if year is not None and _find_time_index(primary_time, year) is None:
            return ChatGraphResponse(error=_strict_time_error(primary_time, year))

    year_range = _extract_year_range(req.question)
    if year_range and req.series:
        start_year, end_year = year_range
        s0 = req.series[0]
        start_idx = _find_time_index(s0.time, start_year)
        end_idx = _find_time_index(s0.time, end_year)
        if start_idx is None or end_idx is None:
            return ChatGraphResponse(error=_strict_time_error(s0.time, {"start": start_year, "end": end_year}))
        start_val = s0.time[start_idx]
        end_val = s0.time[end_idx]
        base_growth = _calc_growth_pct(s0.baseline_values, s0.time, start_val, end_val)
        sim_growth = _calc_growth_pct(s0.sim_values, s0.time, start_val, end_val)
        parts = [
            f"{s0.title} ({start_year}-{end_year}) growth rate:"
            if is_en
            else f"{s0.title} ({start_year}–{end_year}) өсөлтийн хувь:"
        ]
        if base_growth is not None:
            parts.append(f"Baseline: {base_growth:.2f}%" if is_en else f"Суурь: {base_growth:.2f}%")
        if sim_growth is not None:
            parts.append(f"Simulation: {sim_growth:.2f}%" if is_en else f"Симуляци: {sim_growth:.2f}%")
        return ChatGraphResponse(reply="; ".join(parts))

    if ("өсөлтийн хувь" in question_lower or "growth rate" in question_lower) and req.series:
        s0 = req.series[0]
        start = s0.time[0] if s0.time else None
        end = s0.time[-1] if s0.time else None
        if start is None or end is None:
            return ChatGraphResponse(reply="No data available." if is_en else "Өгөгдөл хоосон байна.")

        start_val, start_idx, start_exact = _resolve_time_value(s0.time, start)
        end_val, end_idx, end_exact = _resolve_time_value(s0.time, end)
        if start_idx is None or end_idx is None:
            return ChatGraphResponse(reply="Data not found." if is_en else "Өгөгдөл олдсонгүй.")

        base_growth = _calc_growth_pct(s0.baseline_values, s0.time, start_val, end_val)
        sim_growth = _calc_growth_pct(s0.sim_values, s0.time, start_val, end_val)
        parts = [
            f"{s0.title} growth rate ({start_val}-{end_val}):"
            if is_en
            else f"{s0.title} өсөлтийн хувь ({start_val}–{end_val}):"
        ]
        if base_growth is not None:
            parts.append(f"Baseline: {base_growth:.2f}%" if is_en else f"Суурь: {base_growth:.2f}%")
        if sim_growth is not None:
            parts.append(f"Simulation: {sim_growth:.2f}%" if is_en else f"Симуляци: {sim_growth:.2f}%")
        return ChatGraphResponse(reply="; ".join(parts))

    if not settings.OPENAI_API_KEY:
        return ChatGraphResponse(reply="AI API key is not configured." if is_en else "AI API key тохируулаагүй байна.")

    context = _build_chat_context(req)

    try:
        language_instruction = (
            "IMPORTANT: Respond only in English. Do not use Mongolian."
            if is_en
            else "IMPORTANT: Respond only in Mongolian. Do not use English."
        )
        question_label = "Question" if is_en else "Асуулт"
        context_label = "Data context (JSON)" if is_en else "Өгөгдлийн контекст (JSON)"
        prompt = (
            language_instruction
            + "\n\n"
            + CHAT_SYSTEM_PROMPT
            + "\n\n"
            + question_label
            + ": "
            + req.question
            + "\n\n"
            + context_label
            + ":\n"
            + json.dumps(context, ensure_ascii=False)
        )
        text = openai_explain_mn(prompt)
        if is_en and text and _contains_cyrillic(text):
            # Fallback: enforce English output if the first model answer is not in English.
            retry_prompt = (
                "Translate the following answer to clear, natural English. "
                "Return only English text and keep the original meaning.\n\n"
                + text
            )
            translated = openai_explain_mn(retry_prompt)
            if translated:
                text = translated
        if not text:
            return ChatGraphResponse(reply="No data-based answer was generated." if is_en else "Өгөгдөлд суурилсан хариу олдсонгүй.")
        if is_en and _contains_cyrillic(text):
            return ChatGraphResponse(reply="Sorry, I could not generate an English-only answer this time. Please try again.")
        return ChatGraphResponse(reply=text)
    except Exception as e:
        return ChatGraphResponse(reply=f"Failed to generate AI response: {e}" if is_en else f"AI хариу үүсгэхэд алдаа гарлаа: {e}")

