import React, { useEffect, useMemo, useState } from "react";
import Header from "./components/Header.jsx";
import SliderPanel from "./components/SliderPanel.jsx";
import ChartCard from "./components/ChartCard.jsx";
import AiExplain from "./components/AiExplain.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import ChatbotWidget from "./components/ChatbotWidget.jsx";
import { useChat } from "./hooks/useChat.js";
import { apiGetConfig, apiSimulate, apiReset, apiExplain, apiChatGraph } from "./services/api.js";

const OUTPUT_LABELS_EN = {
  total_ghg: "Total Greenhouse Gas",
  energy_ghg: "Energy Sector GHG",
  transport_ghg: "Transport Sector GHG",
  agri_ghg: "Agriculture Sector GHG",
  forest_sink: "Forest Carbon Sink"
};

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function pct(a, b) {
  if (a === 0 || a === null || a === undefined) return null;
  return ((b - a) / a) * 100;
}

function summarizeOne(time, baseline, simulation, language = "mn") {
  if (!time?.length || !baseline?.length || !simulation?.length) return {};
  const b0 = baseline[0], bN = baseline[baseline.length - 1];
  const s0 = simulation[0], sN = simulation[simulation.length - 1];

  const bMin = Math.min(...baseline), bMax = Math.max(...baseline);
  const sMin = Math.min(...simulation), sMax = Math.max(...simulation);

  return {
    time_start: time[0],
    time_end: time[time.length - 1],
    baseline_last: bN,
    sim_last: sN,
    pct_change_last: pct(bN, sN),
    baseline_min: bMin,
    baseline_max: bMax,
    sim_min: sMin,
    sim_max: sMax,
    baseline_trend: bN > b0 ? (language === "en" ? "increasing" : "өсөх") : (language === "en" ? "decreasing/stable" : "буурах/тогтвортой"),
    sim_trend: sN > s0 ? (language === "en" ? "increasing" : "өсөх") : (language === "en" ? "decreasing/stable" : "буурах/тогтвортой")
  };
}

function downsampleSeries(time, baseline, simulation, maxPoints = 180) {
  const len = time?.length || 0;
  if (len <= maxPoints) {
    return { time, baseline, simulation };
  }
  const step = Math.ceil(len / maxPoints);
  const t = [];
  const b = [];
  const s = [];
  for (let i = 0; i < len; i += step) {
    t.push(time[i]);
    b.push(baseline[i]);
    s.push(simulation[i]);
  }
  if (t[t.length - 1] !== time[len - 1]) {
    t.push(time[len - 1]);
    b.push(baseline[len - 1]);
    s.push(simulation[len - 1]);
  }
  return { time: t, baseline: b, simulation: s };
}

function diffParams(baseParams, params) {
  const changes = [];
  const keys = new Set([...(Object.keys(baseParams || {})), ...(Object.keys(params || {}))]);
  for (const key of Array.from(keys)) {
    const b = baseParams?.[key];
    const s = params?.[key];
    if (b === s) continue;
    const delta = (typeof b === "number" && typeof s === "number") ? (s - b) : null;
    changes.push({ key, baseline: b, sim: s, delta });
  }
  return changes;
}

export default function App() {
  const [config, setConfig] = useState(null);
  const [params, setParams] = useState({});
  const [baseParams, setBaseParams] = useState({});
  const [subscripts, setSubscripts] = useState({});
  const [series, setSeries] = useState(null);
  const [running, setRunning] = useState(false);
  const [language, setLanguage] = useState("mn");

  const [aiText, setAiText] = useState("");
  const [aiLoading, setAiLoading] = useState(false);
  const [selectedExplainSectors, setSelectedExplainSectors] = useState([]);
  const [activeSeriesKey, setActiveSeriesKey] = useState(null);
  const [selectedTimePoint, setSelectedTimePoint] = useState(null);
  const [runWarning, setRunWarning] = useState("");

  const isEn = language === "en";

  useEffect(() => {
    (async () => {
      let cfg = null;
      let lastErr = null;
      for (let i = 0; i < 5; i += 1) {
        try {
          cfg = await apiGetConfig();
          break;
        } catch (e) {
          lastErr = e;
          await sleep(700);
        }
      }
      if (!cfg) throw lastErr || new Error(isEn ? "Could not load config from backend." : "Backend-ээс config авч чадсангүй.");
      setConfig(cfg);

      const initParams = {};
      for (const s of cfg.sliders) initParams[s.key] = s.default;
      setParams(initParams);
      setBaseParams(initParams);

      const initSubs = {};
      const outputs = cfg.available_subscripts?.outputs || {};
      const firstOutKey = Object.keys(outputs)[0];
      const dims = firstOutKey ? (outputs[firstOutKey] || []) : [];
      if (dims.length > 0) {
        for (const d of dims) initSubs[d.name] = d.values[0];
      }
      setSubscripts(initSubs);

      const resetPayload = {
        params: initParams,
        subscripts: Object.fromEntries(
          outputs ? Object.keys(outputs).map((k) => [k, initSubs]) : []
        )
      };
      let sData = null;
      let resetErr = null;
      for (let i = 0; i < 5; i += 1) {
        try {
          sData = await apiReset(resetPayload);
          break;
        } catch (e) {
          resetErr = e;
          await sleep(700);
        }
      }
      if (!sData) throw resetErr || new Error(isEn ? "Could not load baseline from backend." : "Backend-ээс baseline авч чадсангүй.");
      setSeries(sData);
      setRunWarning("");
      setActiveSeriesKey(Object.keys(outputs)[0] || null);
    })().catch((e) => {
      console.error(e);
      alert(isEn ? `App initialization error: ${e?.message || "Unknown error"}` : `Апп эхлүүлэхэд алдаа гарлаа: ${e?.message || "Тодорхойгүй алдаа"}`);
    });
  }, []);

  const outputs = useMemo(() => {
    if (!config) return [];
    const labels = config.outputs_ui_mn || {};
    const orderedKeys = ["total_ghg", "energy_ghg", "transport_ghg", "agri_ghg", "forest_sink"];
    const ordered = orderedKeys
      .filter((key) => labels[key])
      .map((key) => ({ key, title: isEn ? (OUTPUT_LABELS_EN[key] || labels[key]) : labels[key] }));
    const rest = Object.entries(labels)
      .filter(([key]) => !orderedKeys.includes(key))
      .map(([key, title]) => ({ key, title: isEn ? (OUTPUT_LABELS_EN[key] || title) : title }));
    return [...ordered, ...rest];
  }, [config, isEn]);

  const aiSectorOptions = useMemo(() => config?.ai_sector_options || [], [config]);

  useEffect(() => {
    if (!aiSectorOptions.length) return;
    setSelectedExplainSectors((prev) => {
      const kept = prev.filter((name) => aiSectorOptions.includes(name));
      return kept.length ? kept : aiSectorOptions.slice(0, Math.min(5, aiSectorOptions.length));
    });
  }, [aiSectorOptions]);

  const chatSeriesKey = outputs.find((o) => o.key === "herd_total_total")?.key || outputs[0]?.key || null;
  const chatSeriesTitle = outputs.find((o) => o.key === chatSeriesKey)?.title || "";
  const changedParams = useMemo(() => diffParams(baseParams, params), [baseParams, params]);
  const ignoredOverrides = series?.ignored_overrides || [];
  const appliedOverrides = series?.applied_overrides || [];
  const chatAppliedSubscripts = series?.applied_subscripts?.[chatSeriesKey] || subscripts || {};

  const { messages, loading: chatLoading, error: chatError, sendMessage, resetMessages } = useChat(async (question) => {
    const seriesKey = chatSeriesKey || activeSeriesKey || outputs[0]?.key || null;
    const selectedSeries = outputs.find((o) => o.key === seriesKey) || outputs[0];
    const time = series?.time || [];
    const baseline = series?.baseline?.[seriesKey] || [];
    const simulation = series?.simulation?.[seriesKey] || [];
    const wantsYear = /(?:19|20)\d{2}/.test(question);
    const ds = wantsYear ? { time, baseline, simulation } : downsampleSeries(time, baseline, simulation, 180);

    const payload = {
      question,
      language,
      run_meta: {
        selected_series_key: seriesKey,
        selected_series_title: selectedSeries?.title || "",
        selected_time_point: selectedTimePoint ?? null,
        selected_time_window: null,
        selected_subscripts: subscripts || {},
        applied_subscripts: chatAppliedSubscripts || {},
        changed_params: changedParams || []
      },
      params: {
        baseline_params: baseParams,
        sim_params: params
      },
      series: [
        {
          series_key: seriesKey || "unknown",
          title: selectedSeries?.title || "",
          unit: null,
          time: ds.time || [],
          baseline_values: ds.baseline || [],
          sim_values: ds.simulation || []
        }
      ]
    };

    const res = await apiChatGraph(payload);
    return res.reply || "";
  }, language);

  function handleParamChange(key, value) {
    setParams((p) => ({ ...p, [key]: value }));
  }

  async function runSimulation() {
    setRunning(true);
    setAiText("");
    resetMessages();
    try {
      const outputsMap = config?.available_subscripts?.outputs || {};
      const defaults = {};
      for (const s of config.sliders) defaults[s.key] = s.default;

      const changed = {};
      for (const key of Object.keys(params)) {
        if (params[key] !== defaults[key]) changed[key] = params[key];
      }

      const payload = {
        params: changed,
        subscripts: Object.fromEntries(
          Object.keys(outputsMap).map((k) => [k, subscripts])
        )
      };

      const sData = Object.keys(changed).length === 0
        ? await apiReset(payload)
        : await apiSimulate(payload);

      setSeries(sData);
      const ignored = sData?.ignored_overrides || [];
      const received = sData?.received_params || {};
      const sanitized = sData?.sanitized_params || {};
      const requestedKeys = Object.keys(changed);
      const notReceived = requestedKeys.filter((k) => !(k in received));
      const notSanitized = requestedKeys.filter((k) => !(k in sanitized));

      const warnings = [];
      if (ignored.length > 0) {
        warnings.push(
          isEn
            ? `Some overrides were ignored: ${ignored.map((x) => x.key).join(", ")}`
            : `Зарим override үл хэрэгжсэн: ${ignored.map((x) => x.key).join(", ")}`
        );
      }
      if (notReceived.length > 0) {
        warnings.push(
          isEn
            ? `Parameters not received by backend: ${notReceived.join(", ")}`
            : `Backend хүлээж аваагүй параметр: ${notReceived.join(", ")}`
        );
      }
      if (notSanitized.length > 0) {
        warnings.push(
          isEn
            ? `Parameters dropped during backend sanitization: ${notSanitized.join(", ")}`
            : `Backend цэвэрлэгээнд хасагдсан параметр: ${notSanitized.join(", ")}`
        );
      }

      setRunWarning(warnings.join(" | "));
    } catch (e) {
      console.error(e);
      alert(e?.message || (isEn ? "Simulation failed." : "Симуляци хийхэд алдаа гарлаа."));
    } finally {
      setRunning(false);
    }
  }

  async function runExplain() {
    if (!series?.time?.length) {
      alert(isEn ? "Please run simulation first." : "Эхлээд симуляци ажиллуулна уу.");
      return;
    }

    const hasSim = outputs.some((o) => (series.simulation?.[o.key] || []).length > 0);
    if (!hasSim) {
      alert(isEn ? "Simulation has not been run." : "Симуляци ажиллуулаагүй байна.");
      return;
    }

    const selectedSectors = selectedExplainSectors.filter((name) => aiSectorOptions.includes(name));
    if (!selectedSectors.length) {
      alert(isEn ? "Please select sectors to explain." : "Тайлбарлах сектороо сонгоно уу.");
      return;
    }

    setAiLoading(true);
    setAiText("");
    try {
      const stats = {};
      for (const o of outputs) {
        const baseArr = series.baseline?.[o.key] || [];
        const simArr = series.simulation?.[o.key] || [];
        if (simArr.length > 0) {
          stats[o.key] = summarizeOne(series.time, baseArr, simArr, language);
        }
      }

      const sectorLabels = Object.fromEntries(outputs.map((o) => [o.key, o.title]));
      const exp = await apiExplain({
        params_used: params,
        baseline_params: baseParams,
        stats,
        series,
        language,
        selected_sectors: selectedSectors,
        sector_labels: sectorLabels,
        variable_map: config?.variable_map || {}
      });
      setAiText(exp.text_mn || "");
    } catch (e) {
      console.error(e);
      setAiText(isEn ? "Failed to generate AI explanation" : "AI тайлбар үүсгэхэд алдаа гарлаа");
    } finally {
      setAiLoading(false);
    }
  }

  async function doReset() {
    setRunning(true);
    setAiText("");
    resetMessages();
    try {
      const initParams = {};
      for (const s of config.sliders) initParams[s.key] = s.default;
      setParams(initParams);
      setBaseParams(initParams);
      setRunWarning("");

      const outputsMap = config?.available_subscripts?.outputs || {};
      const sData = await apiReset({
        params: initParams,
        subscripts: Object.fromEntries(
          Object.keys(outputsMap).map((k) => [k, subscripts])
        )
      });
      setSeries(sData);
    } catch (e) {
      console.error(e);
      alert(e?.message || (isEn ? "Reset failed." : "Reset хийхэд алдаа гарлаа."));
    } finally {
      setRunning(false);
    }
  }

  if (!config || !series) {
    return (
      <div className="appShell">
        <div className="loading">{isEn ? "Loading..." : "Ачаалж байна..."}</div>
      </div>
    );
  }

  const timeLabel = "TIME";
  const title = isEn ? "Vensim → Python (PySD) Web Simulation" : config.ui_title_mn;
  const subtitle = isEn ? "" : config.ui_subtitle_mn;

  return (
    <>
      <div className="appShell">
        <Header
          title={title}
          subtitle={subtitle}
          modelReady={config.model_ready}
          modelError={config.model_error}
          language={language}
          onToggleLanguage={() => setLanguage((prev) => (prev === "en" ? "mn" : "en"))}
        />

        {(!config.model_ready || runWarning) && (
          <div className="warningBanner">
            {!config.model_ready && config.model_error && <div>{isEn ? "⚠ Model error" : "⚠ Model алдаа"}: {config.model_error}</div>}
            {runWarning && <div>⚠ {runWarning}</div>}
          </div>
        )}

        <div className="layout">
          <div className="leftCol">
            <SliderPanel
              sliders={config.sliders}
              values={params}
              onChange={handleParamChange}
              onRun={runSimulation}
              onReset={doReset}
              running={running}
              series={series}
              outputs={outputs}
              language={language}
            />

            <AiExplain
              text={aiText}
              loading={aiLoading}
              onExplain={runExplain}
              disabled={running}
              sectors={aiSectorOptions}
              selectedSectors={selectedExplainSectors}
              onToggleSector={(name) => {
                setSelectedExplainSectors((prev) => (
                  prev.includes(name)
                    ? prev.filter((s) => s !== name)
                    : [...prev, name]
                ));
              }}
              onSelectAllSectors={() => setSelectedExplainSectors(aiSectorOptions)}
              onClearSectors={() => setSelectedExplainSectors([])}
              language={language}
            />
          </div>

          <div className="rightCol">
            <div className="grid">
              {outputs.map((o, idx) => (
                <div className={`gridItem ${idx === 0 ? "gridItemLarge" : ""}`} key={o.key}>
                  <ChartCard
                    seriesKey={o.key}
                    title={o.title}
                    time={series.time}
                    baseline={series.baseline?.[o.key] || []}
                    simulation={series.simulation?.[o.key] || []}
                    availableDims={[]}
                    subSelection={{}}
                    onSubChange={() => {}}
                    active={activeSeriesKey === o.key}
                    onActivate={(key) => setActiveSeriesKey(key)}
                    onPointSelect={(key, idx2) => {
                      setActiveSeriesKey(key);
                      const tp = series?.time?.[idx2];
                      setSelectedTimePoint(tp ?? null);
                    }}
                    footerText={isEn ? `X axis: ${timeLabel} (depends on model unit)` : `X тэнхлэг: ${timeLabel} (модель дээрх нэгжээс хамаарна)`}
                    language={language}
                  />
                </div>
              ))}
            </div>

            <div className="footnote">
              {isEn ? "Blue = Baseline, Red = Simulation" : "Цэнхэр = Анхны (суурь), Улаан = Симуляци (шинэ)"}
            </div>

            <ChatPanel
              messages={messages}
              loading={chatLoading}
              error={chatError}
              onSend={sendMessage}
              selectedSeriesTitle={chatSeriesTitle}
              selectedTimePoint={selectedTimePoint}
              selectedSubscripts={subscripts}
              appliedSubscripts={chatAppliedSubscripts}
              changedParams={appliedOverrides.length ? appliedOverrides : changedParams}
              language={language}
            />
          </div>
        </div>
      </div>
      <ChatbotWidget language={language} />
    </>
  );
}
