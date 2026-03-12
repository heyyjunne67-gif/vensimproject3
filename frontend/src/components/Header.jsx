import React from "react";

export default function Header({ title, subtitle, modelReady, language = "mn", onToggleLanguage }) {
  const statusText = !modelReady ? "MODEL ERROR" : "MODEL MODE";
  const statusClass = !modelReady ? "badgeWarn" : "badgeOk";
  const languageLabel = language === "en" ? "EN" : "MN";
  const switchLabel = language === "en" ? "Монгол" : "English";

  return (
    <div className="header">
      <div>
        <div className="title">{title}</div>
        <div className="subtitle">{subtitle}</div>
      </div>
      <div className="badgeRow">
        <span className={`badge ${statusClass}`}>
          {statusText}
        </span>
        <button className="btnGhost" type="button" onClick={onToggleLanguage}>
          {languageLabel} / {switchLabel}
        </button>
      </div>
    </div>
  );
}
