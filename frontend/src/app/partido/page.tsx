"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ClosingSheet, CompletedView } from "@/components/match/Closing";
import { LiveTracker } from "@/components/match/LiveTracker";
import { PreMatchStep } from "@/components/match/PreMatch";
import { ReadyCheckStep } from "@/components/match/ReadyCheck";
import { Alert, EmptyState, Spinner } from "@/components/ui";
import { api, session } from "@/lib/api";
import { useApi, usePoll } from "@/lib/hooks";
import { MATCH_STATUS_LABEL, MATCH_STATUS_STYLE } from "@/lib/labels";
import type { CompletionReport, MatchDetail, MatchSummary, Rules } from "@/lib/types";

export default function MatchPage() {
  const [matchId, setMatchId] = useState<number | null>(null);
  const [resolving, setResolving] = useState(true);
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [report, setReport] = useState<CompletionReport | null>(null);
  const [closing, setClosing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const rules = useApi<Rules>("/api/rules");

  // Sin `id` en la URL se abre el proximo partido del equipo con la sesion activa.
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("id");
    if (requested) {
      setMatchId(Number(requested));
      setResolving(false);
      return;
    }
    const teamId = session.teamId;
    if (!teamId) {
      setResolving(false);
      return;
    }
    api<MatchSummary | null>(`/api/matches/next?team_id=${teamId}`)
      .then((next) => setMatchId(next?.id ?? null))
      .catch((err: Error) => setError(err.message))
      .finally(() => setResolving(false));
  }, []);

  const refresh = useCallback(async () => {
    if (matchId === null) return;
    try {
      setMatch(await api<MatchDetail>(`/api/matches/${matchId}`));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [matchId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // El rival puede estar apuntando eventos desde su propio movil.
  usePoll(refresh, 10000, match?.status === "IN_PROGRESS" || match?.status === "READY_CHECK");

  const myTeamId = typeof window === "undefined" ? null : session.teamId;
  const isParticipant =
    match !== null && (myTeamId === match.home_team.id || myTeamId === match.away_team.id);

  const openReadyCheck = async () => {
    if (!match) return;
    setBusy(true);
    try {
      setMatch(
        await api<MatchDetail>(`/api/matches/${match.id}/ready-check`, {
          method: "POST",
          auth: true,
        }),
      );
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (resolving) {
    return (
      <AppShell title="Partido">
        <Spinner />
      </AppShell>
    );
  }

  if (matchId === null) {
    return (
      <AppShell title="Partido">
        <EmptyState
          icon={"\u{1F3C8}"}
          title="No tienes ningun partido pendiente"
          hint="Consulta el calendario de la liga para abrir otro encuentro."
        />
        <Link href="/liga?tab=calendario" className="btn-secondary w-full">
          Ver calendario
        </Link>
      </AppShell>
    );
  }

  return (
    <AppShell
      title={
        match ? `${match.home_team.logo} ${match.home_team.name} vs ${match.away_team.name} ${match.away_team.logo}` : "Partido"
      }
      subtitle={match ? `Jornada ${match.round_number}` : undefined}
      action={
        match && (
          <span className={`chip shrink-0 ${MATCH_STATUS_STYLE[match.status]}`}>
            {MATCH_STATUS_LABEL[match.status]}
          </span>
        )
      }
    >
      {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
      {!match && <Spinner />}

      {match && !isParticipant && match.status !== "COMPLETED" && (
        <Alert kind="info">
          Estas viendo un partido de otros entrenadores. Solo los dos equipos implicados pueden
          registrar eventos.
        </Alert>
      )}

      {match?.status === "SCHEDULED" && (
        <>
          <div className="card">
            <h2 className="section-title">{"\u{1F5D3}"} Partido programado</h2>
            <p className="text-sm text-stone-400">
              Cuando esteis los dos en la mesa, abrid el ready check para confirmar presencia con los
              PIN y calcular la VAE de cada equipo.
            </p>
          </div>
          <button
            type="button"
            className="btn-primary w-full"
            disabled={busy || !isParticipant}
            onClick={openReadyCheck}
          >
            Abrir ready check
          </button>
        </>
      )}

      {match?.status === "READY_CHECK" && <ReadyCheckStep match={match} onUpdated={setMatch} />}

      {match?.status === "PRE_MATCH" && (
        <PreMatchStep match={match} rules={rules.data} onUpdated={setMatch} />
      )}

      {match?.status === "IN_PROGRESS" && (
        <>
          <LiveTracker match={match} onUpdated={setMatch} onFinish={() => setClosing(true)} />
          <ClosingSheet
            match={match}
            open={closing}
            onClose={() => setClosing(false)}
            onCompleted={(result) => {
              setReport(result);
              setClosing(false);
              void refresh();
            }}
          />
        </>
      )}

      {match?.status === "COMPLETED" && <CompletedView match={match} report={report} />}
    </AppShell>
  );
}
