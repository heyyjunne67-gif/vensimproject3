import { useCallback, useState } from "react";

export function useChat(onSend, language = "mn") {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const resetMessages = useCallback(() => {
    setMessages([]);
    setError("");
  }, []);

  const sendMessage = useCallback(
    async (question) => {
      const q = (question || "").trim();
      if (!q) return;

      setMessages((prev) => [...prev, { role: "user", text: q }]);
      setLoading(true);
      setError("");
      try {
        const reply = await onSend(q);
        setMessages((prev) => [...prev, { role: "assistant", text: reply }]);
      } catch (e) {
        const fallbackError = language === "en" ? "Failed to get chatbot response" : "Чатбот хариу авахад алдаа гарлаа";
        const fallbackAssistant = language === "en" ? "Sorry, an error occurred." : "Уучлаарай, алдаа гарлаа.";
        setError(e?.message || fallbackError);
        setMessages((prev) => [
          ...prev,
          { role: "assistant", text: e?.message || fallbackAssistant }
        ]);
      } finally {
        setLoading(false);
      }
    },
    [onSend, language]
  );

  return { messages, loading, error, sendMessage, resetMessages };
}
