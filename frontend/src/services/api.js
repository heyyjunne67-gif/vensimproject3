const API_BASE = "https://vensimproject3.onrender.com";
const ENV_API_BASE = import.meta.env.VITE_API_BASE;

function getApiBases() {
  const bases = [];
  const preferredBase = (ENV_API_BASE || API_BASE || "").replace(/\/+$/, "");
  const isStaleLocal8001 = /^https?:\/\/(localhost|127\.0\.0\.1):8001$/i.test(preferredBase);
  if (preferredBase && !isStaleLocal8001) bases.push(preferredBase);
  if (typeof window !== "undefined") {
    bases.push(`${window.location.protocol}//${window.location.hostname}:8011`);
  }
  bases.push("http://localhost:8011");

  const normalized = [];
  for (const base of bases) {
    const clean = (base || "").replace(/\/+$/, "");
    if (!clean) continue;
    if (!normalized.includes(clean)) normalized.push(clean);
  }
  return normalized;
}

function isNetworkFetchError(err) {
  const msg = String(err?.message || err || "").toLowerCase();
  return msg.includes("failed to fetch") || msg.includes("networkerror") || msg.includes("load failed");
}

async function requestJson(path, options, fallbackMessage) {
  const bases = getApiBases();
  let lastError = null;

  for (const base of bases) {
    try {
      const res = await fetch(`${base}${path}`, options);
      if (!res.ok) {
        await parseError(res, fallbackMessage);
      }
      return await res.json();
    } catch (e) {
      lastError = e;
      if (isNetworkFetchError(e)) {
        continue;
      }
      throw e;
    }
  }

  throw lastError || new Error(fallbackMessage);
}

async function parseError(res, fallbackMessage) {
  let payload = null;
  try {
    payload = await res.json();
  } catch {
    payload = null;
  }
  const detail = payload?.detail;
  if (typeof detail === "string" && detail.trim()) {
    throw new Error(detail);
  }
  if (detail && typeof detail === "object") {
    throw new Error(detail.message || fallbackMessage);
  }
  throw new Error(payload?.message || fallbackMessage);
}

function fixMojibake(value) {
  if (typeof value !== "string") return value;
  if (!/[ÃÐÑ]/.test(value)) return value;
  try {
    const bytes = Uint8Array.from(value, (c) => c.charCodeAt(0));
    return new TextDecoder("utf-8").decode(bytes);
  } catch {
    return value;
  }
}

function normalizeText(obj) {
  if (Array.isArray(obj)) return obj.map(normalizeText);
  if (obj && typeof obj === "object") {
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      out[k] = normalizeText(v);
    }
    return out;
  }
  return fixMojibake(obj);
}

export async function apiGetConfig() {
  const data = await requestJson("/api/config", undefined, "Тохиргоо татахад алдаа гарлаа");
  return normalizeText(data);
}

export async function apiSimulate(payload) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);
  try {
    return await requestJson("/api/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal
    }, "Симуляци хийхэд алдаа гарлаа");
  } catch (e) {
    if (e?.name === "AbortError") {
      throw new Error("Симуляци хэт удаж байна (120 сек). Параметрийн өөрчлөлтөө багасгаад дахин оролдоно уу.");
    }
    throw e;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function apiReset(payload) {
  return await requestJson("/api/reset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }, "Reset хийхэд алдаа гарлаа");
}

export async function apiExplain(payload) {
  return await requestJson("/api/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }, "AI тайлбар авахад алдаа гарлаа");
}

export async function apiChatGraph(payload) {
  const body = await requestJson("/api/chat_graph", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }, "Чатбот хариу авахад алдаа гарлаа");
  if (body?.error?.message) {
    const range = body?.error?.valid_time_range;
    const rangeText = range ? ` (valid: ${range.start} - ${range.end})` : "";
    throw new Error(`${body.error.message}${rangeText}`);
  }
  return body;
}

