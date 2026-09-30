"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { Alert, Sheet, Spinner } from "@/components/ui";
import { api, formatShortGold, session } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { MATCH_STATUS_LABEL, MATCH_STATUS_STYLE, SPONSOR_ICON } from "@/lib/labels";
import type {
  LeagueState,
  MatchSummary,
  Sponsor,
  SponsorAssignment,
  StandingRow,
  TeamDetail,
} from "@/lib/types";

type Tab = "tabla" | "sponsors" | "calendario";

const TABS: { id: Tab; label: string }[] = [
  { id: "tabla", label: "Clasificacion" },
  { id: "sponsors", label: "Patrocinadores" },
  { id: "calendario", label: "Calendario" },
];

export default function LeaguePage() {
  const [tab, setTab] = useState<Tab>("tabla");

  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("tab");
    if (requested && TABS.some((t) => t.id === requested)) setTab(requested as Tab);
  }, []);

  const league = useApi<LeagueState>("/api/league/state");
  const standings = useApi<StandingRow[]>("/api/league/standings");

  return (
    <AppShell
      title={league.data?.name ?? "La liga"}
      subtitle={
        league.data
          ? `Jornada ${league.data.current_round} de ${league.data.total_rounds}`
          : undefined
      }
    >
      <div className="flex gap-2 overflow-x-auto pb-1">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setTab(item.id)}
            className={`btn btn-sm whitespace-nowrap ${
              tab === item.id ? "bg-gold-500 text-pitch-950" : "btn-secondary"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {tab === "tabla" && <StandingsTab standings={standings} />}
      {tab === "sponsors" && <SponsorsTab />}
      {tab === "calendario" && <CalendarTab currentRound={league.data?.current_round ?? 1} />}
    </AppShell>
  );
}

function StandingsTab({
  standings,
}: {
  standings: ReturnType<typeof useApi<StandingRow[]>>;
}) {
  const [open, setOpen] = useState<StandingRow | null>(null);
  const myTeam = typeof window === "undefined" ? null : session.teamId;

  if (standings.loading && !standings.data) return <Spinner />;
  if (standings.error) return <Alert>{standings.error}</Alert>;

  return (
    <>
      <p className="text-xs text-stone-500">
        Victoria 3 pts &middot; Empate 1 pt &middot; Derrota por 1 TD 1 pt. Desempates: diferencia de
        TD, diferencia de bajas y TD a favor.
      </p>

      <div className="space-y-2">
        {standings.data?.map((row) => (
          <button
            key={row.team_id}
            type="button"
            onClick={() => setOpen(row)}
            className={`card-tight flex w-full items-center gap-3 text-left active:scale-[0.99] ${
              row.team_id === myTeam ? "ring-1 ring-gold-500/60" : ""
            }`}
          >
            <span className="w-6 text-center text-lg font-black text-stone-500">{row.position}</span>
            <span className="text-xl">{row.logo}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-semibold text-stone-100">{row.team_name}</span>
              <span className="block text-[11px] text-stone-500">
                {row.played} PJ &middot; TD {row.td_for}:{row.td_against} &middot; Bajas {row.cas_for}
                {row.sponsor_code ? ` \u00b7 ${SPONSOR_ICON[row.sponsor_code] ?? ""}` : ""}
              </span>
            </span>
            <span className="shrink-0 text-right">
              <span className="block text-xl font-black text-gold-400">{row.points}</span>
              <span className="block text-[10px] uppercase text-stone-500">pts</span>
            </span>
          </button>
        ))}
      </div>

      <Sheet open={open !== null} title={open ? `${open.logo} ${open.team_name}` : ""} onClose={() => setOpen(null)}>
        {open && (
          <>
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                ["Puntos", open.points],
                ["Jugados", open.played],
                ["VAE", formatShortGold(open.ctv)],
                ["Victorias", open.wins],
                ["Empates", open.draws],
                ["Derrotas", open.losses],
                ["TD a favor", open.td_for],
                ["TD en contra", open.td_against],
                ["Dif. TD", open.td_diff],
                ["Bajas causadas", open.cas_for],
                ["Bajas sufridas", open.cas_against],
                ["Dif. bajas", open.cas_diff],
                ["Faltas", open.fouls],
                ["Pases", open.passes],
              ].map(([label, value]) => (
                <div key={String(label)} className="card-tight">
                  <p className="text-[10px] uppercase text-stone-500">{label}</p>
                  <p className="text-lg font-bold text-stone-100">{value}</p>
                </div>
              ))}
            </div>
            {open.sponsor_name && (
              <p className="rounded-xl border border-gold-500/30 bg-gold-500/10 p-3 text-sm">
                Patrocinado por <strong>{open.sponsor_name}</strong>
              </p>
            )}
          </>
        )}
      </Sheet>
    </>
  );
}

function SponsorsTab() {
  const sponsors = useApi<Sponsor[]>("/api/league/sponsors");
  const standings = useApi<StandingRow[]>("/api/league/standings");
  const preview = useApi<{
    evaluated_round: number;
    first_round: number;
    assignments: SponsorAssignment[];
  }>("/api/league/sponsors/preview");
  const me = useApi<TeamDetail>("/api/auth/me", { auth: true });

  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const holder = (code: string) =>
    standings.data?.find((row) => row.sponsor_code === code)?.team_name ?? null;

  const movePreference = async (code: string) => {
    if (!me.data) return;
    const current = me.data.sponsor_preference.filter((c) => c !== code);
    setSaving(true);
    try {
      await api(`/api/teams/${me.data.id}`, {
        method: "PATCH",
        auth: true,
        body: { sponsor_preference: [code, ...current] },
      });
      await me.reload();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (sponsors.loading && !sponsors.data) return <Spinner />;

  return (
    <>
      {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
      <p className="text-xs text-stone-500">
        Se evaluan al final de cada jornada desde la Jornada {preview.data?.first_round ?? 3}. Cada
        patrocinador va a un unico equipo; si un equipo lidera dos metricas elige uno y el otro pasa al
        siguiente. El peor clasificado elige primero.
      </p>

      <div className="space-y-3">
        {sponsors.data?.map((sponsor) => {
          const proposal = preview.data?.assignments.find((a) => a.sponsor_code === sponsor.code);
          const current = holder(sponsor.code);
          const preferred = me.data?.sponsor_preference[0] === sponsor.code;
          return (
            <div key={sponsor.code} className="card space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-base font-bold text-stone-100">
                    {SPONSOR_ICON[sponsor.code] ?? "\u{1F3F7}"} {sponsor.name}
                  </p>
                  <p className="text-xs text-stone-400">{sponsor.description}</p>
                </div>
                <span className="chip shrink-0">{current ?? "Libre"}</span>
              </div>
              <p className="rounded-lg bg-pitch-800/70 p-2.5 text-sm text-stone-200">
                {sponsor.benefit}
              </p>
              {proposal && (
                <p className="text-xs text-stone-500">
                  Simulacion con los datos de hoy: {proposal.team_name ?? "sin candidato"}
                  {proposal.metric_value !== null ? ` (${proposal.reason})` : ""}
                </p>
              )}
              <button
                type="button"
                disabled={saving || preferred}
                onClick={() => movePreference(sponsor.code)}
                className={`btn btn-sm w-full ${preferred ? "btn-gold" : "btn-secondary"}`}
              >
                {preferred ? "Es tu preferido en caso de empate" : "Marcar como preferido"}
              </button>
            </div>
          );
        })}
      </div>
    </>
  );
}

function CalendarTab({ currentRound }: { currentRound: number }) {
  const [round, setRound] = useState(currentRound);
  useEffect(() => setRound(currentRound), [currentRound]);

  const matches = useApi<MatchSummary[]>(`/api/matches?round=${round}`);
  const all = useApi<MatchSummary[]>("/api/matches");
  const rounds = Array.from(new Set((all.data ?? []).map((m) => m.round_number))).sort(
    (a, b) => a - b,
  );

  return (
    <>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {rounds.map((value) => (
          <button
            key={value}
            type="button"
            onClick={() => setRound(value)}
            className={`btn btn-sm min-w-[52px] ${
              value === round ? "bg-gold-500 text-pitch-950" : "btn-secondary"
            }`}
          >
            J{value}
          </button>
        ))}
      </div>

      {matches.loading && !matches.data && <Spinner />}
      <div className="space-y-2">
        {matches.data?.map((match) => (
          <Link key={match.id} href={`/partido?id=${match.id}`} className="card-tight flex items-center gap-3">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-stone-100">
                {match.home_logo} {match.home_team_name}
              </span>
              <span className="block truncate text-sm font-semibold text-stone-100">
                {match.away_logo} {match.away_team_name}
              </span>
            </span>
            <span className="shrink-0 text-center">
              <span className="block text-xl font-black tabular-nums text-gold-400">
                {match.home_td} - {match.away_td}
              </span>
              <span className={`chip mt-1 ${MATCH_STATUS_STYLE[match.status]}`}>
                {MATCH_STATUS_LABEL[match.status]}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </>
  );
}
