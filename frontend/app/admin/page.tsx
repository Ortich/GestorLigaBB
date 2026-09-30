"use client";

import { useEffect, useState } from "react";
import { api, gold, STATUS_LABEL } from "@/lib/api";
import type { Bounty, Player, Rules, ShortMatch, Standing, TeamCard } from "@/lib/types";
import { Banner, BigButton, Shell } from "@/components/ui";

type Overview = {
  league: {
    current_round: number;
    active_bounty: Bounty | null;
    sponsor_log: string[];
    standings: Standing[];
  };
  teams: TeamCard[];
  players: Player[];
  matches: ShortMatch[];
};

const STATUSES = ["SCHEDULED", "READY_CHECK", "PRE_MATCH", "IN_PROGRESS", "COMPLETED"];

export default function AdminPage() {
  const [key, setKey] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [rules, setRules] = useState<Rules | null>(null);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [round, setRound] = useState(1);
  const [teamId, setTeamId] = useState<number | null>(null);

  function load() {
    api<Overview>("/api/admin/overview", { admin: true })
      .then((data) => {
        setOverview(data);
        setRound(data.league.current_round);
        setTeamId((current) => current ?? data.teams[0]?.id ?? null);
        setError("");
      })
      .catch((err: Error) => {
        if (err.message.toLowerCase().includes("comisario") || err.message.toLowerCase().includes("sesión")) {
          window.localStorage.removeItem("bb_admin_token");
          setOverview(null);
        }
        setError(err.message);
      });
  }

  useEffect(() => {
    api<Rules>("/api/rules", { token: null }).then(setRules).catch(() => undefined);
    if (window.localStorage.getItem("bb_admin_token")) load();
  }, []);

  async function enter() {
    setError("");
    try {
      const result = await api<{ token: string }>("/api/admin/login", { body: { master_key: key }, token: null });
      window.localStorage.setItem("bb_admin_token", result.token);
      setKey("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Llave incorrecta.");
    }
  }

  if (!overview) {
    return (
      <Shell title="Comisario" eyebrow="Acceso reservado">
        {error && <Banner>{error}</Banner>}
        <p className="mb-4 text-sm leading-relaxed text-muted">
          Esta ruta no está enlazada desde la liga. Sirve para corregir actas, oro y lesiones.
        </p>
        <input
          type="password"
          value={key}
          onChange={(event) => setKey(event.target.value)}
          className="min-h-14 w-full rounded-2xl border border-line bg-card px-4"
          placeholder="Llave maestra"
        />
        <div className="mt-3">
          <BigButton disabled={!key} onClick={() => void enter()}>
            Entrar
          </BigButton>
        </div>
      </Shell>
    );
  }

  const visible = overview.matches.filter((match) => match.round_number === round);
  const players = overview.players.filter((player) => player.team_id === teamId);
  return (
    <Shell
      title="Comisario"
      eyebrow={`Jornada ${overview.league.current_round}`}
      action={
        <button
          className="text-xs font-semibold uppercase text-muted"
          onClick={() => {
            window.localStorage.removeItem("bb_admin_token");
            setOverview(null);
          }}
        >
          Salir
        </button>
      }
    >
      {error && <Banner>{error}</Banner>}
      {info && <Banner tone="info">{info}</Banner>}
      <section className="mb-4 rounded-3xl border border-line bg-card p-4">
        <h2 className="font-display text-xl uppercase">Jornada y recompensa</h2>
        <div className="mt-3 flex gap-2">
          <input
            inputMode="numeric"
            value={round}
            onChange={(event) => setRound(Number(event.target.value || 1))}
            className="min-h-12 w-20 rounded-2xl border border-line bg-ink/40 px-3 text-center"
          />
          <button
            className="min-h-12 flex-1 rounded-2xl bg-card2 font-semibold"
            onClick={() =>
              api("/api/admin/round", { admin: true, body: { round_number: round } })
                .then(() => {
                  setInfo(`La jornada actual pasa a ser la ${round}.`);
                  load();
                })
                .catch((err: Error) => setError(err.message))
            }
          >
            Fijar jornada
          </button>
        </div>
        <select
          className="mt-3 min-h-12 w-full rounded-2xl border border-line bg-ink/40 px-3"
          value={overview.league.active_bounty?.id || ""}
          onChange={(event) =>
            api("/api/admin/bounty", {
              admin: true,
              body: { bounty_id: event.target.value || null },
            })
              .then(() => load())
              .catch((err: Error) => setError(err.message))
          }
        >
          <option value="">Sin recompensa</option>
          {rules?.bounties.map((bounty) => (
            <option key={bounty.id} value={bounty.id}>
              {bounty.name}
            </option>
          ))}
        </select>
      </section>
      <section className="mb-4 rounded-3xl border border-blood/50 bg-card p-4">
        <h2 className="font-display text-xl uppercase text-blood">Recalcular liga</h2>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Regenera patrocinadores desde los partidos cerrados. No toca tesorerías ni PEP. Si un equipo lidera dos métricas, la prioridad automática es Sindicato, Tabernero, Carnicería y Prensa, y elige antes el que está más abajo.
        </p>
        <div className="mt-3">
          <BigButton
            tone="blood"
            onClick={() => {
              if (!window.confirm("¿Reasignar los cuatro patrocinadores desde el historial?")) return;
              api<{ log: string[] }>("/api/admin/recalculate", { admin: true, body: {} })
                .then((result) => {
                  setInfo(result.log.join(" "));
                  load();
                })
                .catch((err: Error) => setError(err.message));
            }}
          >
            Recalcular
          </BigButton>
        </div>
        {overview.league.sponsor_log.length > 0 && (
          <div className="mt-3 space-y-2 text-sm text-muted">
            {overview.league.sponsor_log.map((line) => (
              <p key={line}>{line}</p>
            ))}
          </div>
        )}
      </section>
      <section className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-display text-xl uppercase">Actas</h2>
          <div className="flex gap-1">
            <button className="h-10 w-10 rounded-full bg-card2" onClick={() => setRound(Math.max(1, round - 1))}>
              −
            </button>
            <button className="h-10 w-10 rounded-full bg-card2" onClick={() => setRound(round + 1)}>
              +
            </button>
          </div>
        </div>
        <div className="space-y-3">
          {visible.map((match) => (
            <MatchAdmin key={match.id} match={match} onChanged={load} onError={setError} />
          ))}
          {visible.length === 0 && <p className="text-sm text-muted">No hay partidos en esa jornada.</p>}
        </div>
      </section>
      <section className="mb-4 rounded-3xl border border-line bg-card p-4">
        <h2 className="font-display text-xl uppercase">Tesorería y PIN</h2>
        <div className="mt-3 space-y-3">
          {overview.teams.map((team) => (
            <TeamAdmin key={team.id} team={team} onChanged={load} onError={setError} />
          ))}
        </div>
      </section>
      <section className="rounded-3xl border border-line bg-card p-4">
        <h2 className="font-display text-xl uppercase">Salud de la plantilla</h2>
        <select
          className="mt-3 min-h-12 w-full rounded-2xl border border-line bg-ink/40 px-3"
          value={teamId ?? ""}
          onChange={(event) => setTeamId(Number(event.target.value))}
        >
          {overview.teams.map((team) => (
            <option key={team.id} value={team.id}>
              {team.name}
            </option>
          ))}
        </select>
        <div className="mt-3 space-y-2">
          {players.map((player) => (
            <article key={player.id} className="rounded-2xl bg-ink/30 p-3">
              <p className="font-semibold">
                {player.number}. {player.name}
              </p>
              <p className="text-xs text-muted">
                {player.position} · {STATUS_LABEL[player.status] || player.status} · {player.spp} PEP
              </p>
              <div className="mt-2 grid grid-cols-3 gap-1">
                {["ACTIVE", "MNG", "DEAD"].map((status) => (
                  <button
                    key={status}
                    className={`min-h-10 rounded-xl text-[11px] font-bold uppercase ${
                      player.status === status ? "bg-gold text-ink" : "bg-card2"
                    }`}
                    onClick={() =>
                      api(`/api/admin/players/${player.id}/status`, { admin: true, body: { status } })
                        .then(() => load())
                        .catch((err: Error) => setError(err.message))
                    }
                  >
                    {status === "ACTIVE" ? "Vivo" : status === "MNG" ? "MNG" : "Muerto"}
                  </button>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </Shell>
  );
}

function MatchAdmin({
  match,
  onChanged,
  onError,
}: {
  match: ShortMatch;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [status, setStatus] = useState(match.status);
  const [homeTd, setHomeTd] = useState(String(match.home_td));
  const [awayTd, setAwayTd] = useState(String(match.away_td));
  const [events, setEvents] = useState<{ id: number; player_name: string; event_type: string; spp_awarded: number }[] | null>(null);
  return (
    <article className="rounded-3xl border border-line bg-card p-4">
      <h3 className="font-display text-lg uppercase leading-tight">
        {match.home_name} {match.home_td} - {match.away_td} {match.away_name}
      </h3>
      <p className="text-xs text-muted">{STATUS_LABEL[match.status] || match.status}</p>
      <div className="mt-3 flex gap-2">
        <select
          className="min-h-12 flex-1 rounded-2xl border border-line bg-ink/40 px-2"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          {STATUSES.map((item) => (
            <option key={item} value={item}>
              {STATUS_LABEL[item]}
            </option>
          ))}
        </select>
        <button
          className="min-h-12 rounded-2xl bg-gold px-3 font-semibold text-ink"
          onClick={() =>
            api(`/api/admin/matches/${match.id}/status`, { admin: true, body: { status } })
              .then(() => onChanged())
              .catch((err: Error) => onError(err.message))
          }
        >
          Estado
        </button>
      </div>
      <div className="mt-2 grid grid-cols-[1fr_1fr_auto] gap-2">
        <input className="min-h-12 rounded-2xl border border-line bg-ink/40 px-3 text-center" value={homeTd} onChange={(event) => setHomeTd(event.target.value.replace(/[^\d]/g, ""))} />
        <input className="min-h-12 rounded-2xl border border-line bg-ink/40 px-3 text-center" value={awayTd} onChange={(event) => setAwayTd(event.target.value.replace(/[^\d]/g, ""))} />
        <button
          className="min-h-12 rounded-2xl bg-card2 px-3 font-semibold"
          onClick={() =>
            api(`/api/admin/matches/${match.id}/score`, {
              admin: true,
              method: "PATCH",
              body: { home_td: Number(homeTd || 0), away_td: Number(awayTd || 0) },
            })
              .then(() => onChanged())
              .catch((err: Error) => onError(err.message))
          }
        >
          Marcador
        </button>
      </div>
      <button
        className="mt-3 text-sm font-semibold text-gold"
        onClick={() =>
          api<{ events: { id: number; player_name: string; event_type: string; spp_awarded: number }[] }>(
            `/api/admin/matches/${match.id}`,
            { admin: true },
          )
            .then((data) => setEvents(data.events))
            .catch((err: Error) => onError(err.message))
        }
      >
        {events ? "Ocultar eventos" : "Ver eventos"}
      </button>
      {events && (
        <ul className="mt-2 space-y-2">
          {events.length === 0 && <li className="text-sm text-muted">Sin eventos.</li>}
          {events.map((event) => (
            <li key={event.id} className="flex items-center justify-between gap-2 text-sm">
              <span>
                {event.player_name} · {event.event_type}
                {event.spp_awarded ? ` +${event.spp_awarded}` : ""}
              </span>
              <button
                className="rounded-xl bg-blood px-3 py-2 text-xs font-bold uppercase"
                onClick={() =>
                  api(`/api/admin/events/${event.id}`, { admin: true, method: "DELETE" })
                    .then(() => {
                      setEvents(null);
                      onChanged();
                    })
                    .catch((err: Error) => onError(err.message))
                }
              >
                Borrar
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[11px] leading-snug text-muted">
        Forzar el estado no deshace el oro ni las lesiones. Borrar un evento sí revierte sus PEP y, si era un touchdown, el marcador.
      </p>
    </article>
  );
}

function TeamAdmin({
  team,
  onChanged,
  onError,
}: {
  team: TeamCard;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [delta, setDelta] = useState("10000");
  const [pin, setPin] = useState(team.pin || "");
  return (
    <article className="rounded-2xl bg-ink/30 p-3">
      <p className="font-display text-lg uppercase leading-tight">{team.name}</p>
      <p className="text-sm text-muted">
        {gold(team.treasury)} · PIN {team.pin}
        {team.sponsor ? ` · ${team.sponsor.name}` : ""}
      </p>
      <div className="mt-2 flex gap-2">
        <input
          inputMode="numeric"
          value={delta}
          onChange={(event) => setDelta(event.target.value.replace(/[^\d]/g, ""))}
          className="min-h-12 flex-1 rounded-2xl border border-line bg-card px-3"
        />
        <button
          className="min-h-12 rounded-2xl bg-pitch px-3 text-sm font-bold"
          onClick={() =>
            api(`/api/admin/teams/${team.id}/treasury`, { admin: true, body: { delta: Number(delta || 0) } })
              .then(() => onChanged())
              .catch((err: Error) => onError(err.message))
          }
        >
          Sumar
        </button>
        <button
          className="min-h-12 rounded-2xl bg-blood px-3 text-sm font-bold"
          onClick={() =>
            api(`/api/admin/teams/${team.id}/treasury`, { admin: true, body: { delta: -Number(delta || 0) } })
              .then(() => onChanged())
              .catch((err: Error) => onError(err.message))
          }
        >
          Restar
        </button>
      </div>
      <div className="mt-2 flex gap-2">
        <input
          inputMode="numeric"
          value={pin}
          maxLength={4}
          onChange={(event) => setPin(event.target.value.replace(/[^\d]/g, "").slice(0, 4))}
          className="min-h-12 w-28 rounded-2xl border border-line bg-card px-3 text-center"
        />
        <button
          className="min-h-12 flex-1 rounded-2xl bg-card2 text-sm font-semibold disabled:opacity-40"
          disabled={pin.length !== 4}
          onClick={() =>
            api(`/api/admin/teams/${team.id}/pin`, { admin: true, body: { pin } })
              .then(() => onChanged())
              .catch((err: Error) => onError(err.message))
          }
        >
          Cambiar PIN
        </button>
      </div>
    </article>
  );
}
