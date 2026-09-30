import type { CasualtyResult, EventType, MatchStatus, PlayerStatus } from "./types";

export const MATCH_STATUS_LABEL: Record<MatchStatus, string> = {
  SCHEDULED: "Programado",
  READY_CHECK: "Ready check",
  PRE_MATCH: "Prepartido",
  IN_PROGRESS: "En juego",
  COMPLETED: "Finalizado",
};

export const MATCH_STATUS_STYLE: Record<MatchStatus, string> = {
  SCHEDULED: "bg-white/10 text-stone-300",
  READY_CHECK: "bg-sky-500/20 text-sky-300",
  PRE_MATCH: "bg-gold-500/20 text-gold-400",
  IN_PROGRESS: "bg-blood-600/25 text-blood-500 animate-pulse",
  COMPLETED: "bg-emerald-500/20 text-emerald-300",
};

export const PLAYER_STATUS_LABEL: Record<PlayerStatus, string> = {
  ACTIVE: "Disponible",
  MNG: "Se pierde el proximo",
  DEAD: "Muerto",
  RETIRED: "Retirado",
};

export const PLAYER_STATUS_STYLE: Record<PlayerStatus, string> = {
  ACTIVE: "bg-emerald-500/15 text-emerald-300",
  MNG: "bg-amber-500/20 text-amber-300",
  DEAD: "bg-blood-700/30 text-blood-500",
  RETIRED: "bg-white/10 text-stone-400",
};

export const EVENT_LABEL: Record<EventType, string> = {
  TD: "Touchdown",
  CAS: "Baja",
  FOUL: "Falta",
  PASS: "Pase",
  INT: "Intercepcion",
  DEFLECTION: "Desvio",
  MVP: "MVP",
};

export const EVENT_ICON: Record<EventType, string> = {
  TD: "\u{1F3C8}",
  CAS: "\u{1F915}",
  FOUL: "\u{1F45F}",
  PASS: "\u{1F3AF}",
  INT: "\u{1F9E4}",
  DEFLECTION: "\u{1F590}",
  MVP: "\u{2B50}",
};

export const CASUALTY_LABEL: Record<CasualtyResult, string> = {
  BADLY_HURT: "Magullado (sin secuelas)",
  SERIOUSLY_HURT: "Herido de gravedad (MNG)",
  SERIOUS_INJURY: "Lesion grave (MNG + persistente)",
  LASTING_INJURY_MA: "Pierna rota (-1 MA)",
  LASTING_INJURY_ST: "Musculo destrozado (-1 ST)",
  LASTING_INJURY_AG: "Nervio pinzado (-1 AG)",
  LASTING_INJURY_PA: "Mano machacada (-1 PA)",
  LASTING_INJURY_AV: "Cabeza abollada (-1 AV)",
  DEAD: "MUERTO",
};

export const SPONSOR_ICON: Record<string, string> = {
  PRENSA_AMARILLA: "\u{1F4F0}",
  RINCON_TABERNERO: "\u{1F37A}",
  CARNICERIA_DA_BOYZ: "\u{1FA93}",
  SINDICATO_MALHECHORES: "\u{1F573}",
};

export const formatStat = (value: number | null, kind: "plain" | "target") =>
  value === null ? "-" : kind === "target" ? `${value}+` : String(value);
