"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { PlayerListCard } from "@/components/PlayerList";
import { Alert, Sheet, Spinner } from "@/components/ui";
import { api, formatGold, session } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { MATCH_STATUS_LABEL, MATCH_STATUS_STYLE, SPONSOR_ICON } from "@/lib/labels";
import type { LeagueState, MatchSummary, TeamDetail } from "@/lib/types";

export default function TeamDashboardPage() {
  const router = useRouter();
  const [teamId, setTeamId] = useState<number | null>(null);
  const [showStaff, setShowStaff] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setTeamId(session.teamId), []);

  const team = useApi<TeamDetail>("/api/auth/me", { auth: true });
  const league = useApi<LeagueState>("/api/league/state");
  const next = useApi<MatchSummary | null>(teamId ? `/api/matches/next?team_id=${teamId}` : null);

  const logout = () => {
    session.clear();
    router.replace("/");
  };

  const detail = team.data;

  return (
    <AppShell
      title={detail ? `${detail.logo} ${detail.name}` : "Mi equipo"}
      subtitle={detail ? `${detail.race} \u00b7 Entrenador: ${detail.coach_name}` : undefined}
      action={
        <button type="button" onClick={logout} className="btn btn-ghost btn-sm">
          Salir
        </button>
      }
    >
      {team.error && <Alert>{team.error}</Alert>}
      {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
      {team.loading && !detail && <Spinner />}

      {detail && (
        <>
          <section className="grid grid-cols-2 gap-3">
            <div className="card">
              <p className="text-xs uppercase tracking-wider text-stone-500">VAE / CTV</p>
              <p className="text-2xl font-black text-gold-400">{formatGold(detail.ctv.total)}</p>
              <p className="mt-1 text-[11px] text-stone-500">
                {detail.ctv.excluded_players > 0
                  ? `${detail.ctv.excluded_players} jugador(es) excluidos`
                  : "Plantilla al completo"}
              </p>
            </div>
            <div className="card">
              <p className="text-xs uppercase tracking-wider text-stone-500">Tesoreria</p>
              <p className="text-2xl font-black text-stone-100">{formatGold(detail.treasury)}</p>
              <p className="mt-1 text-[11px] text-stone-500">No suma a la VAE</p>
            </div>
          </section>

          <section className="card">
            <h2 className="section-title">{"\u{1F5D3}"} Proximo partido</h2>
            {next.loading && <p className="text-sm text-stone-400">Buscando...</p>}
            {!next.loading && !next.data && (
              <p className="text-sm text-stone-400">No tienes partidos pendientes.</p>
            )}
            {next.data && (
              <Link href={`/partido?id=${next.data.id}`} className="block">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs text-stone-500">Jornada {next.data.round_number}</p>
                    <p className="truncate font-bold text-stone-100">
                      {next.data.home_logo} {next.data.home_team_name}
                      <span className="mx-2 text-stone-500">vs</span>
                      {next.data.away_logo} {next.data.away_team_name}
                    </p>
                  </div>
                  <span className={`chip ${MATCH_STATUS_STYLE[next.data.status]}`}>
                    {MATCH_STATUS_LABEL[next.data.status]}
                  </span>
                </div>
                <span className="btn-primary mt-3 w-full">Abrir asistente de partido</span>
              </Link>
            )}
            {league.data?.active_bounty && (
              <div className="mt-3 rounded-xl border border-gold-500/30 bg-gold-500/10 p-3">
                <p className="text-xs font-bold uppercase tracking-wider text-gold-400">
                  {"\u{1F3AF}"} Bounty de la jornada {league.data.current_round}
                </p>
                <p className="mt-1 text-sm font-semibold text-stone-100">
                  {league.data.active_bounty.name}
                </p>
                <p className="text-xs text-stone-300">{league.data.active_bounty.description}</p>
              </div>
            )}
          </section>

          <section className="card">
            <h2 className="section-title">{"\u{1F4BC}"} Patrocinador</h2>
            {detail.current_sponsor ? (
              <div>
                <p className="text-lg font-bold text-stone-100">
                  {SPONSOR_ICON[detail.current_sponsor.code] ?? "\u{1F3F7}"}{" "}
                  {detail.current_sponsor.name}
                </p>
                <p className="mt-1 text-sm text-stone-300">{detail.current_sponsor.benefit}</p>
              </div>
            ) : (
              <p className="text-sm text-stone-400">
                Sin patrocinador. Se reparten al final de cada jornada desde la Jornada{" "}
                {league.data?.sponsors_first_round ?? 3}.
              </p>
            )}
            <Link href="/liga?tab=sponsors" className="btn btn-secondary btn-sm mt-3 w-full">
              Ver reparto y preferencias
            </Link>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="section-title mb-0">{"\u{1F465}"} Plantilla ({detail.players.length})</h2>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowStaff(true)}
              >
                Cuerpo tecnico
              </button>
            </div>
            <PlayerListCard players={detail.players} />
          </section>
        </>
      )}

      {detail && (
        <StaffSheet
          open={showStaff}
          team={detail}
          onClose={() => setShowStaff(false)}
          onError={setError}
          onChanged={() => {
            void team.reload();
          }}
        />
      )}
    </AppShell>
  );
}

function StaffSheet({
  open,
  team,
  onClose,
  onChanged,
  onError,
}: {
  open: boolean;
  team: TeamDetail;
  onClose: () => void;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  const buy = async (item: string, quantity: number) => {
    setBusy(true);
    try {
      await api(`/api/teams/${team.id}/staff`, {
        method: "POST",
        auth: true,
        body: { item, quantity },
      });
      onChanged();
    } catch (err) {
      onError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const rows: { item: string; label: string; value: string; cost: number }[] = [
    {
      item: "REROLL",
      label: "Segundas Oportunidades",
      value: String(team.rerolls),
      cost: team.reroll_cost * 2,
    },
    {
      item: "ASSISTANT_COACH",
      label: "Ayudantes de entrenador",
      value: String(team.assistant_coaches),
      cost: 10000,
    },
    { item: "CHEERLEADER", label: "Animadoras", value: String(team.cheerleaders), cost: 10000 },
    { item: "FAN", label: "Hinchas dedicados", value: String(team.fans), cost: 10000 },
    {
      item: "APOTHECARY",
      label: "Apotecario",
      value: team.apothecary ? "Si" : "No",
      cost: 50000,
    },
  ];

  return (
    <Sheet open={open} title="Cuerpo tecnico e instalaciones" onClose={onClose}>
      <p className="text-sm text-stone-400">
        Tesoreria disponible: <strong className="text-gold-400">{formatGold(team.treasury)}</strong>
      </p>
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.item} className="card-tight flex items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-stone-100">{row.label}</p>
              <p className="text-xs text-stone-500">{formatGold(row.cost)} cada uno</p>
            </div>
            <span className="w-8 text-center text-lg font-bold tabular-nums">{row.value}</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={busy || (row.item === "APOTHECARY" && team.apothecary)}
              onClick={() => buy(row.item, 1)}
            >
              Comprar
            </button>
          </div>
        ))}
      </div>
      <p className="text-xs text-stone-500">
        Las Segundas Oportunidades compradas despues de crear el equipo cuestan el doble.
      </p>
    </Sheet>
  );
}
