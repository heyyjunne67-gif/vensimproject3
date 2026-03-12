from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any


class SliderDef(BaseModel):
    key: str
    label_mn: str
    label_en: Optional[str] = None
    unit_mn: str
    unit_en: Optional[str] = None
    min: float
    max: float
    step: float
    default: float
    as_percent: bool = False  # True бол UI дээр 0-100% гэж харуулах боломжтой


class DimDef(BaseModel):
    name: str
    values: List[str]


class AvailableSubscripts(BaseModel):
    # output_key -> dims
    outputs: Dict[str, List[DimDef]] = Field(default_factory=dict)


class SeriesPayload(BaseModel):
    time: List[float]
    # baseline/simulation series per output (already filtered by chosen subscripts)
    baseline: Dict[str, List[float]]
    simulation: Dict[str, List[float]]
    # transparency: what backend received and actually sanitized before model run
    received_params: Dict[str, float] = Field(default_factory=dict)
    sanitized_params: Dict[str, float] = Field(default_factory=dict)
    # for transparency: which subscripts were used to filter each output
    applied_subscripts: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    applied_overrides: List[Dict[str, Any]] = Field(default_factory=list)
    ignored_overrides: List[Dict[str, Any]] = Field(default_factory=list)


class ConfigPayload(BaseModel):
    ui_title_mn: str
    ui_subtitle_mn: str
    outputs_ui_mn: Dict[str, str]  # output_key -> UI label
    ai_sector_options: List[str] = Field(default_factory=list)
    sliders: List[SliderDef]
    variable_map: Dict[str, str]   # output_key(ui) -> vensim variable name
    param_map: Dict[str, str]      # slider key -> vensim parameter name
    available_subscripts: AvailableSubscripts
    model_ready: bool
    model_error: Optional[str] = None
    time_range: Dict[str, Optional[float]] = Field(default_factory=dict)


class SimulateRequest(BaseModel):
    params: Dict[str, float] = Field(default_factory=dict)
    subscripts: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    # subscripts format:
    # {
    #   "herd_total": {"Аймаг": "Дорнод"},
    #   "births": {"Аймаг": "Дорнод"}
    # }


class ExplainRequest(BaseModel):
    # frontend-оос бэлдсэн товч статистик
    params_used: Dict[str, float] = Field(default_factory=dict)
    stats: Dict[str, Any] = Field(default_factory=dict)
    selected_sectors: List[str] = Field(default_factory=list)
    sector_labels: Dict[str, str] = Field(default_factory=dict)
    variable_map: Dict[str, str] = Field(default_factory=dict)
    baseline_params: Dict[str, float] = Field(default_factory=dict)
    language: str = "mn"
    series: Optional[SeriesPayload] = None
    # stats example:
    # {
    #   "herd_total": {"baseline_last": 100, "sim_last": 120, "pct_change_last": 20.0, ...},
    #   ...
    # }


class ExplainResponse(BaseModel):
    text_mn: str


class ChatGraphRunMeta(BaseModel):
    selected_series_key: Optional[str] = None
    selected_series_title: Optional[str] = None
    selected_time_point: Optional[Any] = None
    selected_time_window: Optional[Dict[str, Any]] = None
    selected_subscripts: Dict[str, str] = Field(default_factory=dict)
    applied_subscripts: Dict[str, str] = Field(default_factory=dict)
    changed_params: List[Dict[str, Any]] = Field(default_factory=list)


class ChatGraphParams(BaseModel):
    baseline_params: Dict[str, Any] = Field(default_factory=dict)
    sim_params: Dict[str, Any] = Field(default_factory=dict)


class ChatGraphSeries(BaseModel):
    series_key: str
    title: str
    unit: Optional[str] = None
    time: List[Any]
    baseline_values: List[float]
    sim_values: List[float]


class ChatGraphRequest(BaseModel):
    question: str
    language: str = "mn"
    run_meta: ChatGraphRunMeta
    params: ChatGraphParams
    series: List[ChatGraphSeries]


class ChatGraphResponse(BaseModel):
    reply: str = ""
    error: Optional[Dict[str, Any]] = None
