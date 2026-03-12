import React, { useEffect, useState } from "react";

export default function ChatbotWidget({ language = "mn" }) {
  const [open, setOpen] = useState(false);
  const [showGreeting, setShowGreeting] = useState(true);
  const isEn = language === "en";

  useEffect(() => {
    const timer = setTimeout(() => setShowGreeting(false), 6000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="fixed bottom-6 right-6 z-[9999]">
      <div className="flex items-center gap-3">
        {showGreeting && !open && (
          <div className="rounded-2xl bg-white px-4 py-2 text-sm text-gray-800 shadow-lg">
            {isEn ? "Hello. How can I help you?" : "Сайн байна уу. Танд юугаар туслах вэ?"}
          </div>
        )}

        <div className="relative">
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-blue-500 text-white shadow-xl transition-transform duration-150 hover:scale-105"
            type="button"
            aria-label="Open chat"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-6 w-6"
            >
              <path d="M7 8h10a1 1 0 110 2H7a1 1 0 110-2zm0 4h6a1 1 0 110 2H7a1 1 0 110-2zm5-10a9 9 0 00-9 9v7a1 1 0 001.447.894L7.2 18H12a9 9 0 000-18z" />
            </svg>
          </button>
          <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full border-2 border-white bg-emerald-400" />
        </div>
      </div>

      {open && (
        <div className="mb-4 w-[320px] max-w-[85vw] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 text-white shadow-2xl transition-opacity duration-200">
          <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
            <div className="text-sm font-semibold">{isEn ? "Chatbot" : "Чатбот"}</div>
            <button
              onClick={() => setOpen(false)}
              className="rounded-full px-2 py-1 text-xs text-slate-300 hover:text-white"
              type="button"
            >
              {isEn ? "Close" : "Хаах"}
            </button>
          </div>
          <div className="px-4 py-4 text-sm text-slate-300">
            {isEn ? "Ready to help you." : "Танд туслахад бэлэн байна."}
          </div>
          <div className="border-t border-white/10 px-4 py-3">
            <input
              className="w-full rounded-xl bg-slate-800 px-3 py-2 text-sm text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder={isEn ? "Type a message..." : "Зурвас бичнэ үү..."}
              type="text"
            />
          </div>
        </div>
      )}
    </div>
  );
}
