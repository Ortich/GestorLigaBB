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
  { type: "CAS", label: "Bloqueo", style: "bg-blood-600 text-white hover:bg-blood-500" },
  { type: "INJURY", label: "Lesion", style: "bg-rose-800 text-white hover:bg-rose-700" },
  { type: "PASS", label: "Pase", style: "bg-sky-600 text-white hover:bg-sky-500" },
  { type: "FOUL", label: "Falta", style: "bg-amber-600 text-white hover:bg-amber-500" },
  { type: "INT", label: "Intercepcion", style: "btn-secondary" },
];

/** Acciones que dan PE / se atribuyen a un jugador y exigen autor. */
const REQUIRES_PLAYER: EventType[] = ["TD", "CAS", "INJURY", "PASS", "INT", "FOUL"];

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
  const [pickPlayerFor, setPickPlayerFor] = useState<Pending | null>(null);
  const [blockFor, setBlockFor] = useState<Pending | null>(null);
  const [injuryFor, setInjuryFor] = useState<Pending | null>(null);
  const [victim, setVictim] = useState<Player | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showLog, setShowLog] = useState(false);

  const resetSheets = () => {
    setPending(null);
    setPickPlayerFor(null);
    setBlockFor(null);
    setInjuryFor(null);
    setVictim(null);
  };

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
      resetSheets();
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

  const startBlock = (choice: Pending) => {
    setPending(null);
    setPickPlayerFor(null);
    setVictim(null);
    setBlockFor(choice);
  };

  const startInjury = (choice: Pending) => {
    setPending(null);
    setPickPlayerFor(null);
    setInjuryFor(choice);
  };

  const pickAction = (choice: Pending, type: EventType) => {
    if (type === "CAS") {
      if (!choice.player) {
        setPending(null);
        setPickPlayerFor({ ...choice, type });
        return;
      }
      startBlock(choice);
      return;
    }
    if (type === "INJURY") {
      if (!choice.player) {
        setPending(null);
        setPickPlayerFor({ ...choice, type });
        return;
      }
      startInjury(choice);
      return;
    }
    if (REQUIRES_PLAYER.includes(type) && !choice.player) {
      setPending(null);
      setPickPlayerFor({ ...choice, type });
      return;
    }
    void send({
      team_id: choice.team.id,
      event_type: type,
      player_id: choice.player?.id ?? null,
      turn,
    });
  };

  const confirmPlayer = (player: Player) => {
    if (!pickPlayerFor?.type) return;
    const next = { ...pickPlayerFor, player };
    if (pickPlayerFor.type === "CAS") {
      startBlock(next);
      return;
    }
    if (pickPlayerFor.type === "INJURY") {
      startInjury(next);
      return;
    }
    void send({
      team_id: next.team.id,
      event_type: pickPlayerFor.type,
      player_id: player.id,
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

  const teamPlayers = (teamId: number) =>
    (teamId === match.home_team.id ? match.home_players : match.away_players).filter(
      (player) => player.status !== "DEAD" && player.status !== "RETIRED",
    );

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
                        {" · "}
                        {player.spp_available ?? player.spp} PE
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
              : `${pending.team.name} (elige jugador luego)`
            : ""
        }
        onClose={() => setPending(null)}
      >
        <p className="text-sm text-stone-400">
          Turno {turn}.{" "}
          {pending?.player
            ? "Elige la accion a registrar."
            : "Bloqueo = baja que causas tu (+2 PE). Lesion = herida sin PE (falta, publico...)."}
        </p>
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
        open={pickPlayerFor !== null}
        title={
          pickPlayerFor?.type === "INJURY"
            ? "Quien resulta lesionado?"
            : pickPlayerFor?.type
              ? `Quien realiza el ${EVENT_LABEL[pickPlayerFor.type]}?`
              : "Elige jugador"
        }
        onClose={() => setPickPlayerFor(null)}
      >
        {pickPlayerFor && (
          <>
            <p className="text-sm text-stone-400">
              {pickPlayerFor.type === "CAS"
                ? "Elige al jugador que provoca la baja con el bloqueo (+2 PE)."
                : pickPlayerFor.type === "INJURY"
                  ? "Elige al jugador herido (falta, empujon al publico, armas...). No da PE."
                  : "Los PE se suman a este jugador."}
            </p>
            <div className="space-y-1.5">
              {teamPlayers(pickPlayerFor.team.id).map((player) => (
                <button
                  key={player.id}
                  type="button"
                  className="btn btn-secondary w-full justify-start"
                  disabled={busy}
                  onClick={() => confirmPlayer(player)}
                >
                  #{player.number} {player.name}
                </button>
              ))}
            </div>
          </>
        )}
      </Sheet>

      <Sheet
        open={blockFor !== null}
        title="Registrar bloqueo"
        onClose={() => {
          setBlockFor(null);
          setVictim(null);
        }}
      >
        {blockFor && !victim && (
          <>
            <p className="text-sm text-stone-400">
              {blockFor.player
                ? `${blockFor.player.name} ha causado la baja. Elige a la victima de ${
                    rivalOf(blockFor.team.id).team.name
                  }.`
                : `Elige a la victima de ${rivalOf(blockFor.team.id).team.name}.`}
            </p>
            <div className="space-y-1.5">
              {rivalOf(blockFor.team.id)
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
              disabled={busy || !blockFor.player}
              onClick={() =>
                send({
                  team_id: blockFor.team.id,
                  event_type: "CAS",
                  player_id: blockFor.player?.id ?? null,
                  is_block_casualty: true,
                  turn,
                })
              }
            >
              Anotar el bloqueo sin indicar victima (+2 PE)
            </button>
          </>
        )}

        {blockFor && victim && (
          <>
            <p className="text-sm text-stone-400">
              Resultado de la tirada de heridas de{" "}
              <strong className="text-stone-200">{victim.name}</strong>. Se aplicara al cerrar el
              acta.
            </p>
            <div className="space-y-1.5">
              {CASUALTY_ORDER.map((result) => (
                <button
                  key={result}
                  type="button"
                  disabled={busy || !blockFor.player}
                  className={`btn w-full justify-start text-sm ${
                    result === "DEAD" ? "bg-blood-700 text-white" : "btn-secondary"
                  }`}
                  onClick={() =>
                    send({
                      team_id: blockFor.team.id,
                      event_type: "CAS",
                      player_id: blockFor.player?.id ?? null,
                      victim_player_id: victim.id,
                      casualty_result: result,
                      is_block_casualty: true,
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

      <Sheet
        open={injuryFor !== null}
        title="Registrar lesion"
        onClose={() => setInjuryFor(null)}
      >
        {injuryFor?.player && (
          <>
            <p className="text-sm text-stone-400">
              Resultado de la tirada de heridas de{" "}
              <strong className="text-stone-200">{injuryFor.player.name}</strong> (sin PE: falta,
              publico, armas...). Se aplicara al cerrar el acta.
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
                      team_id: injuryFor.team.id,
                      event_type: "INJURY",
                      player_id: injuryFor.player!.id,
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
                    {event.spp_awarded ? ` \u00b7 +${event.spp_awarded} PE` : ""}
                    {event.event_type === "INJURY" ? " \u00b7 sin PE" : ""}
                    {event.victim_player_name && event.event_type === "CAS"
                      ? ` \u00b7 victima: ${event.victim_player_name}`
                      : ""}
                    {event.casualty_result ? ` \u00b7 ${CASUALTY_LABEL[event.casualty_result]}` : ""}
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
