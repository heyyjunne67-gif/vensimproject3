import React from "react";

const PARAM_LABELS_EN = {
  repro_rate: "Pasture livestock reproduction rate",
  slaughter_share: "Share of livestock slaughtered for demand",
  initial_herd: "Initial pasture livestock population",
  sold_used_share: "Share of livestock sold and consumed",
  disaster_impact: "Disaster impact on livestock regeneration",
  disaster_first_year: "First year of disaster occurrence",
  disaster_freq: "Disaster frequency"
};

function toEnglishUnit(unit) {
  if (unit === "толгой") return "head";
  if (unit === "жил") return "year";
  if (unit === "жил тутам") return "per year";
  return unit;
}

function formatValue(s, v, language) {
  const unit = language === "en" ? (s.unit_en || toEnglishUnit(s.unit_mn)) : s.unit_mn;
  if (s.as_percent) {
    const percentValue = v <= 1 ? v * 100 : v;
    return `${Math.round(percentValue)} ${unit}`;
  }
  if (s.unit_mn === "толгой") {
    return `${Math.round(v).toLocaleString()} ${unit}`;
  }
  return `${v} ${unit}`;
}

function csvEscape(value) {
  if (value === null || value === undefined) return "";
  const s = String(value);
  if (s.includes(",") || s.includes("\n") || s.includes('"')) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function buildCsv(series, outputs, mode) {
  if (!series?.time?.length) return "";
  const header = ["time", ...outputs.map((o) => o.key)].join(",");
  const rows = series.time.map((t, i) => {
    const cols = [csvEscape(t)];
    for (const o of outputs) {
      const arr = series?.[mode]?.[o.key] || [];
      cols.push(csvEscape(arr[i]));
    }
    return cols.join(",");
  });
  return [header, ...rows].join("\n");
}

function downloadCsv(series, outputs, mode, filename) {
  const csv = buildCsv(series, outputs, mode);
  if (!csv) return;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function SliderPanel({ sliders, values, onChange, onRun, onReset, running, series, outputs, language = "mn" }) {
  const canDownload = !!series?.time?.length;
  const sliderItems = sliders || [];
  const isEn = language === "en";

  function setOne(key, value) {
    onChange(key, value);
  }

  return (
    <div className="card">
      <div>
        <div className="cardTitle">{isEn ? "Parameters" : "Параметрүүд"}</div>
        <div className="cardDesc">
          {isEn ? "Sliders are auto-built from model constants and limits." : "Slider-ууд model-ийн Constant + limits-ээс автоматаар үүснэ."}
        </div>
        <div className="smallHint">{isEn ? `Total ${sliderItems.length} parameters` : `Нийт ${sliderItems.length} параметр`}</div>
      </div>

      <div className="sliderScroll">
        <div className="sliderList">
          {sliderItems.map((s) => {
            const v = values[s.key] ?? s.default;
            return (
              <div className="sliderItem" key={s.key}>
                <div className="sliderTop">
                  <div className="sliderLabel">{isEn ? (s.label_en || s.label_mn) : s.label_mn}</div>
                  <div className="sliderValue">{formatValue(s, v, language)}</div>
                </div>

                  <input
                    className="slider"
                    type="range"
                    min={s.min}
                    max={s.max}
                    step={s.step}
                    value={v}
                    id={s.key}
                    name={s.key}
                    onChange={(e) => setOne(s.key, Number(e.target.value))}
                />
                <div className="sliderMinMax">
                  <span>min={s.min}</span>
                  <span>max={s.max}</span>
                  <span>step={s.step}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="btnRow">
        <button className="btnPrimary" onClick={onRun} disabled={running}>
          {running ? (isEn ? "Running..." : "Ажиллаж байна...") : "Run Simulation"}
        </button>
        <button className="btnGhost" onClick={onReset} disabled={running}>
          {isEn ? "Reset / Initial values" : "Reset / Анхны утга"}
        </button>
      </div>

      <div className="btnRow">
        <button
          className="btnGhost"
          onClick={() => downloadCsv(series, outputs, "baseline", "baseline.csv")}
          disabled={!canDownload}
        >
          {isEn ? "Download CSV (baseline)" : "CSV татах (суурь)"}
        </button>
        <button
          className="btnGhost"
          onClick={() => downloadCsv(series, outputs, "simulation", "simulation.csv")}
          disabled={!canDownload}
        >
          {isEn ? "Download CSV (simulation)" : "CSV татах (симуляци)"}
        </button>
      </div>

      <div className="legendHint">
        <span className="dot dotBlue"></span> {isEn ? "Baseline" : "Анхны (суурь)"}
        <span className="dot dotRed"></span> {isEn ? "Simulation" : "Симуляци (шинэ)"}
      </div>
    </div>
  );
}
