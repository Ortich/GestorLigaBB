"use client";

import Link from "next/link";
import { useState } from "react";

import { Alert, Sheet } from "@/components/ui";
import { api, formatGold } from "@/lib/api";
import { EVENT_ICON, EVENT_LABEL } from "@/lib/labels";
import type { CompletionReport, MatchDetail, Player, TeamSummary } from "@/lib/types";

/** Paso 4: cierre del acta (ganancias, MVP, bounty) y procesado de lesiones. */
export function ClosingSheet({
  match,
  open,
  onClose,
  onCompleted,
}: {
  match: MatchDetail;
  open: boolean;
  onClose: () => void;
  onCompleted: (report: CompletionReport) => void;
}) {
  const [homeMvp, setHomeMvp] = useState<number | "">("");
  const [awayMvp, setAwayMvp] = useState<number | "">("");
  const [homeRoll, setHomeRoll] = useState<number | "">("");
  const [awayRoll, setAwayRoll] = useState<number | "">("");
  const [bountyWinner, setBountyWinner] = useState<number | "">("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const eligible = (players: Player[]) => players.filter((p) => p.status !== "RETIRED");

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const report = await api<CompletionReport>(`/api/matches/${match.id}/complete`, {
        method: "POST",
        auth: true,
        body: {
          home_mvp_player_id: homeMvp === "" ? null : homeMvp,
          away_mvp_player_id: awayMvp === "" ? null : awayMvp,
          home_winnings_roll: homeRoll === "" ? null : homeRoll,
          away_winnings_roll: awayRoll === "" ? null : awayRoll,
          bounty_winner_team_id: bountyWinner === "" ? null : bountyWinner,
        },
      });
      onCompleted(report);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const sides: { team: TeamSummary; players: Player[]; mvp: number | ""; setMvp: (v: number | "") => void; roll: number | ""; setRoll: (v: number | "") => void }[] = [
    {
      team: match.home_team,
      players: match.home_players,
      mvp: homeMvp,
      setMvp: setHomeMvp,
      roll: homeRoll,
      setRoll: setHomeRoll,
    },
    {
      team: match.away_team,
      players: match.away_players,
      mvp: awayMvp,
      setMvp: setAwayMvp,
      roll: awayRoll,
      setRoll: setAwayRoll,
    },
  ];

  return (
    <Sheet
      open={open}
      title="Cerrar el acta"
      onClose={onClose}
      footer={
        <button type="button" className="btn-primary flex-1" disabled={busy} onClick={submit}>
          {busy ? "Cerrando..." : "Firmar y cerrar"}
        </button>
      }
    >
      <p className="text-sm text-stone-400">
        Resultado final: <strong className="text-stone-100">{match.home_td} - {match.away_td}</strong>.
        Cada equipo tira 1D6 de ganancias (x10.000 mo). Deja la tirada vacia para que la haga la app.
      </p>

      {sides.map((side) => (
        <div key={side.team.id} className="card-tight space-y-3">
          <p className="font-semibold text-stone-100">
            {side.team.logo} {side.team.name}
          </p>
          <div>
            <label className="label" htmlFor={`mvp-${side.team.id}`}>
              MVP (+4 SPP)
            </label>
            <select
              id={`mvp-${side.team.id}`}
              className="input"
              value={side.mvp}
              onChange={(event) =>
                side.setMvp(event.target.value === "" ? "" : Number(event.target.value))
              }
            >
              <option value="">Sin MVP</option>
              {eligible(side.players).map((player) => (
                <option key={player.id} value={player.id}>
                  #{player.number} {player.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor={`roll-${side.team.id}`}>
              Tirada de ganancias (1-6)
            </label>
            <input
              id={`roll-${side.team.id}`}
              type="number"
              inputMode="numeric"
              min={1}
              max={6}
              className="input"
              placeholder="Automatica"
              value={side.roll}
              onChange={(event) =>
                side.setRoll(event.target.value === "" ? "" : Number(event.target.value))
              }
            />
          </div>
        </div>
      ))}

      {match.bounty && (
        <div className="card-tight">
          <p className="font-semibold text-gold-400">{"\u{1F3AF}"} {match.bounty.name}</p>
          <p className="mb-2 text-xs text-stone-400">{match.bounty.description}</p>
          <select
            className="input"
            aria-label="Equipo que cumple el bounty"
            value={bountyWinner}
            onChange={(event) =>
              setBountyWinner(event.target.value === "" ? "" : Number(event.target.value))
            }
          >
            <option value="">Nadie lo ha cumplido</option>
            <option value={match.home_team.id}>{match.home_team.name}</option>
            <option value={match.away_team.id}>{match.away_team.name}</option>
          </select>
        </div>
      )}

      {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
    </Sheet>
  );
}

export function CompletedView({
  match,
  report,
}: {
  match: MatchDetail;
  report: CompletionReport | null;
}) {
  const winner =
    match.home_td > match.away_td
      ? match.home_team
      : match.away_td > match.home_td
        ? match.away_team
        : null;

  return (
    <>
      <section className="card text-center">
        <p className="text-xs uppercase tracking-widest text-stone-500">Resultado final</p>
        <p className="my-2 text-5xl font-black tabular-nums text-gold-400">
          {match.home_td} - {match.away_td}
        </p>
        <p className="text-sm text-stone-300">
          {match.home_team.logo} {match.home_team.name} vs {match.away_team.name}{" "}
          {match.away_team.logo}
        </p>
        <p className="mt-2 text-sm font-semibold text-stone-100">
          {winner ? `Victoria de ${winner.name}` : "Empate"}
        </p>
      </section>

      <section className="grid grid-cols-2 gap-3">
        {[
          { team: match.home_team, gold: match.home_winnings, roll: match.home_winnings_roll },
          { team: match.away_team, gold: match.away_winnings, roll: match.away_winnings_roll },
        ].map(({ team, gold, roll }) => (
          <div key={team.id} className="card text-center">
            <p className="truncate text-xs text-stone-500">{team.name}</p>
            <p className="text-lg font-black text-stone-100">{formatGold(gold)}</p>
            <p className="text-[11px] text-stone-500">Tirada {roll ?? "-"}</p>
          </div>
        ))}
      </section>

      {report && (
        <>
          {report.injuries.length > 0 && (
            <section className="card">
              <h2 className="section-title">{"\u{1F915}"} Parte medico</h2>
              <ul className="space-y-1.5 text-sm">
                {report.injuries.map((injury, index) => (
                  <li key={index} className="flex justify-between gap-3">
                    <span className="truncate text-stone-200">{injury.player_name}</span>
                    <span className="shrink-0 text-stone-400">{injury.effect}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {report.rookie_safety_payouts.length > 0 && (
            <section className="card">
              <h2 className="section-title">{"\u{1F6DF}"} Red de seguridad de novatos</h2>
              <ul className="space-y-1.5 text-sm">
                {report.rookie_safety_payouts.map((payout, index) => (
                  <li key={index} className="flex justify-between gap-3">
                    <span className="truncate text-stone-200">
                      {payout.team_name} &middot; {payout.player_name} ({payout.percentage}%)
                    </span>
                    <span className="shrink-0 font-semibold text-gold-400">
                      +{formatGold(payout.gold)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {report.bounty_payout && (
            <section className="card">
              <h2 className="section-title">{"\u{1F3AF}"} Bounty</h2>
              <p className="text-sm text-stone-200">
                {report.bounty_payout.team_name} cumple &laquo;{report.bounty_payout.bounty}&raquo; y
                cobra {formatGold(report.bounty_payout.gold)}.
              </p>
            </section>
          )}

          {report.sponsors.length > 0 && (
            <section className="card">
              <h2 className="section-title">{"\u{1F4BC}"} Reparto de patrocinadores</h2>
              <ul className="space-y-1.5 text-sm">
                {report.sponsors.map((assignment) => (
                  <li key={assignment.sponsor_code} className="flex justify-between gap-3">
                    <span className="truncate text-stone-200">{assignment.sponsor_name}</span>
                    <span className="shrink-0 text-stone-400">
                      {assignment.team_name ?? "sin candidato"}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      <section className="card">
        <h2 className="section-title">{"\u{1F4DC}"} Acta</h2>
        {match.events.length === 0 ? (
          <p className="text-sm text-stone-400">Sin eventos registrados.</p>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {match.events.map((event) => (
              <li key={event.id} className="flex items-center gap-2">
                <span>{EVENT_ICON[event.event_type]}</span>
                <span className="min-w-0 flex-1 truncate text-stone-200">
                  {EVENT_LABEL[event.event_type]}
                  {event.player_name ? ` \u00b7 ${event.player_name}` : ""}
                </span>
                <span className="shrink-0 text-xs text-stone-500">{event.team_name}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Link href="/liga" className="btn-secondary w-full">
        Ver la clasificacion
      </Link>
    </>
  );
}
