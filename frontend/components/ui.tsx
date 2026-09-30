"use client";

import Link from "next/link";

export function Shell({
  children,
  title,
  eyebrow,
  action,
}: {
  children: React.ReactNode;
  title: string;
  eyebrow?: string;
  action?: React.ReactNode;
}) {
  return (
    <main className="mx-auto min-h-screen w-full max-w-md px-4 pb-16 pt-5">
      <header className="mb-5 flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-gold">
            {eyebrow || "Liga de la Mesa"}
          </p>
          <h1 className="font-display text-[1.7rem] uppercase leading-none tracking-wide text-bone">{title}</h1>
        </div>
        {action}
      </header>
      {children}
    </main>
  );
}

export function Banner({ tone = "error", children }: { tone?: "error" | "info"; children: React.ReactNode }) {
  const styles =
    tone === "error"
      ? "border-blood/70 bg-blood/15 text-bone"
      : "border-gold/40 bg-gold/10 text-bone";
  return <div className={`mb-4 rounded-2xl border px-4 py-3 text-sm leading-snug ${styles}`}>{children}</div>;
}

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/70 p-4 sm:items-center">
      <div className="w-full max-w-md rounded-3xl border border-line bg-card p-5 shadow-card">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gold">Resultado</p>
        <h2 className="mt-1 font-display text-3xl uppercase leading-none text-bone">{title}</h2>
        <div className="mt-3 text-base leading-relaxed text-muted">{children}</div>
        <button
          className="mt-5 min-h-14 w-full rounded-2xl bg-gold font-display text-xl uppercase tracking-wide text-ink"
          onClick={onClose}
        >
          Entendido
        </button>
      </div>
    </div>
  );
}

export function BigButton({
  children,
  onClick,
  disabled,
  tone = "gold",
  type = "button",
}: {
  children: React.ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  tone?: "gold" | "pitch" | "blood" | "ghost";
  type?: "button" | "submit";
}) {
  const tones = {
    gold: "bg-gold text-ink",
    pitch: "bg-pitch text-bone",
    blood: "bg-blood text-bone",
    ghost: "border border-line bg-card2 text-bone",
  };
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      className={`min-h-14 w-full rounded-2xl px-4 font-display text-xl uppercase tracking-wide transition active:scale-[0.98] disabled:opacity-40 ${tones[tone]}`}
    >
      {children}
    </button>
  );
}

export function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="text-sm font-semibold text-gold">
      {label}
    </Link>
  );
}

export function PinPad({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const digits = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "del"];
  return (
    <div>
      <div className="mb-3 flex justify-center gap-3">
        {[0, 1, 2, 3].map((index) => (
          <span
            key={index}
            className={`h-4 w-4 rounded-full border ${value.length > index ? "border-gold bg-gold" : "border-line bg-transparent"}`}
          />
        ))}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {digits.map((digit, index) => {
          if (!digit) return <span key={index} />;
          const isDelete = digit === "del";
          return (
            <button
              key={index}
              type="button"
              className={`min-h-14 rounded-2xl bg-card2 text-bone active:bg-line ${isDelete ? "text-sm font-semibold" : "font-display text-2xl"}`}
              onClick={() => {
                if (isDelete) onChange(value.slice(0, -1));
                else if (value.length < 4) onChange(value + digit);
              }}
            >
              {isDelete ? "Borrar" : digit}
            </button>
          );
        })}
      </div>
    </div>
  );
}
