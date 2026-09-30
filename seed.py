import os
from sqlmodel import Session, select
from database import engine, create_db_and_tables
from models import Team, Player, Match, MatchEvent, LeagueState

TEAMS_DATA = [
    {
        "name": "Reikland Reavers",
        "coach_name": "Coach Miller",
        "race": "Humanos",
        "pin": "1111",
        "treasury": 1_000_000,
        "rerolls": 3,
        "reroll_cost": 50_000,
        "apothecary": 1,
        "assistant_coaches": 1,
        "cheerleaders": 1,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Griffith", "position": "Blitzer", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Block", "cost": 85_000},
            {"number": 2, "name": "Valen", "position": "Blitzer", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Block", "cost": 85_000},
            {"number": 3, "name": "Klaus", "position": "Thrower", "ma": 6, "st": 3, "ag": "3+", "pa": "2+", "av": "9+", "skills": "Pass, Sure Hands", "cost": 80_000},
            {"number": 4, "name": "Helmut", "position": "Catcher", "ma": 8, "st": 2, "ag": "3+", "pa": "5+", "av": "8+", "skills": "Catch, Dodge", "cost": 65_000},
            {"number": 5, "name": "Dieter", "position": "Catcher", "ma": 8, "st": 2, "ag": "3+", "pa": "5+", "av": "8+", "skills": "Catch, Dodge", "cost": 65_000},
            {"number": 6, "name": "Hans", "position": "Lineman", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "", "cost": 50_000},
            {"number": 7, "name": "Otto", "position": "Lineman", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "", "cost": 50_000},
            {"number": 8, "name": "Fritz", "position": "Lineman", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "", "cost": 50_000},
            {"number": 9, "name": "Karl", "position": "Lineman", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "", "cost": 50_000},
            {"number": 10, "name": "Gunter", "position": "Lineman", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "", "cost": 50_000},
            {"number": 11, "name": "Heinrich", "position": "Lineman", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "", "cost": 50_000},
        ]
    },
    {
        "name": "Gouged Eye",
        "coach_name": "Coach Varag",
        "race": "Orcos",
        "pin": "2222",
        "treasury": 1_000_000,
        "rerolls": 3,
        "reroll_cost": 60_000,
        "apothecary": 1,
        "assistant_coaches": 1,
        "cheerleaders": 1,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Ugluk", "position": "Black Orc Blocker", "ma": 4, "st": 4, "ag": "4+", "pa": "-", "av": "10+", "skills": "Brawler", "cost": 90_000},
            {"number": 2, "name": "Grishnak", "position": "Black Orc Blocker", "ma": 4, "st": 4, "ag": "4+", "pa": "-", "av": "10+", "skills": "Brawler", "cost": 90_000},
            {"number": 3, "name": "Gorbag", "position": "Black Orc Blocker", "ma": 4, "st": 4, "ag": "4+", "pa": "-", "av": "10+", "skills": "Brawler", "cost": 90_000},
            {"number": 4, "name": "Shagrat", "position": "Black Orc Blocker", "ma": 4, "st": 4, "ag": "4+", "pa": "-", "av": "10+", "skills": "Brawler", "cost": 90_000},
            {"number": 5, "name": "Borg", "position": "Blitzer", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "10+", "skills": "Block", "cost": 80_000},
            {"number": 6, "name": "Krag", "position": "Blitzer", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "10+", "skills": "Block", "cost": 80_000},
            {"number": 7, "name": "Skab", "position": "Thrower", "ma": 5, "st": 3, "ag": "3+", "pa": "3+", "av": "10+", "skills": "Pass, Sure Hands", "cost": 65_000},
            {"number": 8, "name": "Grot", "position": "Goblin", "ma": 6, "st": 2, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge, Right Stuff, Stunty", "cost": 40_000},
            {"number": 9, "name": "Lug", "position": "Lineman", "ma": 5, "st": 3, "ag": "3+", "pa": "4+", "av": "10+", "skills": "", "cost": 50_000},
            {"number": 10, "name": "Gash", "position": "Lineman", "ma": 5, "st": 3, "ag": "3+", "pa": "4+", "av": "10+", "skills": "", "cost": 50_000},
            {"number": 11, "name": "Mug", "position": "Lineman", "ma": 5, "st": 3, "ag": "3+", "pa": "4+", "av": "10+", "skills": "", "cost": 50_000},
        ]
    },
    {
        "name": "Athel Loren Foresters",
        "coach_name": "Coach Jordell",
        "race": "Elfos Silvanos",
        "pin": "3333",
        "treasury": 1_000_000,
        "rerolls": 2,
        "reroll_cost": 50_000,
        "apothecary": 1,
        "assistant_coaches": 0,
        "cheerleaders": 0,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Faelar", "position": "Wardancer", "ma": 8, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "Block, Dodge, Leap", "cost": 125_000},
            {"number": 2, "name": "Silas", "position": "Wardancer", "ma": 8, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "Block, Dodge, Leap", "cost": 125_000},
            {"number": 3, "name": "Elendir", "position": "Thrower", "ma": 7, "st": 3, "ag": "2+", "pa": "2+", "av": "8+", "skills": "Pass", "cost": 95_000},
            {"number": 4, "name": "Caelen", "position": "Catcher", "ma": 8, "st": 2, "ag": "2+", "pa": "4+", "av": "8+", "skills": "Catch, Dodge", "cost": 90_000},
            {"number": 5, "name": "Arion", "position": "Lineman", "ma": 7, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "", "cost": 70_000},
            {"number": 6, "name": "Thalion", "position": "Lineman", "ma": 7, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "", "cost": 70_000},
            {"number": 7, "name": "Lethir", "position": "Lineman", "ma": 7, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "", "cost": 70_000},
            {"number": 8, "name": "Galad", "position": "Lineman", "ma": 7, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "", "cost": 70_000},
            {"number": 9, "name": "Finrod", "position": "Lineman", "ma": 7, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "", "cost": 70_000},
            {"number": 10, "name": "Belen", "position": "Lineman", "ma": 7, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "", "cost": 70_000},
            {"number": 11, "name": "Erendir", "position": "Lineman", "ma": 7, "st": 3, "ag": "2+", "pa": "4+", "av": "8+", "skills": "", "cost": 70_000},
        ]
    },
    {
        "name": "Dwarf Giants",
        "coach_name": "Coach Grim",
        "race": "Enanos",
        "pin": "4444",
        "treasury": 1_000_000,
        "rerolls": 3,
        "reroll_cost": 50_000,
        "apothecary": 1,
        "assistant_coaches": 1,
        "cheerleaders": 0,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Grombrindal", "position": "Blitzer", "ma": 5, "st": 3, "ag": "3+", "pa": "4+", "av": "10+", "skills": "Block, Thick Skull", "cost": 80_000},
            {"number": 2, "name": "Thorin", "position": "Blitzer", "ma": 5, "st": 3, "ag": "3+", "pa": "4+", "av": "10+", "skills": "Block, Thick Skull", "cost": 80_000},
            {"number": 3, "name": "Gotrek", "position": "Troll Slayer", "ma": 5, "st": 3, "ag": "4+", "pa": "-", "av": "9+", "skills": "Block, Dauntless, Frenzy, Thick Skull", "cost": 90_000},
            {"number": 4, "name": "Snorri", "position": "Troll Slayer", "ma": 5, "st": 3, "ag": "4+", "pa": "-", "av": "9+", "skills": "Block, Dauntless, Frenzy, Thick Skull", "cost": 90_000},
            {"number": 5, "name": "Barundin", "position": "Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Sure Hands, Thick Skull", "cost": 85_000},
            {"number": 6, "name": "Duregar", "position": "Blocker", "ma": 4, "st": 3, "ag": "4+", "pa": "-", "av": "10+", "skills": "Block, Tackle, Thick Skull", "cost": 70_000},
            {"number": 7, "name": "Borek", "position": "Blocker", "ma": 4, "st": 3, "ag": "4+", "pa": "-", "av": "10+", "skills": "Block, Tackle, Thick Skull", "cost": 70_000},
            {"number": 8, "name": "Krag", "position": "Blocker", "ma": 4, "st": 3, "ag": "4+", "pa": "-", "av": "10+", "skills": "Block, Tackle, Thick Skull", "cost": 70_000},
            {"number": 9, "name": "Thorek", "position": "Blocker", "ma": 4, "st": 3, "ag": "4+", "pa": "-", "av": "10+", "skills": "Block, Tackle, Thick Skull", "cost": 70_000},
            {"number": 10, "name": "Gunnar", "position": "Blocker", "ma": 4, "st": 3, "ag": "4+", "pa": "-", "av": "10+", "skills": "Block, Tackle, Thick Skull", "cost": 70_000},
            {"number": 11, "name": "Balin", "position": "Blocker", "ma": 4, "st": 3, "ag": "4+", "pa": "-", "av": "10+", "skills": "Block, Tackle, Thick Skull", "cost": 70_000},
        ]
    },
    {
        "name": "Champions of Death",
        "coach_name": "Coach Tom",
        "race": "No-Muertos",
        "pin": "5555",
        "treasury": 1_000_000,
        "rerolls": 3,
        "reroll_cost": 60_000,
        "apothecary": 0, # Undead cannot have apothecary
        "assistant_coaches": 0,
        "cheerleaders": 0,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Rattles", "position": "Mummy", "ma": 3, "st": 5, "ag": "5+", "pa": "-", "av": "10+", "skills": "Mighty Blow (+1), Regeneration", "cost": 125_000},
            {"number": 2, "name": "Dusty", "position": "Mummy", "ma": 3, "st": 5, "ag": "5+", "pa": "-", "av": "10+", "skills": "Mighty Blow (+1), Regeneration", "cost": 125_000},
            {"number": 3, "name": "Bones", "position": "Wight Blitzer", "ma": 6, "st": 3, "ag": "3+", "pa": "5+", "av": "9+", "skills": "Block, Regeneration", "cost": 90_000},
            {"number": 4, "name": "Skully", "position": "Wight Blitzer", "ma": 6, "st": 3, "ag": "3+", "pa": "5+", "av": "9+", "skills": "Block, Regeneration", "cost": 90_000},
            {"number": 5, "name": "Snarl", "position": "Ghoul Runner", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge", "cost": 75_000},
            {"number": 6, "name": "Bitey", "position": "Ghoul Runner", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge", "cost": 75_000},
            {"number": 7, "name": "Walky", "position": "Zombie Lineman", "ma": 4, "st": 3, "ag": "5+", "pa": "-", "av": "9+", "skills": "Regeneration", "cost": 40_000},
            {"number": 8, "name": "Groany", "position": "Zombie Lineman", "ma": 4, "st": 3, "ag": "5+", "pa": "-", "av": "9+", "skills": "Regeneration", "cost": 40_000},
            {"number": 9, "name": "Clanky", "position": "Skeleton Lineman", "ma": 5, "st": 3, "ag": "4+", "pa": "6+", "av": "8+", "skills": "Regeneration, Thick Skull", "cost": 40_000},
            {"number": 10, "name": "Ribby", "position": "Skeleton Lineman", "ma": 5, "st": 3, "ag": "4+", "pa": "6+", "av": "8+", "skills": "Regeneration, Thick Skull", "cost": 40_000},
            {"number": 11, "name": "Creaky", "position": "Skeleton Lineman", "ma": 5, "st": 3, "ag": "4+", "pa": "6+", "av": "8+", "skills": "Regeneration, Thick Skull", "cost": 40_000},
        ]
    },
    {
        "name": "Skavenblight Scramblers",
        "coach_name": "Coach Queek",
        "race": "Skaven",
        "pin": "6666",
        "treasury": 1_000_000,
        "rerolls": 3,
        "reroll_cost": 50_000,
        "apothecary": 1,
        "assistant_coaches": 1,
        "cheerleaders": 1,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Quick-tail", "position": "Gutter Runner", "ma": 9, "st": 2, "ag": "2+", "pa": "4+", "av": "8+", "skills": "Dodge", "cost": 85_000},
            {"number": 2, "name": "Shadow-paw", "position": "Gutter Runner", "ma": 9, "st": 2, "ag": "2+", "pa": "4+", "av": "8+", "skills": "Dodge", "cost": 85_000},
            {"number": 3, "name": "Fang-strike", "position": "Blitzer", "ma": 7, "st": 3, "ag": "3+", "pa": "5+", "av": "9+", "skills": "Block", "cost": 90_000},
            {"number": 4, "name": "Claw-rend", "position": "Blitzer", "ma": 7, "st": 3, "ag": "3+", "pa": "5+", "av": "9+", "skills": "Block", "cost": 90_000},
            {"number": 5, "name": "Squeak-pass", "position": "Thrower", "ma": 7, "st": 3, "ag": "3+", "pa": "2+", "av": "8+", "skills": "Pass, Sure Hands", "cost": 85_000},
            {"number": 6, "name": "Ratch", "position": "Lineman", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "", "cost": 50_000},
            {"number": 7, "name": "Sneek", "position": "Lineman", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "", "cost": 50_000},
            {"number": 8, "name": "Skit", "position": "Lineman", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "", "cost": 50_000},
            {"number": 9, "name": "Vermin", "position": "Lineman", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "", "cost": 50_000},
            {"number": 10, "name": "Gnaw", "position": "Lineman", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "", "cost": 50_000},
            {"number": 11, "name": "Nibbler", "position": "Lineman", "ma": 7, "st": 3, "ag": "3+", "pa": "4+", "av": "8+", "skills": "", "cost": 50_000},
        ]
    },
    {
        "name": "Doom Diver Renegades",
        "coach_name": "Coach Malakor",
        "race": "Elegidos del Caos",
        "pin": "7777",
        "treasury": 1_000_000,
        "rerolls": 3,
        "reroll_cost": 60_000,
        "apothecary": 1,
        "assistant_coaches": 0,
        "cheerleaders": 1,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Bloodgor", "position": "Chaos Chosen Blocker", "ma": 5, "st": 4, "ag": "3+", "pa": "5+", "av": "10+", "skills": "", "cost": 100_000},
            {"number": 2, "name": "Ironhorn", "position": "Chaos Chosen Blocker", "ma": 5, "st": 4, "ag": "3+", "pa": "5+", "av": "10+", "skills": "", "cost": 100_000},
            {"number": 3, "name": "Skullsplitter", "position": "Chaos Chosen Blocker", "ma": 5, "st": 4, "ag": "3+", "pa": "5+", "av": "10+", "skills": "", "cost": 100_000},
            {"number": 4, "name": "Dreadblade", "position": "Chaos Chosen Blocker", "ma": 5, "st": 4, "ag": "3+", "pa": "5+", "av": "10+", "skills": "", "cost": 100_000},
            {"number": 5, "name": "Gorgoroth", "position": "Beastman Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Horns", "cost": 60_000},
            {"number": 6, "name": "Bovinus", "position": "Beastman Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Horns", "cost": 60_000},
            {"number": 7, "name": "Capra", "position": "Beastman Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Horns", "cost": 60_000},
            {"number": 8, "name": "Hircus", "position": "Beastman Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Horns", "cost": 60_000},
            {"number": 9, "name": "Minotaur-kin", "position": "Beastman Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Horns", "cost": 60_000},
            {"number": 10, "name": "Hoof-smash", "position": "Beastman Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Horns", "cost": 60_000},
            {"number": 11, "name": "Blackhorn", "position": "Beastman Runner", "ma": 6, "st": 3, "ag": "3+", "pa": "4+", "av": "9+", "skills": "Horns", "cost": 60_000},
        ]
    },
    {
        "name": "Lustria Croakers",
        "coach_name": "Coach Tehenhauin",
        "race": "Hombres Lagarto",
        "pin": "8888",
        "treasury": 1_000_000,
        "rerolls": 2,
        "reroll_cost": 70_000,
        "apothecary": 1,
        "assistant_coaches": 1,
        "cheerleaders": 0,
        "fans": 1,
        "players": [
            {"number": 1, "name": "Klaq", "position": "Saurus Blocker", "ma": 6, "st": 4, "ag": "5+", "pa": "6+", "av": "10+", "skills": "", "cost": 85_000},
            {"number": 2, "name": "Zlat", "position": "Saurus Blocker", "ma": 6, "st": 4, "ag": "5+", "pa": "6+", "av": "10+", "skills": "", "cost": 85_000},
            {"number": 3, "name": "Xhotl", "position": "Saurus Blocker", "ma": 6, "st": 4, "ag": "5+", "pa": "6+", "av": "10+", "skills": "", "cost": 85_000},
            {"number": 4, "name": "Chaq", "position": "Saurus Blocker", "ma": 6, "st": 4, "ag": "5+", "pa": "6+", "av": "10+", "skills": "", "cost": 85_000},
            {"number": 5, "name": "Tlaxt", "position": "Saurus Blocker", "ma": 6, "st": 4, "ag": "5+", "pa": "6+", "av": "10+", "skills": "", "cost": 85_000},
            {"number": 6, "name": "Itza", "position": "Saurus Blocker", "ma": 6, "st": 4, "ag": "5+", "pa": "6+", "av": "10+", "skills": "", "cost": 85_000},
            {"number": 7, "name": "Tik", "position": "Skink Runner", "ma": 8, "st": 2, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge, Stunty", "cost": 60_000},
            {"number": 8, "name": "Tak", "position": "Skink Runner", "ma": 8, "st": 2, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge, Stunty", "cost": 60_000},
            {"number": 9, "name": "Pox", "position": "Skink Runner", "ma": 8, "st": 2, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge, Stunty", "cost": 60_000},
            {"number": 10, "name": "Zul", "position": "Skink Runner", "ma": 8, "st": 2, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge, Stunty", "cost": 60_000},
            {"number": 11, "name": "Kixi", "position": "Skink Runner", "ma": 8, "st": 2, "ag": "3+", "pa": "4+", "av": "8+", "skills": "Dodge, Stunty", "cost": 60_000},
        ]
    }
]

def generate_round_robin_schedule(team_ids):
    """
    Standard circle method for round robin scheduling.
    For 8 teams, generates 7 rounds with 4 matches each.
    """
    n = len(team_ids)
    rounds = []
    teams = list(team_ids)
    
    for r in range(n - 1):
        round_matches = []
        for i in range(n // 2):
            t1 = teams[i]
            t2 = teams[n - 1 - i]
            # Alternate home/away based on round for fairness
            if (r + i) % 2 == 0:
                round_matches.append((t1, t2))
            else:
                round_matches.append((t2, t1))
        rounds.append(round_matches)
        # Rotate teams keeping the first fixed
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
        
    return rounds

def seed_database(reset=True):
    create_db_and_tables()
    
    with Session(engine) as session:
        if reset:
            # Clear existing data in correct order
            session.exec(select(MatchEvent)).all()
            for m in session.exec(select(MatchEvent)).all():
                session.delete(m)
            for m in session.exec(select(Match)).all():
                session.delete(m)
            for p in session.exec(select(Player)).all():
                session.delete(p)
            for t in session.exec(select(Team)).all():
                session.delete(t)
            for s in session.exec(select(LeagueState)).all():
                session.delete(s)
            session.commit()
            
        # Check if already seeded
        existing_teams = session.exec(select(Team)).all()
        if existing_teams:
            print("Database already contains teams. Skipping seed.")
            return

        print("Seeding Blood Bowl teams...")
        created_team_ids = []
        for team_data in TEAMS_DATA:
            players_data = team_data.pop("players")
            team = Team(**team_data)
            session.add(team)
            session.commit()
            session.refresh(team)
            created_team_ids.append(team.id)
            
            for p_data in players_data:
                player = Player(
                    team_id=team.id,
                    current_value=p_data["cost"],
                    **p_data
                )
                session.add(player)
            session.commit()
            
        print(f"Created {len(created_team_ids)} teams with 11 players each.")
        
        # Create Round Robin Matches
        rounds = generate_round_robin_schedule(created_team_ids)
        for r_idx, round_matches in enumerate(rounds):
            round_num = r_idx + 1
            for home_id, away_id in round_matches:
                match = Match(
                    round_number=round_num,
                    home_team_id=home_id,
                    away_team_id=away_id,
                    status="SCHEDULED"
                )
                session.add(match)
        session.commit()
        print(f"Scheduled 7 rounds of matches ({len(rounds) * 4} matches total).")
        
        # Seed LeagueState
        league_state = LeagueState(
            id=1,
            league_name="Liga Blood Bowl BB2020",
            current_round=1,
            total_rounds=7,
            active_bounty_id="cazador_de_cabezas",
            master_key="bbmaster2026"
        )
        session.add(league_state)
        session.commit()
        print("Seeded LeagueState.")

if __name__ == "__main__":
    seed_database(reset=True)
