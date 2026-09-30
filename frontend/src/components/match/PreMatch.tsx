"use client";

import { useState } from "react";

import { Alert, Sheet } from "@/components/ui";
import { api, formatGold } from "@/lib/api";
import type { InducementCatalogItem, MatchDetail, RuleEntry, Rules } from "@/lib/types";

type RollKind = "WEATHER" | "PRAYER" | "KICK_OFF";

const ROLLS: { kind: RollKind; label: string; dice: string; icon: string; max: number }[] = [
  { kind: "WEATHER", label: "Clima", dice: "2D6", icon: "\u{1F324}", max: 12 },
  { kind: "PRAYER", label: "Plegarias a Nuffle", dice: "1D16", icon: "\u{1F64F}", max: 16 },
  { kind: "KICK_OFF", label: "Patada inicial", dice: "2D6", icon: "\u{1F945}", max: 12 },
];

/**
 * Paso 2: VAE de ambos equipos, Fondo Menor para el de menor VAE, catalogo de
 * incentivos y las tres tiradas de prepartido.
 */
export function PreMatchStep({
  match,
  rules,
  onUpdated,
}: {
  match: MatchDetail;
  rules: Rules | null;
  onUpdated: (next: MatchDetail) => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [popup, setPopup] = useState<{ title: string; roll: number; entry: RuleEntry } | null>(null);
  const [manual, setManual] = useState<RollKind | null>(null);
  const [manualValue, setManualValue] = useState("");
  const [starCost, setStarCost] = useState("");
  const [starOpen, setStarOpen] = useState(false);

  const beneficiary =
    match.petty_cash_team_id === match.home_team.id
      ? match.home_team
      : match.petty_cash_team_id === match.away_team.id
        ? match.away_team
        : null;

  const call = async (fn: () => Promise<MatchDetail>) => {
    setBusy(true);
    setError(null);
    try {
      onUpdated(await fn());
      return true;
    } catch (err) {
      setError((err as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };

  const roll = async (kind: RollKind, value?: number) => {
    setBusy(true);
    setError(null);
    try {
      const next = await api<MatchDetail>(`/api/matches/${match.id}/rolls`, {
        method: "POST",
        auth: true,
        body: { kind, value, team_id: kind === "PRAYER" ? match.petty_cash_team_id : undefined },
      });
      onUpdated(next);
      const info =
        kind === "WEATHER"
          ? { title: "Clima", roll: next.weather_roll, entry: next.weather }
          : kind === "PRAYER"
            ? { title: "Plegaria a Nuffle", roll: next.prayer_roll, entry: next.prayer }
            : { title: "Patada inicial", roll: next.kick_off_roll, entry: next.kick_off };
      if (info.roll !== null && info.entry) {
        setPopup({ title: info.title, roll: info.roll, entry: info.entry });
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      setManual(null);
      setManualValue("");
    }
  };

  const buy = (item: InducementCatalogItem, unitCost?: number) =>
    call(() =>
      api<MatchDetail>(`/api/matches/${match.id}/inducements`, {
        method: "POST",
        auth: true,
        body: {
          team_id: match.petty_cash_team_id,
          code: item.code,
          quantity: 1,
          unit_cost: unitCost,
        },
      }),
    );

  const drop = (inducementId: number) =>
    call(() =>
      api<MatchDetail>(`/api/matches/${match.id}/inducements/${inducementId}`, {
        method: "DELETE",
        auth: true,
      }),
    );

  const start = () =>
    call(() => api<MatchDetail>(`/api/matches/${match.id}/start`, { method: "POST", auth: true }));

  const rollValue = (kind: RollKind) =>
    kind === "WEATHER" ? match.weather_roll : kind === "PRAYER" ? match.prayer_roll : match.kick_off_roll;
  const rollEntry = (kind: RollKind) =>
    kind === "WEATHER" ? match.weather : kind === "PRAYER" ? match.prayer : match.kick_off;

  return (
    <>
      {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}

      <section className="card">
        <h2 className="section-title">{"\u{2696}"} Valoracion Actual de Equipo</h2>
        <div className="grid grid-cols-2 gap-3 text-center">
          {[
            { team: match.home_team, ctv: match.home_ctv },
            { team: match.away_team, ctv: match.away_ctv },
          ].map(({ team, ctv }) => (
            <div key={team.id} className="card-tight">
              <p className="text-2xl">{team.logo}</p>
              <p className="truncate text-xs text-stone-400">{team.name}</p>
              <p className="text-lg font-black text-stone-100">{formatGold(ctv)}</p>
            </div>
          ))}
        </div>

        {beneficiary ? (
          <div className="mt-3 rounded-xl border border-gold-500/40 bg-gold-500/10 p-3 text-center">
            <p className="text-xs uppercase tracking-wider text-gold-400">Fondo Menor</p>
            <p className="text-2xl font-black text-gold-400">
              {formatGold(match.petty_cash_amount)}
            </p>
            <p className="text-sm text-stone-200">
              para {beneficiary.logo} {beneficiary.name}
            </p>
            <p className="mt-1 text-[11px] text-stone-400">
              Solo se puede gastar en este partido y el credito sobrante se pierde. No se puede
              anadir oro de la tesoreria.
            </p>
          </div>
        ) : (
          <p className="mt-3 text-center text-sm text-stone-400">
            Las VAE estan igualadas: no hay Fondo Menor ni incentivos.
          </p>
        )}
      </section>

      {beneficiary && (
        <section className="card">
          <div className="mb-3 flex items-baseline justify-between">
            <h2 className="section-title mb-0">{"\u{1F6D2}"} Incentivos</h2>
            <span className="text-sm font-bold text-gold-400">
              {formatGold(match.petty_cash_remaining)} libres
            </span>
          </div>

          {match.inducements.length > 0 && (
            <ul className="mb-3 space-y-2">
              {match.inducements.map((item) => (
                <li key={item.id} className="flex items-center gap-2 rounded-lg bg-pitch-800/70 p-2.5">
                  <span className="min-w-0 flex-1 truncate text-sm font-semibold text-stone-100">
                    {item.quantity}x {item.name}
                  </span>
                  <span className="shrink-0 text-sm text-gold-400">{formatGold(item.total_cost)}</span>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm shrink-0"
                    disabled={busy}
                    onClick={() => drop(item.id)}
                  >
                    Quitar
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="space-y-2">
            {rules?.inducements.catalog.map((item) => {
              const owned = match.inducements.find((i) => i.code === item.code);
              const price = item.cost;
              const unaffordable = price > 0 && price > match.petty_cash_remaining;
              const maxed = (owned?.quantity ?? 0) >= item.max;
              return (
                <div key={item.code} className="card-tight flex items-start gap-3">
                  <span className="text-xl">{item.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-stone-100">{item.name}</p>
                    <p className="text-xs text-stone-500">{item.text}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-sm font-bold text-gold-400">
                      {price ? formatGold(price) : "Variable"}
                    </p>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm mt-1"
                      disabled={busy || maxed || (price > 0 && unaffordable)}
                      onClick={() => (price ? buy(item) : setStarOpen(true))}
                    >
                      {maxed ? "Maximo" : "Anadir"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="card">
        <h2 className="section-title">{"\u{1F3B2}"} Tiradas de prepartido</h2>
        <div className="space-y-2">
          {ROLLS.map((item) => {
            const value = rollValue(item.kind);
            const entry = rollEntry(item.kind);
            return (
              <div key={item.kind} className="card-tight">
                <div className="flex items-center gap-3">
                  <span className="text-xl">{item.icon}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-stone-100">
                      {item.label} <span className="text-stone-500">({item.dice})</span>
                    </p>
                    {entry ? (
                      <button
                        type="button"
                        className="truncate text-xs text-gold-400 underline-offset-2 hover:underline"
                        onClick={() => setPopup({ title: item.label, roll: value ?? 0, entry })}
                      >
                        {value}: {entry.name} &mdash; ver regla
                      </button>
                    ) : (
                      <p className="text-xs text-stone-500">Sin tirar</p>
                    )}
                  </div>
                  <div className="flex shrink-0 gap-1.5">
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      disabled={busy}
                      onClick={() => {
                        setManual(item.kind);
                        setManualValue("");
                      }}
                    >
                      Manual
                    </button>
                    <button
                      type="button"
                      className="btn-gold btn-sm"
                      disabled={busy}
                      onClick={() => roll(item.kind)}
                    >
                      Tirar
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <button
        type="button"
        className="btn-primary w-full"
        disabled={busy || match.weather_roll === null}
        onClick={start}
      >
        {match.weather_roll === null ? "Tira el clima para empezar" : "Empezar el partido"}
      </button>

      <Sheet
        open={popup !== null}
        title={popup ? `${popup.title}: ${popup.roll}` : ""}
        onClose={() => setPopup(null)}
      >
        {popup && (
          <>
            <p className="text-lg font-bold text-gold-400">{popup.entry.name}</p>
            <p className="text-sm text-stone-200">{popup.entry.text}</p>
          </>
        )}
      </Sheet>

      <Sheet
        open={manual !== null}
        title="Introducir tirada manual"
        onClose={() => setManual(null)}
        footer={
          <button
            type="button"
            className="btn-primary flex-1"
            disabled={!manualValue || busy}
            onClick={() => manual && roll(manual, Number(manualValue))}
          >
            Guardar resultado
          </button>
        }
      >
        <p className="text-sm text-stone-400">
          Si ya habeis tirado los dados fisicos, anota aqui el resultado.
        </p>
        <input
          type="number"
          inputMode="numeric"
          className="input"
          placeholder="Resultado"
          min={manual === "PRAYER" ? 1 : 2}
          max={ROLLS.find((r) => r.kind === manual)?.max ?? 12}
          value={manualValue}
          onChange={(event) => setManualValue(event.target.value)}
        />
      </Sheet>

      <Sheet
        open={starOpen}
        title="Jugador Estrella"
        onClose={() => setStarOpen(false)}
        footer={
          <button
            type="button"
            className="btn-primary flex-1"
            disabled={!starCost || busy}
            onClick={async () => {
              const item = rules?.inducements.catalog.find((c) => c.code === "STAR_PLAYER");
              if (!item) return;
              if (await buy(item, Number(starCost))) {
                setStarOpen(false);
                setStarCost("");
              }
            }}
          >
            Contratar
          </button>
        }
      >
        <p className="text-sm text-stone-400">
          Introduce el coste exacto del Jugador Estrella segun su ficha (en monedas de oro).
        </p>
        <input
          type="number"
          inputMode="numeric"
          className="input"
          placeholder="Ej. 250000"
          value={starCost}
          onChange={(event) => setStarCost(event.target.value)}
        />
      </Sheet>
    </>
  );
}
