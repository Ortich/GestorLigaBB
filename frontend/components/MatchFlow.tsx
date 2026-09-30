"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, EVENT_LABEL, gold, STATUS_LABEL } from "@/lib/api";
import type { MatchState, Player, RollCard } from "@/lib/types";
import { BackLink, Banner, BigButton, Modal, PinPad, Shell } from "@/components/ui";

const LIVE_ACTIONS = [
  { type: "TD", label: "TD" },
  { type: "CAS", label: "Baja" },
  { type: "PASS", label: "Pase" },
  { type: "FOUL", label: "Falta" },
  { type: "INT", label: "Int" },
] as const;

export function MatchFlow({ matchId }: { matchId: string }) {
  const router = useRouter();
  const [match, setMatch] = useState<MatchState | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [popup, setPopup] = useState<RollCard>(null);
  const [closing, setClosing] = useState(false);
  const [homePin, setHomePin] = useState("");
  const [awayPin, setAwayPin] = useState("");

  function load() {
    api<MatchState>(`/api/matches/${matchId}`)
      .then((next) => {
        setMatch(next);
        setError("");
      })
      .catch((err: Error) => {
        if (err.message.toLowerCase().includes("sesión") || err.message.toLowerCase().includes("entrar")) {
          window.localStorage.removeItem("bb_token");
          router.replace("/");
          return;
        }
        setError(err.message);
      });
  }

  useEffect(() => {
    if (!window.localStorage.getItem("bb_token")) {
      router.replace("/");
      return;
    }
    load();
  }, [matchId, router]);

  async function run(action: () => Promise<MatchState>, notice?: (next: MatchState) => RollCard) {
    setBusy(true);
    setError("");
    try {
      const next = await action();
      setMatch(next);
      const card = notice?.(next);
      if (card) setPopup(card);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error");
    } finally {
      setBusy(false);
    }
  }

  if (!match) {
    return (
      <Shell title="Partido">
        {error ? <Banner>{error}</Banner> : <p className="text-muted">Abriendo el acta…</p>}
      </Shell>
    );
  }

  const title = `${match.home_name.split(" ")[0]} vs ${match.away_name.split(" ")[0]}`;
  return (
    <Shell
      title={title}
      eyebrow={`Jornada ${match.round_number} · ${STATUS_LABEL[match.status] || match.status}`}
      action={<BackLink href="/dashboard" label="Panel" />}
    >
      {error && <Banner>{error}</Banner>}
      {match.bounty && (
        <p className="mb-4 rounded-2xl border border-line bg-card px-3 py-3 text-sm leading-snug">
          <span className="font-semibold text-gold">{match.bounty.name}. </span>
          {match.bounty.summary}
        </p>
      )}
      {(match.status === "SCHEDULED" || match.status === "READY_CHECK") && (
        <ReadyStep
          match={match}
          homePin={homePin}
          awayPin={awayPin}
          setHomePin={setHomePin}
          setAwayPin={setAwayPin}
          busy={busy}
          onConfirm={(teamId, pin) =>
            run(() => api(`/api/matches/${match.id}/ready`, { body: { team_id: teamId, pin } }))
          }
        />
      )}
      {match.status === "PRE_MATCH" && (
        <PreMatch match={match} busy={busy} run={run} onPopup={setPopup} />
      )}
      {match.status === "IN_PROGRESS" && !closing && (
        <Live match={match} busy={busy} run={run} onClose={() => setClosing(true)} />
      )}
      {match.status === "IN_PROGRESS" && closing && (
        <CloseForm
          match={match}
          busy={busy}
          onCancel={() => setClosing(false)}
          onSubmit={(body) =>
            void run(async () => {
              const next = await api<MatchState>(`/api/matches/${match.id}/complete`, { body });
              setClosing(false);
              return next;
            })
          }
        />
      )}
      {match.status === "COMPLETED" && <Acta match={match} />}
      {popup && (
        <Modal title={popup.name} onClose={() => setPopup(null)}>
          <p className="mb-2 font-display text-4xl text-gold">{popup.roll}</p>
          <p>{popup.summary}</p>
        </Modal>
      )}
    </Shell>
  );
}

function ReadyStep({
  match,
  homePin,
  awayPin,
  setHomePin,
  setAwayPin,
  busy,
  onConfirm,
}: {
  match: MatchState;
  homePin: string;
  awayPin: string;
  setHomePin: (value: string) => void;
  setAwayPin: (value: string) => void;
  busy: boolean;
  onConfirm: (teamId: number, pin: string) => void;
}) {
  return (
    <div className="space-y-4">
      <p className="text-sm leading-relaxed text-muted">
        Los dos entrenadores confirman en este móvil. Hasta que no entren los dos PIN no se calcula el fondo menor.
      </p>
      <PinBlock
        name={match.home_name}
        coach={match.home_coach}
        ready={match.home_ready}
        pin={homePin}
        onChange={setHomePin}
        disabled={busy || match.home_ready}
        onConfirm={() => onConfirm(match.home_team_id, homePin)}
      />
      <PinBlock
        name={match.away_name}
        coach={match.away_coach}
        ready={match.away_ready}
        pin={awayPin}
        onChange={setAwayPin}
        disabled={busy || match.away_ready}
        onConfirm={() => onConfirm(match.away_team_id, awayPin)}
      />
    </div>
  );
}

function PinBlock({
  name,
  coach,
  ready,
  pin,
  onChange,
  onConfirm,
  disabled,
}: {
  name: string;
  coach: string;
  ready: boolean;
  pin: string;
  onChange: (value: string) => void;
  onConfirm: () => void;
  disabled: boolean;
}) {
  return (
    <section className="rounded-3xl border border-line bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="font-display text-xl uppercase leading-none">{name}</h2>
          <p className="text-sm text-muted">{coach}</p>
        </div>
        <span className={`text-xs font-semibold uppercase ${ready ? "text-[#8ddeaf]" : "text-muted"}`}>
          {ready ? "Dentro" : "Pendiente"}
        </span>
      </div>
      {!ready && (
        <>
          <PinPad value={pin} onChange={onChange} />
          <div className="mt-3">
            <BigButton disabled={disabled || pin.length !== 4} onClick={onConfirm}>
              Confirmar
            </BigButton>
          </div>
        </>
      )}
    </section>
  );
}

function PreMatch({
  match,
  busy,
  run,
  onPopup,
}: {
  match: MatchState;
  busy: boolean;
  run: (action: () => Promise<MatchState>, notice?: (next: MatchState) => RollCard) => Promise<void>;
  onPopup: (card: RollCard) => void;
}) {
  const petty =
    match.petty_cash_team_id === match.home.id
      ? match.home
      : match.petty_cash_team_id === match.away.id
        ? match.away
        : null;
  return (
    <div className="space-y-4 pb-4">
      <section className="grid grid-cols-2 gap-2">
        <ValueCard name={match.home.name} value={match.home.ctv} breakdown={match.home.ctv_breakdown} />
        <ValueCard name={match.away.name} value={match.away.ctv} breakdown={match.away.ctv_breakdown} />
      </section>
      <section className="rounded-3xl border border-gold/40 bg-card p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gold">Fondo menor</p>
        {petty ? (
          <>
            <h2 className="mt-1 font-display text-2xl uppercase leading-none">{petty.name}</h2>
            <p className="mt-2 text-sm text-muted">
              Recibe {gold(match.petty_cash_amount)}. Quedan {gold(match.petty_cash_remaining)}. Lo que no se gaste se pierde, y no se puede completar con tesorería.
            </p>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted">Las valoraciones están igualadas. Nadie recibe fondo menor.</p>
        )}
      </section>
      {petty && (
        <div className="space-y-2">
          {match.inducements.map((item) => {
            const nextCostFits = match.petty_cash_remaining >= item.cost;
            return (
              <article key={item.id} className="rounded-3xl border border-line bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-display text-lg uppercase leading-tight">{item.name}</h3>
                    <p className="text-sm text-gold">{gold(item.cost)}</p>
                  </div>
                  <p className="font-display text-2xl">{item.qty}</p>
                </div>
                <p className="mt-2 text-sm leading-snug text-muted">{item.summary}</p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <button
                    className="min-h-12 rounded-2xl bg-card2 font-display text-xl disabled:opacity-40"
                    disabled={busy || item.qty === 0}
                    onClick={() =>
                      void run(() =>
                        api(`/api/matches/${match.id}/inducements`, {
                          body: {
                            team_id: petty.id,
                            items: match.inducements.map((row) => ({
                              id: row.id,
                              qty: row.id === item.id ? row.qty - 1 : row.qty,
                            })),
                          },
                        }),
                      )
                    }
                  >
                    −
                  </button>
                  <button
                    className="min-h-12 rounded-2xl bg-gold font-display text-xl text-ink disabled:opacity-40"
                    disabled={busy || item.qty >= item.max || !nextCostFits}
                    onClick={() =>
                      void run(() =>
                        api(`/api/matches/${match.id}/inducements`, {
                          body: {
                            team_id: petty.id,
                            items: match.inducements.map((row) => ({
                              id: row.id,
                              qty: row.id === item.id ? row.qty + 1 : row.qty,
                            })),
                          },
                        }),
                      )
                    }
                  >
                    +
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
      <BenefitNotes match={match} />
      <RollCardView
        label="Clima · 2d6"
        card={match.weather}
        busy={busy}
        onDigital={() =>
          void run(
            () => api(`/api/matches/${match.id}/rolls`, { body: { weather: true } }),
            (next) => next.weather,
          )
        }
        onManual={(value) =>
          void run(
            () => api(`/api/matches/${match.id}/rolls`, { body: { weather_manual: value } }),
            (next) => next.weather,
          )
        }
        onOpen={() => match.weather && onPopup(match.weather)}
      />
      <RollCardView
        label="Plegarias · 1d16"
        card={match.prayer}
        busy={busy}
        onDigital={() =>
          void run(
            () => api(`/api/matches/${match.id}/rolls`, { body: { prayer: true } }),
            (next) => next.prayer,
          )
        }
        onManual={(value) =>
          void run(
            () => api(`/api/matches/${match.id}/rolls`, { body: { prayer_manual: value } }),
            (next) => next.prayer,
          )
        }
        onOpen={() => match.prayer && onPopup(match.prayer)}
      />
      <RollCardView
        label="Patada inicial · 2d6"
        card={match.kick_off}
        busy={busy}
        onDigital={() =>
          void run(
            () => api(`/api/matches/${match.id}/rolls`, { body: { kickoff: true } }),
            (next) => next.kick_off,
          )
        }
        onManual={(value) =>
          void run(
            () => api(`/api/matches/${match.id}/rolls`, { body: { kickoff_manual: value } }),
            (next) => next.kick_off,
          )
        }
        onOpen={() => match.kick_off && onPopup(match.kick_off)}
      />
      <section className="rounded-3xl border border-line bg-card p-4">
        <h2 className="font-display text-xl uppercase">¿Quién saca?</h2>
        {(match.home.benefits.chooses_kick || match.away.benefits.chooses_kick) && (
          <p className="mt-2 text-sm text-gold">
            {match.home.benefits.chooses_kick ? match.home.name : match.away.name} tiene la Prensa Amarilla y elige.
          </p>
        )}
        <div className="mt-3 grid grid-cols-2 gap-2">
          {[match.home, match.away].map((side) => (
            <button
              key={side.id}
              className={`min-h-14 rounded-2xl px-2 font-display text-sm uppercase leading-tight ${
                match.kicking_team_id === side.id ? "bg-gold text-ink" : "bg-card2 text-bone"
              }`}
              disabled={busy}
              onClick={() =>
                void run(() => api(`/api/matches/${match.id}/rolls`, { body: { kicking_team_id: side.id } }))
              }
            >
              Saca {side.name}
            </button>
          ))}
        </div>
      </section>
      <BigButton disabled={busy} tone="pitch" onClick={() => void run(() => api(`/api/matches/${match.id}/begin`, { method: "POST" }))}>
        Empezar partido
      </BigButton>
    </div>
  );
}

function ValueCard({
  name,
  value,
  breakdown,
}: {
  name: string;
  value: number;
  breakdown: MatchState["home"]["ctv_breakdown"];
}) {
  return (
    <article className="rounded-3xl border border-line bg-card p-3">
      <h2 className="truncate font-display text-base uppercase leading-tight">{name}</h2>
      <p className="mt-2 font-display text-2xl leading-none text-gold">{gold(value)}</p>
      <p className="mt-2 text-[11px] leading-snug text-muted">
        Jugadores {gold(breakdown.players)} · SO {breakdown.reroll_count} · Apo {breakdown.apothecary ? "sí" : "no"}
      </p>
    </article>
  );
}

function RollCardView({
  label,
  card,
  busy,
  onDigital,
  onManual,
  onOpen,
}: {
  label: string;
  card: RollCard;
  busy: boolean;
  onDigital: () => void;
  onManual: (value: number) => void;
  onOpen: () => void;
}) {
  const [manual, setManual] = useState("");
  return (
    <section className="rounded-3xl border border-line bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="font-display text-lg uppercase leading-tight">{label}</h2>
        {card && (
          <button className="font-display text-3xl leading-none text-gold" onClick={onOpen}>
            {card.roll}
          </button>
        )}
      </div>
      {card ? (
        <button className="mt-2 text-left text-sm text-muted" onClick={onOpen}>
          {card.name}. Toca para leer el recordatorio.
        </button>
      ) : (
        <p className="mt-2 text-sm text-muted">Sin tirar.</p>
      )}
      <button className="mt-3 min-h-12 w-full rounded-2xl bg-gold font-display uppercase text-ink disabled:opacity-40" disabled={busy} onClick={onDigital}>
        {card ? "Repetir tirada" : "Tirar dados"}
      </button>
      <div className="mt-2 flex gap-2">
        <input
          inputMode="numeric"
          value={manual}
          onChange={(event) => setManual(event.target.value.replace(/[^\d]/g, "").slice(0, 2))}
          className="min-h-12 w-24 rounded-2xl border border-line bg-ink/40 px-2 text-center"
          placeholder="Nº"
        />
        <button
          className="min-h-12 flex-1 rounded-2xl bg-card2 px-3 font-semibold disabled:opacity-40"
          disabled={busy || !manual}
          onClick={() => onManual(Number(manual))}
        >
          Anotar dado físico
        </button>
      </div>
    </section>
  );
}

function BenefitNotes({ match }: { match: MatchState }) {
  const notes = [match.home, match.away].flatMap((side) => {
    const lines: string[] = [];
    if (side.benefits.free_reroll) lines.push(`${side.name}: una segunda oportunidad gratis del Tabernero.`);
    if (side.benefits.free_bribe) lines.push(`${side.name}: un soborno gratis del Sindicato.`);
    if (side.benefits.ko_recovery) lines.push(`${side.name}: recupera un KO adicional.`);
    if (side.benefits.cas_bonus) lines.push(`${side.name}: 20.000 mo si causa 2 o más bajas.`);
    return lines;
  });
  if (!notes.length) return null;
  return (
    <section className="rounded-3xl border border-line bg-card p-4 text-sm leading-relaxed text-muted">
      {notes.map((line) => (
        <p key={line}>{line}</p>
      ))}
    </section>
  );
}

function Live({
  match,
  busy,
  run,
  onClose,
}: {
  match: MatchState;
  busy: boolean;
  run: (action: () => Promise<MatchState>) => Promise<void>;
  onClose: () => void;
}) {
  return (
    <div className="pb-28">
      <div className="sticky top-0 z-10 -mx-4 mb-3 border-b border-line bg-ink/90 px-4 py-3 backdrop-blur">
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          <p className="truncate text-right font-display text-sm uppercase">{match.home_name}</p>
          <p className="font-display text-3xl leading-none">
            {match.home_td}
            <span className="mx-1 text-muted">-</span>
            {match.away_td}
          </p>
          <p className="truncate font-display text-sm uppercase">{match.away_name}</p>
        </div>
        <div className="mt-2 flex items-center justify-center gap-3">
          <button
            className="h-10 w-10 rounded-full bg-card2 font-display text-xl"
            onClick={() => void run(() => api(`/api/matches/${match.id}/turn`, { body: { turn: Math.max(0, match.current_turn - 1) } }))}
          >
            −
          </button>
          <p className="text-sm uppercase tracking-wide text-muted">Turno {match.current_turn}</p>
          <button
            className="h-10 w-10 rounded-full bg-card2 font-display text-xl"
            onClick={() => void run(() => api(`/api/matches/${match.id}/turn`, { body: { turn: Math.min(16, match.current_turn + 1) } }))}
          >
            +
          </button>
        </div>
      </div>
      <BenefitButtons match={match} busy={busy} run={run} />
      <div className="grid grid-cols-2 gap-2">
        <Column match={match} side="home" busy={busy} run={run} />
        <Column match={match} side="away" busy={busy} run={run} />
      </div>
      <section className="mt-4 rounded-3xl border border-line bg-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-display text-lg uppercase">Acta viva</h2>
          <button
            className="text-sm font-semibold text-gold disabled:opacity-40"
            disabled={busy || match.events.length === 0}
            onClick={() => void run(() => api(`/api/matches/${match.id}/events/undo`, { method: "POST" }))}
          >
            Deshacer último
          </button>
        </div>
        {match.events.length === 0 && <p className="text-sm text-muted">Todavía no hay eventos.</p>}
        <ul className="space-y-1">
          {[...match.events].reverse().slice(0, 8).map((event) => (
            <li key={event.id} className="text-sm text-muted">
              T{event.turn ?? "–"} · {event.player_name} · {EVENT_LABEL[event.event_type] || event.event_type}
              {event.spp_awarded ? ` · +${event.spp_awarded} PEP` : ""}
            </li>
          ))}
        </ul>
      </section>
      <div className="fixed inset-x-0 bottom-0 z-20 mx-auto w-full max-w-md border-t border-line bg-ink/95 p-3">
        <BigButton tone="blood" onClick={onClose}>
          Cerrar acta
        </BigButton>
      </div>
    </div>
  );
}

function BenefitButtons({
  match,
  busy,
  run,
}: {
  match: MatchState;
  busy: boolean;
  run: (action: () => Promise<MatchState>) => Promise<void>;
}) {
  const buttons = [
    match.home.benefits.free_reroll
      ? { team: match.home.id, benefit: "reroll", label: `SO gratis ${match.home.name}`, used: match.free_reroll_used.home }
      : null,
    match.away.benefits.free_reroll
      ? { team: match.away.id, benefit: "reroll", label: `SO gratis ${match.away.name}`, used: match.free_reroll_used.away }
      : null,
    match.home.benefits.free_bribe
      ? { team: match.home.id, benefit: "bribe", label: `Soborno ${match.home.name}`, used: match.free_bribe_used.home }
      : null,
    match.away.benefits.free_bribe
      ? { team: match.away.id, benefit: "bribe", label: `Soborno ${match.away.name}`, used: match.free_bribe_used.away }
      : null,
  ].filter(Boolean) as { team: number; benefit: string; label: string; used: boolean }[];
  if (!buttons.length) return null;
  return (
    <div className="mb-3 space-y-2">
      {buttons.map((button) => (
        <button
          key={button.label}
          disabled={busy || button.used}
          className="min-h-12 w-full rounded-2xl border border-gold/40 bg-gold/10 px-3 text-sm font-semibold disabled:opacity-40"
          onClick={() =>
            void run(() =>
              api(`/api/matches/${match.id}/benefits`, {
                body: { team_id: button.team, benefit: button.benefit },
              }),
            )
          }
        >
          {button.used ? `${button.label} usada` : button.label}
        </button>
      ))}
    </div>
  );
}

function Column({
  match,
  side,
  busy,
  run,
}: {
  match: MatchState;
  side: "home" | "away";
  busy: boolean;
  run: (action: () => Promise<MatchState>) => Promise<void>;
}) {
  const team = side === "home" ? match.home : match.away;
  const players = [...team.players].sort((a, b) => Number(a.status !== "ACTIVE") - Number(b.status !== "ACTIVE") || a.number - b.number);
  return (
    <div className="space-y-2">
      <h2 className="truncate px-1 font-display text-sm uppercase text-gold">{team.name}</h2>
      {players.map((player) => (
        <PlayerActions key={player.id} matchId={match.id} teamId={team.id} turn={match.current_turn} player={player} busy={busy} run={run} />
      ))}
    </div>
  );
}

function PlayerActions({
  matchId,
  teamId,
  turn,
  player,
  busy,
  run,
}: {
  matchId: number;
  teamId: number;
  turn: number;
  player: Player;
  busy: boolean;
  run: (action: () => Promise<MatchState>) => Promise<void>;
}) {
  const active = player.status === "ACTIVE";
  return (
    <article className={`rounded-2xl border border-line bg-card p-2 ${active ? "" : "opacity-50"}`}>
      <p className="truncate font-semibold leading-tight">{player.name}</p>
      <p className="truncate text-[11px] text-muted">
        {player.position} · {player.spp} PEP
      </p>
      {active && (
        <div className="mt-2 grid grid-cols-2 gap-1">
          {LIVE_ACTIONS.map((action) => (
            <button
              key={action.type}
              disabled={busy}
              className={`min-h-11 rounded-xl text-[11px] font-bold uppercase ${
                action.type === "TD" ? "bg-pitch text-bone" : action.type === "CAS" ? "bg-blood text-bone" : "bg-card2 text-bone"
              }`}
              onClick={() =>
                void run(() =>
                  api(`/api/matches/${matchId}/events`, {
                    body: { team_id: teamId, player_id: player.id, event_type: action.type, turn },
                  }),
                )
              }
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </article>
  );
}

function CloseForm({
  match,
  busy,
  onCancel,
  onSubmit,
}: {
  match: MatchState;
  busy: boolean;
  onCancel: () => void;
  onSubmit: (body: unknown) => void;
}) {
  const [homeMvp, setHomeMvp] = useState<number | null>(null);
  const [awayMvp, setAwayMvp] = useState<number | null>(null);
  const [homeDie, setHomeDie] = useState("");
  const [awayDie, setAwayDie] = useState("");
  const [injuries, setInjuries] = useState<Record<number, { result: string; note: string }>>({});
  const roster = [...match.home.players, ...match.away.players].filter((player) => player.status !== "DEAD");
  return (
    <div className="space-y-4">
      <p className="text-sm leading-relaxed text-muted">
        Cada equipo suma 1d6 × 10.000 mo. Si dejas el dado vacío, lo tira la app. Elige un MVP por equipo: son 4 PEP.
      </p>
      <DieField label={`Ganancia de ${match.home.name}`} value={homeDie} onChange={setHomeDie} />
      <DieField label={`Ganancia de ${match.away.name}`} value={awayDie} onChange={setAwayDie} />
      <MvpPicker label={`MVP ${match.home.name}`} players={match.home.players} value={homeMvp} onChange={setHomeMvp} />
      <MvpPicker label={`MVP ${match.away.name}`} players={match.away.players} value={awayMvp} onChange={setAwayMvp} />
      <section className="rounded-3xl border border-line bg-card p-4">
        <h2 className="font-display text-xl uppercase">Lesiones</h2>
        <p className="mt-1 text-sm text-muted">
          En jornadas 1 y 2, muerte o lesión permanente devuelve oro a la tesorería. Un MNG no entra en esa red.
        </p>
        <div className="mt-3 space-y-3">
          {roster.map((player) => {
            const current = injuries[player.id]?.result || "";
            return (
              <div key={player.id}>
                <p className="text-sm font-semibold">
                  {player.number}. {player.name}
                  <span className="font-normal text-muted"> · {player.status === "MNG" ? "ya estaba MNG" : player.position}</span>
                </p>
                <div className="mt-1 grid grid-cols-2 gap-1">
                  {[
                    ["", "Nada"],
                    ["MNG", "MNG"],
                    ["PERMANENT", "Permanente"],
                    ["DEAD", "Muerto"],
                  ].map(([value, label]) => (
                    <button
                      key={label}
                      className={`min-h-10 rounded-xl text-xs font-semibold uppercase ${
                        current === value ? "bg-gold text-ink" : "bg-card2 text-bone"
                      }`}
                      onClick={() =>
                        setInjuries((prev) => ({
                          ...prev,
                          [player.id]: { result: value, note: prev[player.id]?.note || "" },
                        }))
                      }
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {current && current !== "" && (
                  <input
                    className="mt-1 min-h-11 w-full rounded-xl border border-line bg-ink/40 px-3"
                    placeholder="Nota, por ejemplo -1 MA"
                    value={injuries[player.id]?.note || ""}
                    onChange={(event) =>
                      setInjuries((prev) => ({
                        ...prev,
                        [player.id]: { result: current, note: event.target.value },
                      }))
                    }
                  />
                )}
              </div>
            );
          })}
        </div>
      </section>
      <BigButton
        disabled={busy || !homeMvp || !awayMvp}
        onClick={() =>
          onSubmit({
            home_mvp_player_id: homeMvp,
            away_mvp_player_id: awayMvp,
            home_winnings_d6: homeDie ? Number(homeDie) : null,
            away_winnings_d6: awayDie ? Number(awayDie) : null,
            injuries: Object.entries(injuries)
              .filter(([, value]) => value.result)
              .map(([playerId, value]) => ({
                player_id: Number(playerId),
                result: value.result,
                note: value.note,
              })),
          })
        }
      >
        {busy ? "Cerrando…" : "Firmar el acta"}
      </BigButton>
      <BigButton tone="ghost" onClick={onCancel}>
        Volver al partido
      </BigButton>
    </div>
  );
}

function DieField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block rounded-3xl border border-line bg-card p-4">
      <span className="text-sm text-muted">{label}</span>
      <input
        inputMode="numeric"
        value={value}
        placeholder="1-6 o vacío"
        onChange={(event) => onChange(event.target.value.replace(/[^\d]/g, "").slice(0, 1))}
        className="mt-2 min-h-12 w-full rounded-2xl border border-line bg-ink/40 px-3"
      />
    </label>
  );
}

function MvpPicker({
  label,
  players,
  value,
  onChange,
}: {
  label: string;
  players: Player[];
  value: number | null;
  onChange: (id: number) => void;
}) {
  const options = players.filter((player) => player.status === "ACTIVE");
  return (
    <section className="rounded-3xl border border-line bg-card p-4">
      <h2 className="mb-2 font-display text-lg uppercase">{label}</h2>
      <div className="space-y-1">
        {options.map((player) => (
          <button
            key={player.id}
            className={`flex min-h-11 w-full items-center justify-between rounded-xl px-3 text-left text-sm ${
              value === player.id ? "bg-gold text-ink" : "bg-card2"
            }`}
            onClick={() => onChange(player.id)}
          >
            <span>
              {player.number}. {player.name}
            </span>
            <span>{player.spp} PEP</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function Acta({ match }: { match: MatchState }) {
  const mvp = (id: number | null, players: Player[]) => players.find((player) => player.id === id)?.name || "—";
  return (
    <div className="space-y-3">
      <section className="rounded-3xl border border-line bg-card p-4 text-center">
        <p className="font-display text-5xl">
          {match.home_td}
          <span className="mx-2 text-muted">-</span>
          {match.away_td}
        </p>
        <p className="mt-2 text-sm text-muted">
          {match.home_name} {match.home_td} · {match.away_name} {match.away_td}
        </p>
      </section>
      <Info label="Ganancias" text={`${match.home_name} ${gold(match.home_winnings)} · ${match.away_name} ${gold(match.away_winnings)}`} />
      <Info label="MVP" text={`${mvp(match.home_mvp_player_id, match.home.players)} y ${mvp(match.away_mvp_player_id, match.away.players)}`} />
      {match.injuries.length > 0 && (
        <section className="rounded-3xl border border-line bg-card p-4">
          <h2 className="font-display text-lg uppercase">Lesiones</h2>
          {match.injuries.map((injury) => (
            <p key={injury.id} className="mt-2 text-sm text-muted">
              {injury.player_name}: {injury.result}
              {injury.mercy_gold ? ` · red de novatos ${gold(injury.mercy_gold)}` : ""}
              {injury.note ? ` · ${injury.note}` : ""}
            </p>
          ))}
        </section>
      )}
      <section className="rounded-3xl border border-line bg-card p-4">
        <h2 className="font-display text-lg uppercase">Eventos</h2>
        <ul className="mt-2 space-y-1">
          {match.events.map((event) => (
            <li key={event.id} className="text-sm text-muted">
              {event.player_name} · {EVENT_LABEL[event.event_type] || event.event_type}
              {event.spp_awarded ? ` +${event.spp_awarded}` : ""}
            </li>
          ))}
        </ul>
      </section>
      {(match.weather || match.kick_off || match.prayer) && (
        <section className="rounded-3xl border border-line bg-card p-4 text-sm text-muted">
          {match.weather && <p>Clima {match.weather.roll}: {match.weather.name}</p>}
          {match.prayer && <p>Plegaria {match.prayer.roll}: {match.prayer.name}</p>}
          {match.kick_off && <p>Saque {match.kick_off.roll}: {match.kick_off.name}</p>}
        </section>
      )}
    </div>
  );
}

function Info({ label, text }: { label: string; text: string }) {
  return (
    <section className="rounded-3xl border border-line bg-card p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-gold">{label}</p>
      <p className="mt-1 text-sm leading-snug">{text}</p>
    </section>
  );
}
