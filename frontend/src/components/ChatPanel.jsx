import React, { useState } from "react";

export default function ChatPanel({
  messages,
  loading,
  error,
  onSend,
  selectedSeriesTitle,
  selectedTimePoint,
  selectedSubscripts,
  appliedSubscripts,
  changedParams,
  language = "mn"
}) {
  const [input, setInput] = useState("");
  const isEn = language === "en";

  const subscriptText = (subs) => {
    if (!subs || Object.keys(subs).length === 0) return "-";
    return Object.entries(subs)
      .map(([k, v]) => `${k}=${v}`)
      .join(", ");
  };

  const changedText = Array.isArray(changedParams) && changedParams.length > 0
    ? changedParams.map((p) => {
      const key = p.key || p.param || "-";
      const baseline = p.baseline ?? p.requested;
      const sim = p.sim ?? p.applied;
      const delta = p.delta === null || p.delta === undefined ? "" : ` (Δ ${p.delta})`;
      return `${key}: ${baseline} → ${sim}${delta}`;
    }).join("; ")
    : "-";

  function handleSubmit(e) {
    e.preventDefault();
    const q = input.trim();
    if (!q || loading) return;
    onSend(q);
    setInput("");
  }

  return (
    <div className="card chatPanel">
      <div className="cardTitle">{isEn ? "Chat Analysis" : "Чатбот анализ"}</div>
      <div className="cardDesc">
        {isEn ? "Explains based on the selected chart data." : "Сонгосон графикийн өгөгдөл дээр тулгуурлан тайлбарлана."}
      </div>

      <div className="chatMeta">
        <div>{isEn ? "Active indicator" : "Идэвхтэй үзүүлэлт"}: <b>{selectedSeriesTitle || "-"}</b></div>
        <div>{isEn ? "Selected time" : "Сонгосон хугацаа"}: <b>{selectedTimePoint ?? "-"}</b></div>
        <div>{isEn ? "Changed parameters" : "Өөрчилсөн параметрүүд"}: <b>{changedText}</b></div>
      </div>

      <div className="chatList">
        {messages.length === 0 && (
          <div className="chatEmpty">{isEn ? "Type your question and send." : "Асуултаа бичээд илгээнэ үү."}</div>
        )}
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`chatMsg ${m.role === "user" ? "chatMsgUser" : "chatMsgAssistant"}`}
          >
            {m.text}
          </div>
        ))}
      </div>

      {error && <div className="errorText">{error}</div>}

      <form className="chatInputRow" onSubmit={handleSubmit}>
        <input
          className="chatInput"
          placeholder={isEn ? "Example: What is the growth rate?" : "Жишээ: Өсөлтийн хувь хэд вэ?"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button className="btnPrimary" type="submit" disabled={loading || !input.trim()}>
          {loading ? (isEn ? "Sending..." : "Илгээж байна...") : (isEn ? "Send" : "Илгээх")}
        </button>
      </form>
    </div>
  );
}
