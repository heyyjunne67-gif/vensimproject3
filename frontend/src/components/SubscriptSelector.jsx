import React from "react";

/*
availableSubscripts.outputs[outputKey] = [
  { name: "Аймаг", values: ["Дорнод", ...] },
  ...
]
selection:
  subscripts[outputKey] = { "Аймаг": "Дорнод" }
*/

export default function SubscriptSelector({ outputKey, availableDims, selection, onChange }) {
  if (!availableDims || availableDims.length === 0) return null;

  return (
    <div className="subsel">
      <div className="subselTitle">Subscript сонголт</div>

      {availableDims.map((dim) => {
        const cur = selection?.[dim.name] ?? dim.values[0];
        return (
          <div key={dim.name} className="subselDim">
            <div className="subselDimName">{dim.name}</div>
            <div className="segmented">
              {dim.values.map((v) => {
                const active = v === cur;
                return (
                  <button
                    key={v}
                    className={`segBtn ${active ? "segBtnActive" : ""}`}
                    onClick={() => onChange(outputKey, dim.name, v)}
                    type="button"
                  >
                    {v}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
