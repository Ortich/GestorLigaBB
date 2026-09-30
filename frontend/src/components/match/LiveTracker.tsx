"use client";

import { useState } from "react";

import { Alert, Sheet } from "@/components/ui";
import { api } from "@/lib/api";
import { CASUALTY_LABEL, EVENT_ICON, EVENT_LABEL } from "@/lib/labels";
import type {
  CasualtyResult,
  EventType,
  MatchDetail,
  Player,
  TeamSummary,
} from "@/lib/types";

const QUICK_ACTIONS: { type: EventType; label: string; style: string }[] = [
  { type: "TD", label: "Touchdown", style: "bg-emerald-600 text-white hover:bg-emerald-500" },
  { type: "CAS", label: "Baja", style: "bg-blood-600 text-white hover:bg-blood-500" },
  { type: "PASS", label: "Pase", style: "bg-sky-600 text-white hover:bg-sky-500" },
  { type: "FOUL", label: "Falta", style: "bg-amber-600 text-white hover:bg-amber-500" },
  { type: "INT", label: "Intercepcion", style: "btn-secondary" },
];

const CASUALTY_ORDER: CasualtyResult[] = [
  "BADLY_HURT",
  "SERIOUSLY_HURT",
  "SERIOUS_INJURY",
  "LASTING_INJURY_MA",
  "LASTING_INJURY_ST",
  "LASTING_INJURY_AG",
  "LASTING_INJURY_PA",
  "LASTING_INJURY_AV",
  "DEAD",
];

interface Pending {
  team: TeamSummary;
  player: Player | null;
  type?: EventType;
}

/** Paso 3: registro en vivo a dos columnas (local vs visitante). */
export function LiveTracker({
  match,
  onUpdated,
  onFinish,
}: {
  match: MatchDetail;
  onUpdated: (next: MatchDetail) => void;
  onFinish: () => void;
}) {
  const [turn, setTurn] = useState(1);
  const [pending, setPending] = useState<Pending | null>(null);
  const [victimFor, setVictimFor] = useState<Pending | null>(null);
  const [victim, setVictim] = useState<Player | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showLog, setShowLog] = useState(false);

  const send = async (body: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      onUpdated(
        await api<MatchDetail>(`/api/matches/${match.id}/events`, {
          method: "POST",
          auth: true,
          body,
        }),
      );
      setPending(null);
      setVictimFor(null);
      setVictim(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const removeEvent = async (eventId: number) => {
    setBusy(true);
    try {
      onUpdated(
        await api<MatchDetail>(`/api/matches/${match.id}/events/${eventId}`, {
          method: "DELETE",
          auth: true,
        }),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const pickAction = (choice: Pending, type: EventType) => {
    if (type === "CAS") {
      setPending(null);
      setVictimFor({ ...choice, type });
      return;
    }
    void send({
      team_id: choice.team.id,
      event_type: type,
      player_id: choice.player?.id ?? null,
      turn,
    });
  };

  const columns: { team: TeamSummary; players: Player[]; score: number }[] = [
    { team: match.home_team, players: match.home_players, score: match.home_td },
    { team: match.away_team, players: match.away_players, score: match.away_td },
  ];

  const rivalOf = (teamId: number) =>
    teamId === match.home_team.id
      ? { team: match.away_team, players: match.away_players }
      : { team: match.home_team, players: match.home_players };

  return (
    <>
      <div className="sticky top-[57px] z-20 -mx-4 border-b border-white/10 bg-pitch-950/95 px-4 py-3 backdrop-blur">
        <div className="flex items-center justify-between gap-2">
          <ScoreSide team={match.home_team} score={match.home_td} />
          <div className="shrink-0 text-center">
            <p className="text-3xl font-black tabular-nums text-gold-400">
              {match.home_td} - {match.away_td}
            </p>
            <div className="mt-1 flex items-center justify-center gap-1.5">
              <button
                type="button"
                className="btn btn-secondary btn-sm h-7 w-7 px-0 text-xs"
                onClick={() => setTurn((t) => Math.max(1, t - 1))}
                aria-label="Turno anterior"
              >
                -
              </button>
              <span className="text-[11px] uppercase tracking-wider text-stone-400">
                Turno {turn}
              </span>
              <button
                type="button"
                className="btn btn-secondary btn-sm h-7 w-7 px-0 text-xs"
                onClick={() => setTurn((t) => Math.min(16, t + 1))}
                aria-label="Turno siguiente"
              >
                +
              </button>
            </div>
          </div>
          <ScoreSide team={match.away_team} score={match.away_td} align="right" />
        </div>
      </div>

      {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}

      <div className="grid grid-cols-2 gap-2">
        {columns.map(({ team, players }) => (
          <div key={team.id} className="space-y-1.5">
            <button
              type="button"
              className="btn btn-secondary btn-sm w-full"
              onClick={() => setPending({ team, player: null })}
            >
              + Evento de equipo
            </button>
            {players
              .filter((player) => player.status !== "DEAD" && player.status !== "RETIRED")
              .map((player) => {
                const stats = match.events.filter((event) => event.player_id === player.id);
                return (
                  <button
                    key={player.id}
                    type="button"
                    onClick={() => setPending({ team, player })}
                    className="card-tight flex w-full items-center gap-2 px-2 py-2 text-left active:scale-[0.98]"
                  >
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-pitch-800 text-xs font-bold text-gold-400">
                      {player.number}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-semibold text-stone-100">
                        {player.name}
                      </span>
                      <span className="block truncate text-[10px] text-stone-500">
                        {player.status === "MNG" ? "No disponible" : player.position}
                      </span>
                    </span>
                    {stats.length > 0 && (
                      <span className="shrink-0 text-[10px] leading-tight">
                        {stats.map((event) => EVENT_ICON[event.event_type]).join("")}
                      </span>
                    )}
                  </button>
                );
              })}
          </div>
        ))}
      </div>

      {/* Siempre a mano: la plantilla es larga y el boton no puede quedar al final del scroll. */}
      <div className="fixed bottom-[60px] left-1/2 z-30 flex w-full max-w-xl -translate-x-1/2 gap-2 border-t border-white/10 bg-pitch-950/95 px-4 py-2 backdrop-blur">
        <button type="button" className="btn btn-secondary flex-1" onClick={() => setShowLog(true)}>
          Acta ({match.events.length})
        </button>
        <button type="button" className="btn-primary flex-1" onClick={onFinish}>
          Pitar el final
        </button>
      </div>
      <div className="h-16" />

      <Sheet
        open={pending !== null}
        title={
          pending
            ? pending.player
              ? `#${pending.player.number} ${pending.player.name}`
              : `${pending.team.name} (sin jugador)`
            : ""
        }
        onClose={() => setPending(null)}
      >
        <p className="text-sm text-stone-400">Turno {turn}. Elige la accion a registrar.</p>
        <div className="grid grid-cols-2 gap-2">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.type}
              type="button"
              disabled={busy}
              className={`btn ${action.style}`}
              onClick={() => pending && pickAction(pending, action.type)}
            >
              {EVENT_ICON[action.type]} {action.label}
            </button>
          ))}
        </div>
      </Sheet>

      <Sheet
        open={victimFor !== null}
        title="Registrar baja"
        onClose={() => {
          setVictimFor(null);
          setVictim(null);
        }}
      >
        {victimFor && !victim && (
          <>
            <p className="text-sm text-stone-400">
              Elige al jugador de {rivalOf(victimFor.team.id).team.name} que ha caido.
            </p>
            <div className="space-y-1.5">
              {rivalOf(victimFor.team.id)
                .players.filter((player) => player.status === "ACTIVE")
                .map((player) => (
                  <button
                    key={player.id}
                    type="button"
                    className="btn btn-secondary w-full justify-start"
                    onClick={() => setVictim(player)}
                  >
                    #{player.number} {player.name}
                  </button>
                ))}
            </div>
            <button
              type="button"
              className="btn btn-ghost w-full"
              disabled={busy}
              onClick={() =>
                send({
                  team_id: victimFor.team.id,
                  event_type: "CAS",
                  player_id: victimFor.player?.id ?? null,
                  turn,
                })
              }
            >
              Anotar la baja sin indicar victima
            </button>
          </>
        )}

        {victimFor && victim && (
          <>
            <p className="text-sm text-stone-400">
              Resultado de la tirada de heridas de{" "}
              <strong className="text-stone-200">{victim.name}</strong>. Se aplicara al cerrar el acta.
            </p>
            <div className="space-y-1.5">
              {CASUALTY_ORDER.map((result) => (
                <button
                  key={result}
                  type="button"
                  disabled={busy}
                  className={`btn w-full justify-start text-sm ${
                    result === "DEAD" ? "bg-blood-700 text-white" : "btn-secondary"
                  }`}
                  onClick={() =>
                    send({
                      team_id: victimFor.team.id,
                      event_type: "CAS",
                      player_id: victimFor.player?.id ?? null,
                      victim_player_id: victim.id,
                      casualty_result: result,
                      turn,
                    })
                  }
                >
                  {CASUALTY_LABEL[result]}
                </button>
              ))}
            </div>
          </>
        )}
      </Sheet>

      <Sheet open={showLog} title="Acta del partido" onClose={() => setShowLog(false)}>
        {match.events.length === 0 ? (
          <p className="text-sm text-stone-400">Todavia no hay eventos registrados.</p>
        ) : (
          <ul className="space-y-2">
            {[...match.events].reverse().map((event) => (
              <li key={event.id} className="card-tight flex items-center gap-3">
                <span className="text-lg">{EVENT_ICON[event.event_type]}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-stone-100">
                    {EVENT_LABEL[event.event_type]}
                    {event.player_name ? ` \u00b7 ${event.player_name}` : ""}
                  </p>
                  <p className="truncate text-xs text-stone-500">
                    {event.team_name}
                    {event.turn ? ` \u00b7 turno ${event.turn}` : ""}
                    {event.spp_awarded ? ` \u00b7 +${event.spp_awarded} SPP` : ""}
                    {event.victim_player_name ? ` \u00b7 victima: ${event.victim_player_name}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm shrink-0"
                  disabled={busy}
                  onClick={() => removeEvent(event.id)}
                >
                  Borrar
                </button>
              </li>
            ))}
          </ul>
        )}
      </Sheet>
    </>
  );
}

function ScoreSide({
  team,
  score,
  align = "left",
}: {
  team: TeamSummary;
  score: number;
  align?: "left" | "right";
}) {
  return (
    <div className={`min-w-0 flex-1 ${align === "right" ? "text-right" : ""}`}>
      <p className="text-xs font-bold leading-tight text-stone-100">
        {align === "left" ? `${team.logo} ` : ""}
        {team.name}
        {align === "right" ? ` ${team.logo}` : ""}
      </p>
      <p className="text-[11px] text-stone-500">{score} TD</p>
    </div>
  );
}
