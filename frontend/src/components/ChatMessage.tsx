interface ChatMessageProps {
  speaker: "adversary" | "user";
  text: string;
}

export default function ChatMessage({ speaker, text }: ChatMessageProps) {
  const isUser = speaker === "user";

  return (
    <div
      className={`max-w-[75%] animate-fade-in-up ${
        isUser ? "ml-auto text-right" : "mr-auto"
      }`}
    >
      <span
        className={`mb-1 inline-block text-[0.625rem] font-bold uppercase tracking-widest ${
          isUser ? "text-emerald-400" : "text-red-400"
        }`}
      >
        {isUser ? "YOU" : "THEM"}
      </span>

      <div
        className={`px-4 py-3 text-[0.9375rem] leading-relaxed text-slate-200 ${
          isUser
            ? "rounded-2xl rounded-br-sm bg-indigo-500/10"
            : "rounded-2xl rounded-bl-sm bg-[#1C2536]"
        }`}
      >
        {text}
      </div>
    </div>
  );
}
