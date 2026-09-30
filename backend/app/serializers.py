"""Conversion de modelos de base de datos a esquemas publicos."""

from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from app import league_engine, rules
from app.models import (
    Bounty,
    LeagueState,
    Match,
    MatchEvent,
    MatchInducement,
    Player,
    Sponsor,
    Team,
    TreasurySpill,
)
from app.schemas import (
    BountyPublic,
    InducementPublic,
    LeagueStatePublic,
    MatchDetail,
    MatchEventPublic,
    MatchSummary,
    PlayerPublic,
    SponsorPublic,
    TeamDetail,
    TeamSummary,
    TreasurySpillPublic,
)


def split_skills(raw: str) -> list[str]:
    return [s.strip() for s in (raw or "").split(",") if s.strip()]


def player_public(player: Player) -> PlayerPublic:
    return PlayerPublic(
        id=player.id or 0,
        team_id=player.team_id,
        number=player.number,
        name=player.name,
        position=player.position,
        ma=player.ma,
        st=player.st,
        ag=player.ag,
        pa=player.pa,
        av=player.av,
        skills=split_skills(player.skills),
        cost=player.cost,
        current_value=player.current_value,
        spp=player.spp,
        status=player.status,
        level=rules.level_for_spp(player.spp),
        niggling_injuries=player.niggling_injuries,
        counts_towards_ctv=league_engine.player_counts_towards_ctv(player),
    )


def sponsor_public(sponsor: Optional[Sponsor]) -> Optional[SponsorPublic]:
    if sponsor is None:
        return None
    return SponsorPublic(
        id=sponsor.id or 0,
        code=sponsor.code,
        name=sponsor.name,
        metric=sponsor.metric,
        description=sponsor.description,
        benefit=sponsor.benefit,
    )


def bounty_public(bounty: Optional[Bounty]) -> Optional[BountyPublic]:
    if bounty is None:
        return None
    return BountyPublic(
        id=bounty.id or 0,
        code=bounty.code,
        name=bounty.name,
        description=bounty.description,
        reward_gold=bounty.reward_gold,
    )


def spill_public(session: Session, spill: TreasurySpill) -> TreasurySpillPublic:
    team = session.get(Team, spill.team_id)
    match = session.get(Match, spill.match_id)
    opponent_name = ""
    if match is not None:
        opponent_id = match.away_team_id if match.home_team_id == spill.team_id else match.home_team_id
        opponent = session.get(Team, opponent_id)
        opponent_name = opponent.name if opponent is not None else ""
    return TreasurySpillPublic(
        id=spill.id or 0,
        round_number=spill.round_number,
        match_id=spill.match_id,
        team_id=spill.team_id,
        team_name=team.name if team is not None else "",
        opponent_name=opponent_name,
        gold_lost=spill.gold_lost,
        winnings=spill.winnings,
        treasury_before=spill.treasury_before,
        headline=spill.headline,
    )


def team_summary(session: Session, team: Team) -> TeamSummary:
    sponsor = session.get(Sponsor, team.current_sponsor_id) if team.current_sponsor_id else None
    return TeamSummary(
        id=team.id or 0,
        name=team.name,
        coach_name=team.coach_name,
        race=team.race,
        logo=team.logo,
        treasury=team.treasury,
        ctv=league_engine.compute_ctv(session, team).total,
        fans=team.fans,
        current_sponsor_id=team.current_sponsor_id,
        current_sponsor=sponsor_public(sponsor),
    )


def team_detail(session: Session, team: Team) -> TeamDetail:
    players = session.exec(
        select(Player).where(Player.team_id == team.id).order_by(Player.number)
    ).all()
    sponsor = session.get(Sponsor, team.current_sponsor_id) if team.current_sponsor_id else None
    return TeamDetail(
        id=team.id or 0,
        name=team.name,
        coach_name=team.coach_name,
        race=team.race,
        logo=team.logo,
        treasury=team.treasury,
        rerolls=team.rerolls,
        reroll_cost=team.reroll_cost,
        assistant_coaches=team.assistant_coaches,
        cheerleaders=team.cheerleaders,
        apothecary=team.apothecary,
        fans=team.fans,
        sponsor_preference=[c for c in (team.sponsor_preference or "").split(",") if c],
        rookie_safety_claims=team.rookie_safety_claims,
        current_sponsor=sponsor_public(sponsor),
        ctv=league_engine.compute_ctv(session, team, players),
        players=[player_public(p) for p in players],
    )


def match_summary(session: Session, match: Match) -> MatchSummary:
    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    return MatchSummary(
        id=match.id or 0,
        round_number=match.round_number,
        status=match.status,
        home_team_id=match.home_team_id,
        away_team_id=match.away_team_id,
        home_team_name=home.name if home else "?",
        away_team_name=away.name if away else "?",
        home_logo=home.logo if home else "",
        away_logo=away.logo if away else "",
        home_td=match.home_td,
        away_td=match.away_td,
    )


def event_public(event: MatchEvent, names: dict[int, str], team_names: dict[int, str]) -> MatchEventPublic:
    return MatchEventPublic(
        id=event.id or 0,
        match_id=event.match_id,
        team_id=event.team_id,
        team_name=team_names.get(event.team_id, "?"),
        player_id=event.player_id,
        player_name=names.get(event.player_id) if event.player_id else None,
        event_type=event.event_type,
        turn=event.turn,
        spp_awarded=event.spp_awarded,
        victim_player_id=event.victim_player_id,
        victim_player_name=names.get(event.victim_player_id) if event.victim_player_id else None,
        casualty_result=event.casualty_result,
        note=event.note,
        created_at=event.created_at,
    )


def inducement_public(item: MatchInducement) -> InducementPublic:
    return InducementPublic(
        id=item.id or 0,
        match_id=item.match_id,
        team_id=item.team_id,
        code=item.code,
        name=item.name,
        quantity=item.quantity,
        unit_cost=item.unit_cost,
        total_cost=item.total_cost,
    )


def match_detail(session: Session, match: Match) -> MatchDetail:
    home = session.get(Team, match.home_team_id)
    away = session.get(Team, match.away_team_id)
    if home is None or away is None:  # pragma: no cover - integridad referencial
        raise ValueError("El partido apunta a un equipo inexistente")

    home_players = session.exec(
        select(Player).where(Player.team_id == home.id).order_by(Player.number)
    ).all()
    away_players = session.exec(
        select(Player).where(Player.team_id == away.id).order_by(Player.number)
    ).all()

    events = session.exec(
        select(MatchEvent).where(MatchEvent.match_id == match.id).order_by(MatchEvent.id)
    ).all()
    inducements = session.exec(
        select(MatchInducement).where(MatchInducement.match_id == match.id).order_by(MatchInducement.id)
    ).all()

    names = {p.id: p.name for p in [*home_players, *away_players] if p.id}
    team_names = {home.id: home.name, away.id: away.name}

    spent = sum(i.total_cost for i in inducements)
    bounty = session.get(Bounty, match.bounty_id) if match.bounty_id else None

    scoreboard: dict[str, dict[str, int]] = {}
    for team in (home, away):
        team_events = [e for e in events if e.team_id == team.id]
        scoreboard[str(team.id)] = {
            "TD": sum(1 for e in team_events if e.event_type == "TD"),
            "CAS": sum(1 for e in team_events if e.event_type == "CAS"),
            "FOUL": sum(1 for e in team_events if e.event_type == "FOUL"),
            "PASS": sum(1 for e in team_events if e.event_type == "PASS"),
            "INT": sum(1 for e in team_events if e.event_type == "INT"),
        }

    return MatchDetail(
        id=match.id or 0,
        round_number=match.round_number,
        status=match.status,
        home_team=team_summary(session, home),
        away_team=team_summary(session, away),
        home_td=match.home_td,
        away_td=match.away_td,
        home_ctv=match.home_ctv,
        away_ctv=match.away_ctv,
        petty_cash_amount=match.petty_cash_amount,
        petty_cash_team_id=match.petty_cash_team_id,
        petty_cash_spent=spent,
        petty_cash_remaining=max(match.petty_cash_amount - spent, 0),
        home_ready=match.home_ready,
        away_ready=match.away_ready,
        weather_roll=match.weather_roll,
        weather=rules.weather_entry(match.weather_roll) if match.weather_roll else None,
        prayer_roll=match.prayer_roll,
        prayer=rules.prayer_entry(match.prayer_roll) if match.prayer_roll else None,
        prayer_team_id=match.prayer_team_id,
        kick_off_roll=match.kick_off_roll,
        kick_off=rules.kick_off_entry(match.kick_off_roll) if match.kick_off_roll else None,
        bounty=bounty_public(bounty),
        bounty_winner_team_id=match.bounty_winner_team_id,
        home_winnings=match.home_winnings,
        away_winnings=match.away_winnings,
        home_winnings_roll=match.home_winnings_roll,
        away_winnings_roll=match.away_winnings_roll,
        home_fans_roll=match.home_fans_roll,
        away_fans_roll=match.away_fans_roll,
        home_fans_before=match.home_fans_before,
        away_fans_before=match.away_fans_before,
        home_fans_after=match.home_fans_after,
        away_fans_after=match.away_fans_after,
        home_gold_discarded=match.home_gold_discarded,
        away_gold_discarded=match.away_gold_discarded,
        conceded_by_team_id=match.conceded_by_team_id,
        home_mvp_player_id=match.home_mvp_player_id,
        away_mvp_player_id=match.away_mvp_player_id,
        inducements=[inducement_public(i) for i in inducements],
        events=[event_public(e, names, team_names) for e in events],
        home_players=[player_public(p) for p in home_players],
        away_players=[player_public(p) for p in away_players],
        scoreboard=scoreboard,
    )


def league_state_public(session: Session, state: LeagueState) -> LeagueStatePublic:
    bounty = session.get(Bounty, state.active_bounty_id) if state.active_bounty_id else None
    return LeagueStatePublic(
        name=state.name,
        current_round=state.current_round,
        total_rounds=state.total_rounds,
        active_bounty=bounty_public(bounty),
        rookie_safety_last_round=state.rookie_safety_last_round,
        sponsors_first_round=int(rules.sponsor_rules().get("first_round", 3)),
    )
