"use client";

import { useEffect, useState } from "react";

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "clear", "0", "back"];

/** Teclado numerico grande: se usa a pie de mesa con una sola mano. */
export function PinPad({
  value,
  onChange,
  onComplete,
  disabled = false,
}: {
  value: string;
  onChange: (next: string) => void;
  onComplete?: (pin: string) => void;
  disabled?: boolean;
}) {
  const [shake, setShake] = useState(false);

  useEffect(() => {
    if (value.length === 4 && onComplete) onComplete(value);
  }, [value, onComplete]);

  const press = (key: string) => {
    if (disabled) return;
    if (key === "clear") return onChange("");
    if (key === "back") return onChange(value.slice(0, -1));
    if (value.length >= 4) {
      setShake(true);
      window.setTimeout(() => setShake(false), 300);
      return;
    }
    onChange(value + key);
  };

  return (
    <div className="space-y-4">
      <div className={`flex justify-center gap-3 ${shake ? "animate-pulse" : ""}`}>
        {[0, 1, 2, 3].map((index) => (
          <div
            key={index}
            className={`h-14 w-12 rounded-xl border-2 text-center text-2xl font-bold leading-[3rem] ${
              value.length > index
                ? "border-gold-500 bg-gold-500/15 text-gold-400"
                : "border-white/15 bg-pitch-950/70"
            }`}
          >
            {value.length > index ? "\u25CF" : ""}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-2.5">
        {KEYS.map((key) => (
          <button
            key={key}
            type="button"
            disabled={disabled}
            onClick={() => press(key)}
            aria-label={key === "back" ? "Borrar" : key === "clear" ? "Limpiar" : key}
            className={`btn min-h-[60px] text-xl ${
              key === "clear" || key === "back"
                ? "btn-secondary text-base"
                : "bg-pitch-800 text-stone-100 hover:bg-pitch-700"
            }`}
          >
            {key === "back" ? "\u232B" : key === "clear" ? "C" : key}
          </button>
        ))}
      </div>
    </div>
  );
}
