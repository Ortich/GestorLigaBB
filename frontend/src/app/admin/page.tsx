"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Alert, Sheet, Spinner } from "@/components/ui";
import { api, formatGold, session } from "@/lib/api";
import { EVENT_ICON, EVENT_LABEL, MATCH_STATUS_LABEL, PLAYER_STATUS_LABEL } from "@/lib/labels";
import type {
  Bounty,
  LeagueState,
  MatchDetail,
  MatchStatus,
  MatchSummary,
  PlayerStatus,
  Sponsor,
  StandingRow,
  TeamDetail,
  TeamSummary,
} from "@/lib/types";

interface Overview {
  league: LeagueState;
  teams: TeamSummary[];
  matches: MatchSummary[];
  sponsors: Sponsor[];
  bounties: Bounty[];
}

const STATUSES: MatchStatus[] = [
  "SCHEDULED",
  "READY_CHECK",
  "PRE_MATCH",
  "IN_PROGRESS",
  "COMPLETED",
];

type Tab = "actas" | "equipos" | "liga";

export default function AdminPage() {
  const [unlocked, setUnlocked] = useState(false);
  const [keyInput, setKeyInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<Tab>("actas");

  const load = useCallback(async () => {
    try {
      setOverview(await api<Overview>("/api/admin/overview", { master: true }));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    if (session.masterKey) {
      setUnlocked(true);
      void load();
    }
  }, [load]);

  const unlock = async () => {
    try {
      await api("/api/admin/login", { method: "POST", master: true, masterKey: keyInput });
      session.saveMasterKey(keyInput);
      setUnlocked(true);
      setKeyInput("");
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  if (!unlocked) {
    return (
      <div className="mx-auto flex min-h-[100dvh] w-full max-w-md flex-col justify-center gap-5 px-5">
        <div className="text-center">
          <p className="text-4xl">{"\u{1F3DB}"}</p>
          <h1 className="mt-2 text-2xl font-black uppercase text-stone-50">Panel del comisario</h1>
          <p className="text-sm text-stone-400">Acceso restringido</p>
        </div>
        <div className="card space-y-4">
          <div>
            <label className="label" htmlFor="master">
              Clave maestra
            </label>
            <input
              id="master"
              type="password"
              className="input"
              value={keyInput}
              onChange={(event) => setKeyInput(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && unlock()}
            />
          </div>
          {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
          <button type="button" className="btn-primary w-full" onClick={unlock} disabled={!keyInput}>
            Entrar
          </button>
        </div>
        <Link href="/" className="text-center text-xs text-stone-600 hover:underline">
          Volver al login de equipos
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-[100dvh] w-full max-w-xl px-4 pb-16 pt-4">
      <header className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-black text-stone-50">{"\u{1F3DB}"} Comisario</h1>
          <p className="text-xs text-stone-400">
            {overview?.league.name} &middot; Jornada {overview?.league.current_round}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => {
            session.clearMasterKey();
            setUnlocked(false);
          }}
        >
          Bloquear
        </button>
      </header>

      {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
      {notice && (
        <Alert kind="success" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}

      <div className="mb-4 flex gap-2">
        {(
          [
            ["actas", "Actas"],
            ["equipos", "Tesoreria y salud"],
            ["liga", "Liga"],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`btn btn-sm flex-1 ${tab === id ? "bg-gold-500 text-pitch-950" : "btn-secondary"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {!overview && <Spinner />}

      {overview && tab === "actas" && (
        <MatchManager overview={overview} onError={setError} onNotice={setNotice} onChanged={load} />
      )}
      {overview && tab === "equipos" && (
        <TeamManager overview={overview} onError={setError} onNotice={setNotice} onChanged={load} />
      )}
      {overview && tab === "liga" && (
        <LeagueManager overview={overview} onError={setError} onNotice={setNotice} onChanged={load} />
      )}
    </div>
  );
}

interface PanelProps {
  overview: Overview;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
  onChanged: () => Promise<void>;
}

function MatchManager({ overview, onError, onNotice, onChanged }: PanelProps) {
  const [selected, setSelected] = useState<MatchDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [home, setHome] = useState("");
  const [away, setAway] = useState("");

  const open = async (matchId: number) => {
    try {
      const detail = await api<MatchDetail>(`/api/matches/${matchId}`);
      setSelected(detail);
      setHome(String(detail.home_td));
      setAway(String(detail.away_td));
    } catch (err) {
      onError((err as Error).message);
    }
  };

  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await fn();
      if (selected) await open(selected.id);
      await onChanged();
      onNotice(message);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="space-y-2">
        {overview.matches.map((match) => (
          <button
            key={match.id}
            type="button"
            onClick={() => open(match.id)}
            className="card-tight flex w-full items-center gap-3 text-left"
          >
            <span className="w-8 shrink-0 text-center text-xs text-stone-500">J{match.round_number}</span>
            <span className="min-w-0 flex-1 truncate text-sm text-stone-100">
              {match.home_team_name} vs {match.away_team_name}
            </span>
            <span className="shrink-0 text-sm font-bold tabular-nums text-gold-400">
              {match.home_td}-{match.away_td}
            </span>
            <span className="shrink-0 text-[10px] uppercase text-stone-500">
              {MATCH_STATUS_LABEL[match.status]}
            </span>
          </button>
        ))}
      </div>

      <Sheet
        open={selected !== null}
        title={selected ? `J${selected.round_number}: ${selected.home_team.name} vs ${selected.away_team.name}` : ""}
        onClose={() => setSelected(null)}
      >
        {selected && (
          <>
            <div>
              <p className="label">Forzar estado</p>
              <div className="grid grid-cols-2 gap-2">
                {STATUSES.map((status) => (
                  <button
                    key={status}
                    type="button"
                    disabled={busy || status === selected.status}
                    className={`btn btn-sm ${status === selected.status ? "btn-gold" : "btn-secondary"}`}
                    onClick={() =>
                      run(
                        () =>
                          api(`/api/admin/matches/${selected.id}/status`, {
                            method: "POST",
                            master: true,
                            body: { status },
                          }),
                        `Partido movido a ${MATCH_STATUS_LABEL[status]}.`,
                      )
                    }
                  >
                    {MATCH_STATUS_LABEL[status]}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="label">Marcador manual</p>
              <div className="flex items-center gap-2">
                <input
                  aria-label="TD local"
                  type="number"
                  min={0}
                  className="input text-center"
                  value={home}
                  onChange={(event) => setHome(event.target.value)}
                />
                <span className="text-stone-500">-</span>
                <input
                  aria-label="TD visitante"
                  type="number"
                  min={0}
                  className="input text-center"
                  value={away}
                  onChange={(event) => setAway(event.target.value)}
                />
                <button
                  type="button"
                  className="btn-primary btn-sm shrink-0"
                  disabled={busy}
                  onClick={() =>
                    run(
                      () =>
                        api(`/api/admin/matches/${selected.id}/score`, {
                          method: "PATCH",
                          master: true,
                          body: { home_td: Number(home), away_td: Number(away) },
                        }),
                      "Marcador actualizado.",
                    )
                  }
                >
                  Guardar
                </button>
              </div>
            </div>

            <div>
              <p className="label">Eventos ({selected.events.length})</p>
              {selected.events.length === 0 ? (
                <p className="text-sm text-stone-500">Sin eventos.</p>
              ) : (
                <ul className="space-y-1.5">
                  {selected.events.map((event) => (
                    <li key={event.id} className="card-tight flex items-center gap-2">
                      <span>{EVENT_ICON[event.event_type]}</span>
                      <span className="min-w-0 flex-1 truncate text-xs text-stone-200">
                        {EVENT_LABEL[event.event_type]}
                        {event.player_name ? ` \u00b7 ${event.player_name}` : ""} ({event.team_name})
                      </span>
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm shrink-0"
                        disabled={busy}
                        onClick={() =>
                          run(
                            () =>
                              api(`/api/admin/events/${event.id}`, {
                                method: "DELETE",
                                master: true,
                              }),
                            "Evento eliminado.",
                          )
                        }
                      >
                        Borrar
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </Sheet>
    </>
  );
}

function TeamManager({ overview, onError, onNotice, onChanged }: PanelProps) {
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [amount, setAmount] = useState("10000");
  const [busy, setBusy] = useState(false);

  const open = async (teamId: number) => {
    try {
      setTeam(await api<TeamDetail>(`/api/teams/${teamId}`));
    } catch (err) {
      onError((err as Error).message);
    }
  };

  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await fn();
      if (team) await open(team.id);
      await onChanged();
      onNotice(message);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="space-y-2">
        {overview.teams.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => open(item.id)}
            className="card-tight flex w-full items-center gap-3 text-left"
          >
            <span className="text-xl">{item.logo}</span>
            <span className="min-w-0 flex-1 truncate text-sm text-stone-100">{item.name}</span>
            <span className="shrink-0 text-xs text-gold-400">{formatGold(item.treasury)}</span>
          </button>
        ))}
      </div>

      <Sheet
        open={team !== null}
        title={team ? `${team.logo} ${team.name}` : ""}
        onClose={() => setTeam(null)}
      >
        {team && (
          <>
            <div>
              <p className="label">Tesoreria: {formatGold(team.treasury)}</p>
              <div className="flex gap-2">
                <input
                  aria-label="Cantidad de oro"
                  type="number"
                  className="input"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                />
                <button
                  type="button"
                  className="btn-secondary btn-sm shrink-0"
                  disabled={busy}
                  onClick={() =>
                    run(
                      () =>
                        api(`/api/admin/teams/${team.id}/treasury`, {
                          method: "POST",
                          master: true,
                          body: { delta: -Math.abs(Number(amount)) },
                        }),
                      "Oro restado.",
                    )
                  }
                >
                  Restar
                </button>
                <button
                  type="button"
                  className="btn-gold btn-sm shrink-0"
                  disabled={busy}
                  onClick={() =>
                    run(
                      () =>
                        api(`/api/admin/teams/${team.id}/treasury`, {
                          method: "POST",
                          master: true,
                          body: { delta: Math.abs(Number(amount)) },
                        }),
                      "Oro anadido.",
                    )
                  }
                >
                  Sumar
                </button>
              </div>
            </div>

            <div>
              <p className="label">Estado de los jugadores</p>
              <ul className="space-y-1.5">
                {team.players.map((player) => (
                  <li key={player.id} className="card-tight flex items-center gap-2">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-stone-100">
                        #{player.number} {player.name}
                      </span>
                      <span className="block text-[11px] text-stone-500">
                        {PLAYER_STATUS_LABEL[player.status]} &middot; {player.spp} SPP
                      </span>
                    </span>
                    <select
                      aria-label={`Estado de ${player.name}`}
                      className="min-h-[40px] shrink-0 rounded-lg border border-white/15 bg-pitch-950 px-2 text-xs"
                      value={player.status}
                      disabled={busy}
                      onChange={(event) =>
                        run(
                          () =>
                            api(`/api/admin/players/${player.id}`, {
                              method: "PATCH",
                              master: true,
                              body: { status: event.target.value as PlayerStatus },
                            }),
                          `${player.name} actualizado.`,
                        )
                      }
                    >
                      {(["ACTIVE", "MNG", "DEAD", "RETIRED"] as PlayerStatus[]).map((status) => (
                        <option key={status} value={status}>
                          {PLAYER_STATUS_LABEL[status]}
                        </option>
                      ))}
                    </select>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
      </Sheet>
    </>
  );
}

function LeagueManager({ overview, onError, onNotice, onChanged }: PanelProps) {
  const [round, setRound] = useState(String(overview.league.current_round));
  const [bounty, setBounty] = useState(String(overview.league.active_bounty?.id ?? ""));
  const [standings, setStandings] = useState<StandingRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    api<StandingRow[]>("/api/league/standings").then(setStandings).catch(() => setStandings([]));
  }, [overview]);

  const run = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    try {
      await fn();
      await onChanged();
      setStandings(await api<StandingRow[]>("/api/league/standings"));
      onNotice(message);
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="card space-y-3">
        <h2 className="section-title">Estado de la liga</h2>
        <div>
          <label className="label" htmlFor="round">
            Jornada actual
          </label>
          <input
            id="round"
            type="number"
            min={1}
            className="input"
            value={round}
            onChange={(event) => setRound(event.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="bounty">
            Bounty activo
          </label>
          <select
            id="bounty"
            className="input"
            value={bounty}
            onChange={(event) => setBounty(event.target.value)}
          >
            <option value="">Ninguno</option>
            {overview.bounties.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} (+{formatGold(item.reward_gold)})
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="btn-primary w-full"
          disabled={busy}
          onClick={() =>
            run(
              () =>
                api("/api/admin/league", {
                  method: "PATCH",
                  master: true,
                  body: {
                    current_round: Number(round),
                    active_bounty_id: bounty === "" ? 0 : Number(bounty),
                  },
                }),
              "Estado de liga guardado.",
            )
          }
        >
          Guardar
        </button>
      </div>

      <div className="card space-y-3">
        <h2 className="section-title">Patrocinadores</h2>
        {overview.sponsors.map((sponsor) => {
          const holder = standings?.find((row) => row.sponsor_code === sponsor.code);
          return (
            <div key={sponsor.code}>
              <label className="label" htmlFor={`sp-${sponsor.code}`}>
                {sponsor.name}
              </label>
              <select
                id={`sp-${sponsor.code}`}
                className="input"
                value={holder?.team_id ?? ""}
                disabled={busy}
                onChange={(event) =>
                  run(
                    () =>
                      api("/api/admin/sponsors/override", {
                        method: "POST",
                        master: true,
                        body: {
                          sponsor_code: sponsor.code,
                          team_id: event.target.value === "" ? null : Number(event.target.value),
                        },
                      }),
                    `${sponsor.name} reasignado.`,
                  )
                }
              >
                <option value="">Sin asignar</option>
                {overview.teams.map((team) => (
                  <option key={team.id} value={team.id}>
                    {team.name}
                  </option>
                ))}
              </select>
            </div>
          );
        })}
      </div>

      <div className="card space-y-3 border-blood-600/40">
        <h2 className="section-title text-blood-500">{"\u26A0"} Zona de peligro</h2>
        <p className="text-sm text-stone-400">
          Regenera los marcadores de todos los partidos a partir de los eventos registrados, recalcula
          la clasificacion y reasigna los patrocinadores desde cero.
        </p>
        <button
          type="button"
          className="btn-primary w-full bg-blood-700 hover:bg-blood-600"
          disabled={busy}
          onClick={() => setConfirmReset(true)}
        >
          Recalcular toda la liga
        </button>
      </div>

      <Sheet
        open={confirmReset}
        title="Confirmar recalculo"
        onClose={() => setConfirmReset(false)}
        footer={
          <>
            <button
              type="button"
              className="btn-secondary flex-1"
              onClick={() => setConfirmReset(false)}
            >
              Cancelar
            </button>
            <button
              type="button"
              className="btn-primary flex-1 bg-blood-700"
              disabled={busy}
              onClick={async () => {
                await run(
                  () => api("/api/admin/recalculate", { method: "POST", master: true }),
                  "Liga recalculada desde el historial de eventos.",
                );
                setConfirmReset(false);
              }}
            >
              Recalcular
            </button>
          </>
        }
      >
        <p className="text-sm text-stone-300">
          Los marcadores introducidos a mano que no coincidan con los eventos seran sobrescritos.
        </p>
      </Sheet>
    </div>
  );
}
