"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, gold, raceColor, signed, STATUS_LABEL } from "@/lib/api";
import type { Dashboard, Player } from "@/lib/types";
import { Banner, Shell } from "@/components/ui";

type Tab = "roster" | "table" | "round";

export default function DashboardPage() {
  const router = useRouter();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<Tab>("roster");
  const [openId, setOpenId] = useState<number | null>(null);

  function load() {
    api<Dashboard>("/api/dashboard")
      .then(setData)
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
  }, [router]);

  if (!data) {
    return (
      <Shell title="Tu equipo">
        {error ? <Banner>{error}</Banner> : <p className="text-muted">Cargando la liga…</p>}
      </Shell>
    );
  }

  const team = data.team;
  return (
    <Shell
      title={team.name}
      eyebrow={`Jornada ${data.current_round}`}
      action={
        <button
          className="rounded-full border border-line px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted"
          onClick={() => {
            window.localStorage.removeItem("bb_token");
            router.replace("/");
          }}
        >
          Salir
        </button>
      }
    >
      {error && <Banner>{error}</Banner>}
      <p className="mb-3 text-sm text-muted">
        {team.race} · {team.coach_name}
      </p>
      <div className="mb-4 grid grid-cols-2 gap-2">
        <Stat label="Tesorería" value={gold(team.treasury)} />
        <Stat label="VAE" value={gold(data.ctv.total)} />
        <Stat label="Hinchas" value={`${team.effective_fans}`} />
        <Stat label="Segundas" value={`${team.rerolls}`} />
      </div>
      {team.sponsor && (
        <article className="mb-4 rounded-3xl border border-gold/50 bg-gold/10 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gold">Patrocinador</p>
          <h2 className="font-display text-2xl uppercase leading-none">{team.sponsor.name}</h2>
          <p className="mt-2 text-sm leading-snug text-muted">{team.sponsor.benefit}</p>
        </article>
      )}
      {data.next_match && (
        <Link
          href={`/match/${data.next_match.id}`}
          className="mb-4 block rounded-3xl border border-line bg-card p-4 shadow-card"
        >
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gold">Próximo partido</p>
          <div className="mt-2 flex items-center justify-between gap-3">
            <div>
              <p className="font-display text-xl uppercase leading-tight">
                {data.next_match.home_name}
                <span className="mx-2 text-muted">vs</span>
                {data.next_match.away_name}
              </p>
              <p className="mt-1 text-sm text-muted">
                {STATUS_LABEL[data.next_match.status] || data.next_match.status}
                {data.next_match.status === "COMPLETED"
                  ? ` · ${data.next_match.home_td}-${data.next_match.away_td}`
                  : ""}
              </p>
            </div>
            <span className="font-display text-lg uppercase text-gold">Abrir</span>
          </div>
          {data.active_bounty && (
            <p className="mt-3 rounded-2xl bg-ink/40 px-3 py-2 text-sm leading-snug">
              <span className="font-semibold text-gold">{data.active_bounty.name}. </span>
              {data.active_bounty.summary} Premio {gold(data.active_bounty.reward)}.
            </p>
          )}
        </Link>
      )}
      <div className="mb-4 grid grid-cols-3 gap-2">
        {(
          [
            ["roster", "Plantilla"],
            ["table", "Liga"],
            ["round", "Jornada"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            className={`min-h-12 rounded-2xl font-display text-sm uppercase tracking-wide ${
              tab === key ? "bg-gold text-ink" : "bg-card text-bone"
            }`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "roster" && (
        <div className="space-y-2">
          {data.roster.map((player) => (
            <PlayerCard
              key={player.id}
              player={player}
              open={openId === player.id}
              onToggle={() => setOpenId(openId === player.id ? null : player.id)}
              onSaved={load}
              onError={setError}
            />
          ))}
          <p className="px-1 pt-2 text-xs leading-relaxed text-muted">
            Fuera de la VAE: {data.ctv.excluded_players.length ? data.ctv.excluded_players.map((p) => p.name).join(", ") : "nadie"}.
            Tesorería e hinchas no suman.
          </p>
        </div>
      )}
      {tab === "table" && (
        <div className="space-y-2">
          {data.standings.map((row) => (
            <article
              key={row.team_id}
              className={`rounded-3xl border p-4 ${row.team_id === team.id ? "border-gold bg-card2" : "border-line bg-card"}`}
            >
              <div className="flex items-start gap-3">
                <span className="font-display text-3xl leading-none text-gold">{row.rank}</span>
                <div className="min-w-0 flex-1">
                  <h3 className="truncate font-display text-xl uppercase leading-none">{row.name}</h3>
                  <p className="mt-1 text-sm text-muted">
                    {row.race} · {row.coach_name}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-display text-3xl leading-none">{row.points}</p>
                  <p className="text-[11px] uppercase tracking-wide text-muted">pts</p>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
                <Mini label="PJ" value={`${row.wins}-${row.draws}-${row.losses}`} />
                <Mini label="TD" value={signed(row.td_diff)} />
                <Mini label="Bajas" value={signed(row.cas_diff)} />
              </div>
            </article>
          ))}
          <p className="px-1 pt-1 text-xs leading-relaxed text-muted">{data.scoring_summary}</p>
        </div>
      )}
      {tab === "round" && (
        <div className="space-y-2">
          {data.round_matches.map((match) => (
            <article key={match.id} className="rounded-3xl border border-line bg-card p-4">
              <div className="flex items-center gap-2">
                <span className="h-8 w-1.5 rounded-full" style={{ background: raceColor(match.home_race_key) }} />
                <p className="min-w-0 flex-1 truncate font-display text-lg uppercase">{match.home_name}</p>
                <span className="font-display text-xl">{match.status === "COMPLETED" ? match.home_td : ""}</span>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span className="h-8 w-1.5 rounded-full" style={{ background: raceColor(match.away_race_key) }} />
                <p className="min-w-0 flex-1 truncate font-display text-lg uppercase">{match.away_name}</p>
                <span className="font-display text-xl">{match.status === "COMPLETED" ? match.away_td : ""}</span>
              </div>
              <p className="mt-2 text-sm text-muted">{STATUS_LABEL[match.status] || match.status}</p>
            </article>
          ))}
          {data.sponsor_log.length > 0 && (
            <article className="rounded-3xl border border-line bg-card p-4 text-sm leading-relaxed text-muted">
              {data.sponsor_log.map((line) => (
                <p key={line} className="mb-2 last:mb-0">
                  {line}
                </p>
              ))}
            </article>
          )}
        </div>
      )}
    </Shell>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-line bg-card px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.14em] text-muted">{label}</p>
      <p className="font-display text-xl leading-tight">{value}</p>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-ink/30 px-2 py-2">
      <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
      <p className="font-semibold">{value}</p>
    </div>
  );
}

function PlayerCard({
  player,
  open,
  onToggle,
  onSaved,
  onError,
}: {
  player: Player;
  open: boolean;
  onToggle: () => void;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [skills, setSkills] = useState(player.skills);
  const [value, setValue] = useState(String(player.current_value));
  const [busy, setBusy] = useState(false);
  const dead = player.status === "DEAD";
  const mng = player.status === "MNG";
  return (
    <article className={`rounded-3xl border border-line bg-card p-4 ${dead ? "opacity-60" : ""}`}>
      <button type="button" className="flex w-full items-center gap-3 text-left" onClick={onToggle}>
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-card2 font-display text-lg">
          {player.number}
        </span>
        <span className="min-w-0 flex-1">
          <span className={`block truncate font-display text-lg uppercase leading-tight ${dead ? "line-through" : ""}`}>
            {player.name}
          </span>
          <span className="block truncate text-sm text-muted">{player.position}</span>
        </span>
        <span
          className={`rounded-full px-2 py-1 text-[11px] font-semibold uppercase ${
            dead ? "bg-blood/20 text-blood" : mng ? "bg-gold/15 text-gold" : "bg-pitch/20 text-[#8ddeaf]"
          }`}
        >
          {mng ? "MNG" : dead ? "Muerto" : `${player.spp} PEP`}
        </span>
      </button>
      {open && (
        <div className="mt-4">
          <div className="grid grid-cols-5 gap-1 text-center">
            <StatMini label="MA" value={`${player.ma}`} />
            <StatMini label="ST" value={`${player.st}`} />
            <StatMini label="AG" value={`${player.ag}+`} />
            <StatMini label="PA" value={player.pa ? `${player.pa}+` : "—"} />
            <StatMini label="AV" value={`${player.av}+`} />
          </div>
          <p className="mt-3 text-sm leading-relaxed text-muted">{player.skills || "Sin habilidades."}</p>
          {player.injuries && <p className="mt-2 text-sm text-gold">Lesiones: {player.injuries}</p>}
          <p className="mt-2 text-sm">
            Valor {gold(player.current_value)} · coste {gold(player.cost)} · {player.spp} PEP
          </p>
          <label className="mt-4 block text-xs uppercase tracking-wide text-muted">
            Habilidades
            <textarea
              className="mt-1 min-h-20 w-full rounded-2xl border border-line bg-ink/40 p-3 text-base text-bone"
              value={skills}
              onChange={(event) => setSkills(event.target.value)}
            />
          </label>
          <label className="mt-3 block text-xs uppercase tracking-wide text-muted">
            Valor actual
            <input
              inputMode="numeric"
              className="mt-1 min-h-12 w-full rounded-2xl border border-line bg-ink/40 px-3 text-bone"
              value={value}
              onChange={(event) => setValue(event.target.value.replace(/[^\d]/g, ""))}
            />
          </label>
          <button
            className="mt-3 min-h-12 w-full rounded-2xl bg-gold font-display uppercase tracking-wide text-ink disabled:opacity-40"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              api(`/api/players/${player.id}`, {
                method: "PATCH",
                body: { skills, current_value: Number(value || 0) },
              })
                .then(() => onSaved())
                .catch((err: Error) => onError(err.message))
                .finally(() => setBusy(false));
            }}
          >
            {busy ? "Guardando…" : "Guardar ficha"}
          </button>
        </div>
      )}
    </article>
  );
}

function StatMini({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-ink/40 py-2">
      <p className="text-[10px] uppercase text-muted">{label}</p>
      <p className="font-display text-lg leading-none">{value}</p>
    </div>
  );
}
