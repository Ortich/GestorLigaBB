"use client";

import { useEffect, useRef } from "react";

export function Spinner({ label = "Cargando..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 text-stone-400">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/15 border-t-gold-500" />
      <p className="text-sm">{label}</p>
    </div>
  );
}

export function Alert({
  kind = "error",
  children,
  onDismiss,
}: {
  kind?: "error" | "info" | "success";
  children: React.ReactNode;
  onDismiss?: () => void;
}) {
  const styles = {
    error: "border-blood-600/50 bg-blood-700/20 text-blood-500",
    info: "border-sky-500/40 bg-sky-500/10 text-sky-200",
    success: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200",
  }[kind];

  return (
    <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm ${styles}`} role="alert">
      <span className="flex-1">{children}</span>
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label="Cerrar aviso" className="text-lg leading-none">
          &times;
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, hint }: { icon: string; title: string; hint?: string }) {
  return (
    <div className="card flex flex-col items-center gap-2 py-10 text-center">
      <span className="text-4xl">{icon}</span>
      <p className="font-semibold text-stone-200">{title}</p>
      {hint && <p className="max-w-xs text-sm text-stone-400">{hint}</p>}
    </div>
  );
}

/** Hoja inferior: el patron mas comodo para pulgares en movil. */
export function Sheet({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="Cerrar"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="relative z-10 max-h-[88dvh] w-full overflow-y-auto rounded-t-3xl border border-white/10
                   bg-pitch-900 p-5 shadow-card sm:max-w-lg sm:rounded-3xl"
      >
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-white/20 sm:hidden" />
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-lg font-bold text-gold-400">{title}</h2>
          <button type="button" onClick={onClose} className="text-2xl leading-none text-stone-400">
            &times;
          </button>
        </div>
        <div className="space-y-4">{children}</div>
        {footer && <div className="mt-5 flex gap-3">{footer}</div>}
      </div>
    </div>
  );
}

export function StatBlock({
  ma,
  st,
  ag,
  pa,
  av,
}: {
  ma: number;
  st: number;
  ag: number;
  pa: number | null;
  av: number;
}) {
  const cells: [string, string][] = [
    ["MA", String(ma)],
    ["ST", String(st)],
    ["AG", `${ag}+`],
    ["PA", pa === null ? "-" : `${pa}+`],
    ["AV", `${av}+`],
  ];
  return (
    <div className="flex gap-1.5">
      {cells.map(([key, value]) => (
        <div key={key} className="stat-pill">
          <span className="text-[9px] font-normal uppercase text-stone-500">{key}</span>
          <span className="-mt-0.5 leading-none">{value}</span>
        </div>
      ))}
    </div>
  );
}

export function Counter({
  value,
  onChange,
  min = 0,
  max = 99,
  label,
}: {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  label: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-pitch-800/70 px-3 py-2">
      <span className="text-sm text-stone-300">{label}</span>
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={`Quitar ${label}`}
          className="btn btn-secondary btn-sm h-9 w-9 px-0"
          disabled={value <= min}
          onClick={() => onChange(value - 1)}
        >
          -
        </button>
        <span className="w-8 text-center text-lg font-bold tabular-nums">{value}</span>
        <button
          type="button"
          aria-label={`Anadir ${label}`}
          className="btn btn-secondary btn-sm h-9 w-9 px-0"
          disabled={value >= max}
          onClick={() => onChange(value + 1)}
        >
          +
        </button>
      </div>
    </div>
  );
}
