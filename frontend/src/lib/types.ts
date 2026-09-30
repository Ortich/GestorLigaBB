export type PlayerStatus = "ACTIVE" | "MNG" | "DEAD" | "RETIRED";

export type MatchStatus =
  | "SCHEDULED"
  | "READY_CHECK"
  | "PRE_MATCH"
  | "IN_PROGRESS"
  | "COMPLETED";

export type EventType = "TD" | "CAS" | "FOUL" | "PASS" | "INT" | "DEFLECTION" | "MVP";

export type CasualtyResult =
  | "BADLY_HURT"
  | "SERIOUSLY_HURT"
  | "SERIOUS_INJURY"
  | "LASTING_INJURY_MA"
  | "LASTING_INJURY_ST"
  | "LASTING_INJURY_AG"
  | "LASTING_INJURY_PA"
  | "LASTING_INJURY_AV"
  | "DEAD";

export interface LoginOption {
  id: number;
  name: string;
  coach_name: string;
  race: string;
  logo: string;
}

export interface Player {
  id: number;
  team_id: number;
  number: number;
  name: string;
  position: string;
  ma: number;
  st: number;
  ag: number;
  pa: number | null;
  av: number;
  skills: string[];
  cost: number;
  current_value: number;
  spp: number;
  status: PlayerStatus;
  level: string;
  niggling_injuries: number;
  counts_towards_ctv: boolean;
}

export interface Sponsor {
  id: number;
  code: string;
  name: string;
  metric: string;
  description: string;
  benefit: string;
}

export interface CtvBreakdown {
  team_id: number;
  players: number;
  rerolls: number;
  assistant_coaches: number;
  cheerleaders: number;
  apothecary: number;
  total: number;
  excluded_players: number;
}

export interface TeamSummary {
  id: number;
  name: string;
  coach_name: string;
  race: string;
  logo: string;
  treasury: number;
  ctv: number;
  current_sponsor_id: number | null;
  current_sponsor: Sponsor | null;
}

export interface TeamDetail {
  id: number;
  name: string;
  coach_name: string;
  race: string;
  logo: string;
  treasury: number;
  rerolls: number;
  reroll_cost: number;
  assistant_coaches: number;
  cheerleaders: number;
  apothecary: boolean;
  fans: number;
  sponsor_preference: string[];
  rookie_safety_claims: number;
  current_sponsor: Sponsor | null;
  ctv: CtvBreakdown;
  players: Player[];
}

export interface StandingRow {
  position: number;
  team_id: number;
  team_name: string;
  logo: string;
  race: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  points: number;
  td_for: number;
  td_against: number;
  td_diff: number;
  cas_for: number;
  cas_against: number;
  cas_diff: number;
  fouls: number;
  passes: number;
  ctv: number;
  sponsor_code: string | null;
  sponsor_name: string | null;
}

export interface Bounty {
  id: number;
  code: string;
  name: string;
  description: string;
  reward_gold: number;
}

export interface LeagueState {
  name: string;
  current_round: number;
  total_rounds: number;
  active_bounty: Bounty | null;
  rookie_safety_last_round: number;
  sponsors_first_round: number;
}

export interface MatchSummary {
  id: number;
  round_number: number;
  status: MatchStatus;
  home_team_id: number;
  away_team_id: number;
  home_team_name: string;
  away_team_name: string;
  home_logo: string;
  away_logo: string;
  home_td: number;
  away_td: number;
}

export interface MatchEvent {
  id: number;
  match_id: number;
  team_id: number;
  team_name: string;
  player_id: number | null;
  player_name: string | null;
  event_type: EventType;
  turn: number | null;
  spp_awarded: number;
  victim_player_id: number | null;
  victim_player_name: string | null;
  casualty_result: CasualtyResult | null;
  note: string;
  created_at: string;
}

export interface Inducement {
  id: number;
  match_id: number;
  team_id: number;
  code: string;
  name: string;
  quantity: number;
  unit_cost: number;
  total_cost: number;
}

export interface RuleEntry {
  roll: string;
  min?: number;
  max?: number;
  name: string;
  text: string;
}

export interface MatchDetail {
  id: number;
  round_number: number;
  status: MatchStatus;
  home_team: TeamSummary;
  away_team: TeamSummary;
  home_td: number;
  away_td: number;
  home_ctv: number | null;
  away_ctv: number | null;
  petty_cash_amount: number;
  petty_cash_team_id: number | null;
  petty_cash_spent: number;
  petty_cash_remaining: number;
  home_ready: boolean;
  away_ready: boolean;
  weather_roll: number | null;
  weather: RuleEntry | null;
  prayer_roll: number | null;
  prayer: RuleEntry | null;
  prayer_team_id: number | null;
  kick_off_roll: number | null;
  kick_off: RuleEntry | null;
  bounty: Bounty | null;
  bounty_winner_team_id: number | null;
  home_winnings: number;
  away_winnings: number;
  home_winnings_roll: number | null;
  away_winnings_roll: number | null;
  home_mvp_player_id: number | null;
  away_mvp_player_id: number | null;
  inducements: Inducement[];
  events: MatchEvent[];
  home_players: Player[];
  away_players: Player[];
  scoreboard: Record<string, Record<string, number>>;
}

export interface CompletionReport {
  match_id: number;
  home_winnings: number;
  away_winnings: number;
  injuries: { player_name: string; team_id: number; result: string; effect: string }[];
  rookie_safety_payouts: {
    team_name: string;
    player_name: string;
    percentage: number;
    gold: number;
  }[];
  bounty_payout: { team_name: string; bounty: string; gold: number } | null;
  recovered_players: { player_name: string; team_id: number }[];
  sponsors: SponsorAssignment[];
}

export interface SponsorAssignment {
  sponsor_code: string;
  sponsor_name: string;
  team_id: number | null;
  team_name: string | null;
  metric: string;
  metric_value: number | null;
  reason: string;
}

export interface InducementCatalogItem {
  code: string;
  name: string;
  cost: number;
  max: number;
  icon: string;
  text: string;
}

export interface Rules {
  edition: string;
  weather: { title: string; dice: string; entries: RuleEntry[] };
  kick_off: { title: string; dice: string; entries: RuleEntry[] };
  prayers_to_nuffle: { title: string; dice: string; entries: RuleEntry[] };
  casualty_table: { title: string; dice: string; entries: (RuleEntry & { code: string })[] };
  inducements: { title: string; note: string; catalog: InducementCatalogItem[] };
  scoring: { text: string; tiebreakers: string[] };
  spp: Record<string, number | string>;
  levels: { name: string; min: number; max: number }[];
  advancements: { code: string; name: string; spp: number; value: number }[];
  ctv: { text: string };
  rookie_safety: { title: string; text: string; last_round: number; tiers: number[] };
  post_match: { text: string };
  sponsors: {
    code: string;
    name: string;
    metric: string;
    description: string;
    benefit: string;
  }[];
  sponsor_rules: { first_round: number; text: string };
  bounties: { code: string; name: string; description: string; reward_gold: number }[];
}

export interface RosterPosition {
  code: string;
  name: string;
  max: number;
  ma: number;
  st: number;
  ag: number;
  pa: number | null;
  av: number;
  cost: number;
  skills: string[];
  used: number;
  remaining: number;
}

export interface RosterOptions {
  race: string;
  reroll_cost: number;
  positions: RosterPosition[];
  roster_size: number;
}
