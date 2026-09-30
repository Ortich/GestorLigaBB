"use client";

import { useState } from "react";

import { PinPad } from "@/components/PinPad";
import { Alert, Sheet } from "@/components/ui";
import { api } from "@/lib/api";
import type { MatchDetail, TeamSummary } from "@/lib/types";

/**
 * Paso 1: los dos entrenadores confirman su presencia con el PIN en el mismo
 * movil. Al confirmar el segundo, el backend pasa el partido a PRE_MATCH.
 */
export function ReadyCheckStep({
  match,
  onUpdated,
}: {
  match: MatchDetail;
  onUpdated: (next: MatchDetail) => void;
}) {
  const [target, setTarget] = useState<TeamSummary | null>(null);
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const confirm = async (candidate: string) => {
    if (!target || candidate.length !== 4 || busy) return;
    setBusy(true);
    setError(null);
    try {
      const next = await api<MatchDetail>(`/api/matches/${match.id}/confirm`, {
        method: "POST",
        auth: true,
        body: { team_id: target.id, pin: candidate },
      });
      onUpdated(next);
      setTarget(null);
      setPin("");
    } catch (err) {
      setError((err as Error).message);
      setPin("");
    } finally {
      setBusy(false);
    }
  };

  const rows: { team: TeamSummary; ready: boolean }[] = [
    { team: match.home_team, ready: match.home_ready },
    { team: match.away_team, ready: match.away_ready },
  ];

  return (
    <>
      <div className="card">
        <h2 className="section-title">{"\u{1F91D}"} Ready check</h2>
        <p className="text-sm text-stone-400">
          Pasad el movil: cada entrenador introduce su PIN para confirmar que esta en la mesa. Cuando
          los dos confirmen se abrira el prepartido.
        </p>
      </div>

      <div className="space-y-3">
        {rows.map(({ team, ready }) => (
          <div key={team.id} className="card flex items-center gap-3">
            <span className="text-3xl">{team.logo}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-bold text-stone-100">{team.name}</p>
              <p className="truncate text-xs text-stone-400">{team.coach_name}</p>
            </div>
            {ready ? (
              <span className="chip bg-emerald-500/15 text-emerald-300">Confirmado</span>
            ) : (
              <button
                type="button"
                className="btn-primary btn-sm shrink-0"
                onClick={() => {
                  setTarget(team);
                  setPin("");
                  setError(null);
                }}
              >
                Introducir PIN
              </button>
            )}
          </div>
        ))}
      </div>

      <Sheet
        open={target !== null}
        title={target ? `PIN de ${target.name}` : ""}
        onClose={() => setTarget(null)}
      >
        <PinPad value={pin} onChange={setPin} onComplete={confirm} disabled={busy} />
        {error && <Alert onDismiss={() => setError(null)}>{error}</Alert>}
      </Sheet>
    </>
  );
}
