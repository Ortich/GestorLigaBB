"use client";

import { useState } from "react";

import { Sheet, StatBlock } from "@/components/ui";
import { formatGold } from "@/lib/api";
import { PLAYER_STATUS_LABEL, PLAYER_STATUS_STYLE } from "@/lib/labels";
import type { Player } from "@/lib/types";

export function PlayerRow({ player, onOpen }: { player: Player; onOpen: (player: Player) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpen(player)}
      className="card-tight flex w-full items-center gap-3 text-left active:scale-[0.99]"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-pitch-800 text-base font-bold text-gold-400">
        {player.number}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="truncate font-semibold text-stone-100">{player.name}</span>
          {player.status !== "ACTIVE" && (
            <span className={`chip ${PLAYER_STATUS_STYLE[player.status]}`}>
              {PLAYER_STATUS_LABEL[player.status]}
            </span>
          )}
        </span>
        <span className="block truncate text-xs text-stone-400">{player.position}</span>
      </span>
      <span className="shrink-0 text-right">
        <span className="block text-sm font-semibold text-stone-200">{player.spp} SPP</span>
        <span className="block text-[11px] text-stone-500">{formatGold(player.current_value)}</span>
      </span>
    </button>
  );
}

export function PlayerSheet({ player, onClose }: { player: Player | null; onClose: () => void }) {
  return (
    <Sheet open={player !== null} title={player ? `#${player.number} ${player.name}` : ""} onClose={onClose}>
      {player && (
        <>
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-semibold text-stone-100">{player.position}</p>
              <p className="text-xs text-stone-400">
                {player.level} &middot; {player.spp} SPP
              </p>
            </div>
            <span className={`chip ${PLAYER_STATUS_STYLE[player.status]}`}>
              {PLAYER_STATUS_LABEL[player.status]}
            </span>
          </div>

          <StatBlock ma={player.ma} st={player.st} ag={player.ag} pa={player.pa} av={player.av} />

          <div>
            <p className="label">Habilidades</p>
            {player.skills.length ? (
              <div className="flex flex-wrap gap-1.5">
                {player.skills.map((skill) => (
                  <span key={skill} className="chip">
                    {skill}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-stone-500">Sin habilidades todavia.</p>
            )}
          </div>

          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div className="card-tight">
              <dt className="text-xs text-stone-500">Coste de contratacion</dt>
              <dd className="font-semibold">{formatGold(player.cost)}</dd>
            </div>
            <div className="card-tight">
              <dt className="text-xs text-stone-500">Valor actual</dt>
              <dd className="font-semibold">{formatGold(player.current_value)}</dd>
            </div>
            <div className="card-tight col-span-2">
              <dt className="text-xs text-stone-500">Cuenta para la VAE</dt>
              <dd className="font-semibold">
                {player.counts_towards_ctv ? "Si" : "No (lesionado o muerto)"}
              </dd>
            </div>
          </dl>
        </>
      )}
    </Sheet>
  );
}

export function PlayerListCard({ players }: { players: Player[] }) {
  const [selected, setSelected] = useState<Player | null>(null);
  return (
    <>
      <div className="space-y-2">
        {players.map((player) => (
          <PlayerRow key={player.id} player={player} onOpen={setSelected} />
        ))}
      </div>
      <PlayerSheet player={selected} onClose={() => setSelected(null)} />
    </>
  );
}
