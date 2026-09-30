export type Sponsor = {
  id: string;
  name: string;
  assigns: string;
  benefit: string;
};

export type Benefits = {
  chooses_kick: boolean;
  fan_bonus: number;
  free_reroll: boolean;
  ko_recovery: boolean;
  cas_bonus: boolean;
  free_bribe: boolean;
};

export type TeamCard = {
  id: number;
  name: string;
  coach_name: string;
  race: string;
  race_key: string;
  treasury: number;
  rerolls: number;
  reroll_cost: number;
  assistant_coaches: number;
  cheerleaders: number;
  apothecary: boolean;
  fans: number;
  effective_fans: number;
  sponsor_id: string | null;
  sponsor: Sponsor | null;
  benefits: Benefits;
  pin?: string;
};

export type Player = {
  id: number;
  team_id: number;
  name: string;
  position: string;
  number: number;
  ma: number;
  st: number;
  ag: number;
  pa: number | null;
  av: number;
  skills: string;
  cost: number;
  current_value: number;
  spp: number;
  status: string;
  mng_until_round: number | null;
  injuries: string;
};

export type Ctv = {
  players: number;
  rerolls: number;
  reroll_count: number;
  reroll_cost: number;
  assistants: number;
  assistant_count: number;
  cheerleaders: number;
  cheerleader_count: number;
  apothecary: number;
  total: number;
  excluded_players: { id: number; name: string; status: string; value: number }[];
};

export type Standing = {
  rank: number;
  team_id: number;
  name: string;
  coach_name: string;
  race: string;
  race_key: string;
  played: number;
  points: number;
  wins: number;
  draws: number;
  losses: number;
  td_for: number;
  td_against: number;
  td_diff: number;
  cas_for: number;
  cas_against: number;
  cas_diff: number;
  fouls: number;
  sponsor_id: string | null;
};

export type ShortMatch = {
  id: number;
  round_number: number;
  status: string;
  home_team_id: number;
  away_team_id: number;
  home_name: string;
  away_name: string;
  home_coach: string;
  away_coach: string;
  home_race_key: string;
  away_race_key: string;
  home_td: number;
  away_td: number;
  home_ready: boolean;
  away_ready: boolean;
};

export type Bounty = {
  id: string;
  name: string;
  summary: string;
  reward: number;
  metric: string;
  min: number;
};

export type Side = TeamCard & {
  players: Player[];
  ctv_live: number;
  ctv: number;
  ctv_breakdown: Ctv;
};

export type RollCard = { roll: number; name: string; summary: string } | null;

export type Inducement = {
  id: string;
  name: string;
  cost: number;
  max: number;
  summary: string;
  qty: number;
};

export type MatchEvent = {
  id: number;
  team_id: number;
  player_id: number | null;
  player_name: string;
  event_type: string;
  turn: number | null;
  spp_awarded: number;
};

export type MatchState = ShortMatch & {
  home: Side;
  away: Side;
  petty_cash_amount: number;
  petty_cash_team_id: number | null;
  petty_cash_spent: number;
  petty_cash_remaining: number;
  inducements: Inducement[];
  weather_roll: number | null;
  weather: RollCard;
  prayer_roll: number | null;
  prayer: RollCard;
  kick_off_roll: number | null;
  kick_off: RollCard;
  kicking_team_id: number | null;
  bounty: Bounty | null;
  current_turn: number;
  home_aggregates: Record<string, number>;
  away_aggregates: Record<string, number>;
  free_reroll_used: { home: boolean; away: boolean };
  free_bribe_used: { home: boolean; away: boolean };
  home_winnings: number;
  away_winnings: number;
  home_mvp_player_id: number | null;
  away_mvp_player_id: number | null;
  home_bounty_gold: number;
  away_bounty_gold: number;
  home_sponsor_gold: number;
  away_sponsor_gold: number;
  closure_applied: boolean;
  events: MatchEvent[];
  injuries: {
    id: number;
    team_id: number;
    player_id: number;
    player_name: string;
    result: string;
    mercy_gold: number;
    note: string;
  }[];
};

export type Dashboard = {
  team: TeamCard;
  roster: Player[];
  ctv: Ctv;
  standings: Standing[];
  scoring_summary: string;
  current_round: number;
  active_bounty: Bounty | null;
  sponsor_log: string[];
  next_match: ShortMatch | null;
  round_matches: ShortMatch[];
};

export type Rules = {
  scoring: { summary: string };
  mercy: { summary: string };
  winnings: { summary: string };
  sponsors: Sponsor[];
  bounties: Bounty[];
  spp: Record<string, number>;
};
