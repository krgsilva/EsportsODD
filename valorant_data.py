"""
Dados de Valorant (VCT) - lê o dataset "Valorant Champion Tour Data" do
Kaggle (por ryanluong1), organizado em pastas data/valorant/vct_<ano>/
com subpastas matches/, ids/ (e agents/, players_stats/ não usadas aqui).

Cada pasta vct_<ano>/matches/ precisa ter pelo menos:
    overview.csv       (estatística de cada jogador em cada mapa)
    maps_scores.csv    (placar de cada mapa)
e vct_<ano>/ids/ precisa ter:
    tournaments_stages_matches_games_ids.csv  (IDs pra ordenar por data)

Assim como no LoL, tudo roda local e em cache — sem internet, sem rate
limit.
"""

import csv
import os
import glob

_DATA_DIR_V = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "valorant")
os.makedirs(_DATA_DIR_V, exist_ok=True)

_year_cache = {}  # "2026" -> {"mtime":..., "games":[], "by_team":{}, "tournaments":{}}


def _year_folders():
    """Retorna {"2026": "/caminho/data/valorant/vct_2026", ...}"""
    out = {}
    for path in glob.glob(os.path.join(_DATA_DIR_V, "vct_*")):
        if os.path.isdir(path):
            year = os.path.basename(path).replace("vct_", "").strip()
            if year.isdigit():
                out[year] = path
    return out


def v_years():
    return sorted(_year_folders().keys(), reverse=True)


def _to_float(v, default=0.0):
    if v is None:
        return default
    s = str(v).strip().replace("%", "")
    if s in ("", "-"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _folder_mtime(year_folder):
    key_files = [
        os.path.join(year_folder, "matches", "maps_scores.csv"),
        os.path.join(year_folder, "matches", "overview.csv"),
    ]
    return tuple(os.path.getmtime(p) for p in key_files if os.path.exists(p))


def _load_year(year):
    folders = _year_folders()
    if year not in folders:
        return {"games": [], "by_team": {}, "tournaments": {}}
    year_folder = folders[year]
    mtime = _folder_mtime(year_folder)
    cached = _year_cache.get(year)
    if cached and cached["mtime"] == mtime:
        return cached

    matches_dir = os.path.join(year_folder, "matches")
    ids_dir = os.path.join(year_folder, "ids")
    maps_scores_path = os.path.join(matches_dir, "maps_scores.csv")
    overview_path = os.path.join(matches_dir, "overview.csv")
    ids_path = os.path.join(ids_dir, "tournaments_stages_matches_games_ids.csv")

    if not os.path.exists(maps_scores_path) or not os.path.exists(overview_path):
        result = {"mtime": mtime, "games": [], "by_team": {}, "tournaments": {}}
        _year_cache[year] = result
        return result

    def jkey(row):
        return (row.get("Tournament", ""), row.get("Stage", ""), row.get("Match Type", ""),
                row.get("Match Name", ""), row.get("Map", ""))

    # 1) IDs -> pra ordenar por data (Match ID/Game ID crescem com o tempo)
    id_lookup = {}
    if os.path.exists(ids_path):
        with open(ids_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                id_lookup[jkey(row)] = (
                    int(row.get("Match ID") or 0),
                    int(row.get("Game ID") or 0),
                )

    # 2) Jogadores por (mapa, time)
    players_by_key = {}
    with open(overview_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if (row.get("Side") or "").strip().lower() != "both":
                continue
            k = jkey(row) + (row.get("Team", ""),)
            players_by_key.setdefault(k, []).append({
                "jogador": row.get("Player", ""),
                "agente": row.get("Agents", ""),
                "rating": _to_float(row.get("Rating")),
                "acs": _to_float(row.get("Average Combat Score")),
                "kills": _to_float(row.get("Kills")),
                "deaths": _to_float(row.get("Deaths")),
                "assists": _to_float(row.get("Assists")),
                "adr": _to_float(row.get("Average Damage Per Round")),
                "hs_pct": _to_float(row.get("Headshot %")),
                "fk": _to_float(row.get("First Kills")),
                "fd": _to_float(row.get("First Deaths")),
            })

    # 3) Placar por mapa -> registro por time (2 por mapa: A e B)
    games = []
    with open(maps_scores_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            k = jkey(row)
            mid, gid = id_lookup.get(k, (0, 0))
            team_a = row.get("Team A", "").strip()
            team_b = row.get("Team B", "").strip()
            score_a = _to_float(row.get("Team A Score"))
            score_b = _to_float(row.get("Team B Score"))
            atk_a = _to_float(row.get("Team A Attacker Score"))
            def_a = _to_float(row.get("Team A Defender Score"))
            atk_b = _to_float(row.get("Team B Attacker Score"))
            def_b = _to_float(row.get("Team B Defender Score"))
            if not team_a or not team_b:
                continue
            tournament = row.get("Tournament", "")
            base = {
                "tournament_id": tournament,
                "tournament_label": tournament,
                "stage": row.get("Stage", ""),
                "year": year,
                "map": row.get("Map", ""),
                "match_id": mid, "game_id": gid,
                "duracao": row.get("Duration", ""),
            }
            games.append({**base, "team": team_a, "opponent": team_b,
                          "score_for": score_a, "score_against": score_b,
                          "atk_score": atk_a, "def_score": def_a,
                          "won": score_a > score_b,
                          "jogadores": players_by_key.get(k + (team_a,), [])})
            games.append({**base, "team": team_b, "opponent": team_a,
                          "score_for": score_b, "score_against": score_a,
                          "atk_score": atk_b, "def_score": def_b,
                          "won": score_b > score_a,
                          "jogadores": players_by_key.get(k + (team_b,), [])})

    games.sort(key=lambda g: (g["match_id"], g["game_id"]), reverse=True)

    by_team = {}
    tournaments = {}
    for g in games:
        by_team.setdefault(g["team"], []).append(g)
        tid = g["tournament_id"]
        t = tournaments.setdefault(tid, {"id": tid, "label": g["tournament_label"], "year": year,
                                          "teams": set(), "maps": 0, "min_id": g["match_id"], "max_id": g["match_id"]})
        t["teams"].add(g["team"])
        t["maps"] += 1
        t["min_id"] = min(t["min_id"], g["match_id"])
        t["max_id"] = max(t["max_id"], g["match_id"])

    result = {"mtime": mtime, "games": games, "by_team": by_team, "tournaments": tournaments}
    _year_cache[year] = result
    return result


def v_csv_status():
    folders = _year_folders()
    if not folders:
        return {"disponivel": False}
    total_games = 0
    total_teams = set()
    anos = []
    for year in sorted(folders.keys(), reverse=True):
        data = _load_year(year)
        total_games += len(data["games"]) // 2
        total_teams |= set(data["by_team"].keys())
        anos.append({"ano": year, "jogos_de_mapa": len(data["games"]) // 2, "campeonatos": len(data["tournaments"])})
    return {"disponivel": True, "anos": anos, "total_jogos_de_mapa": total_games, "total_times": len(total_teams)}


def v_tournaments_for_year(year):
    data = _load_year(str(year))
    out = []
    for t in data["tournaments"].values():
        out.append({"id": t["id"], "label": t["label"], "times": len(t["teams"]), "mapas": t["maps"]})
    out.sort(key=lambda x: x["label"])
    return out


def v_teams_in_tournament(tournament_id):
    data = _load_year_containing(tournament_id)
    if not data:
        return []
    t = data["tournaments"].get(tournament_id)
    return sorted(t["teams"]) if t else []


def _load_year_containing(tournament_id):
    """Acha em qual ano esse campeonato está (procura nos anos já
    conhecidos pela pasta; carrega sob demanda)."""
    for year in _year_folders():
        data = _load_year(year)
        if tournament_id in data["tournaments"]:
            return data
    return None


def v_team_games(team_name, tournament_id=None, limit=None):
    data = _load_year_containing(tournament_id) if tournament_id else None
    if data is None:
        # sem campeonato: procura o time em todos os anos carregados/disponíveis
        games = []
        for year in _year_folders():
            games.extend(_load_year(year)["by_team"].get(team_name, []))
        games.sort(key=lambda g: (g["match_id"], g["game_id"]), reverse=True)
    else:
        games = data["by_team"].get(team_name, [])
        if tournament_id:
            games = [g for g in games if g["tournament_id"] == tournament_id]
    if limit:
        games = games[:limit]
    return games


def v_maps_available(team1, team2, tournament_id=None):
    g1 = v_team_games(team1, tournament_id=tournament_id)
    g2 = v_team_games(team2, tournament_id=tournament_id)
    maps1 = {g["map"] for g in g1}
    maps2 = {g["map"] for g in g2}
    return sorted(maps1 | maps2)


def v_win_summary(games):
    if not games:
        return None
    wins = sum(1 for g in games if g["won"])
    return {"jogos": len(games), "vitorias": wins, "taxa_vitoria_pct": round(100 * wins / len(games), 1)}


def v_recent_form(games, n):
    return v_win_summary(games[:n])


def v_head_to_head(games1, opponent):
    confrontos = [g for g in games1 if g["opponent"].strip().lower() == opponent.strip().lower()]
    if not confrontos:
        return None
    wins1 = sum(1 for g in confrontos if g["won"])
    return {
        "mapas": len(confrontos),
        "vitorias_time1": wins1,
        "vitorias_time2": len(confrontos) - wins1,
        "ultimos_resultados": [
            {"mapa": g["map"], "vencedor": "time1" if g["won"] else "time2",
             "placar": f'{int(g["score_for"])}-{int(g["score_against"])}'} for g in confrontos[:15]
        ],
    }


def v_map_detail(team_name, opponent_name, map_name, tournament_id=None):
    games = [g for g in v_team_games(team_name, tournament_id=tournament_id) if g["map"] == map_name]
    if not games:
        return None
    wins = sum(1 for g in games if g["won"])
    against_opponent = [g for g in games if g["opponent"].strip().lower() == opponent_name.strip().lower()]

    players = {}
    for g in games:
        for p in g["jogadores"]:
            acc = players.setdefault(p["jogador"], {"jogador": p["jogador"], "agentes": {}, "amostras": []})
            acc["agentes"][p["agente"]] = acc["agentes"].get(p["agente"], 0) + 1
            acc["amostras"].append(p)

    jogadores = []
    for nome, acc in players.items():
        amostras = acc["amostras"]
        n = len(amostras)
        agente_mais_jogado = max(acc["agentes"].items(), key=lambda kv: kv[1])[0] if acc["agentes"] else None
        jogadores.append({
            "jogador": nome,
            "mapas_jogados": n,
            "agente_mais_jogado": agente_mais_jogado,
            "agentes_jogados": acc["agentes"],
            "media_rating": round(sum(a["rating"] for a in amostras) / n, 2),
            "media_acs": round(sum(a["acs"] for a in amostras) / n, 1),
            "media_kills": round(sum(a["kills"] for a in amostras) / n, 1),
            "media_deaths": round(sum(a["deaths"] for a in amostras) / n, 1),
            "media_assists": round(sum(a["assists"] for a in amostras) / n, 1),
            "media_adr": round(sum(a["adr"] for a in amostras) / n, 1),
            "media_hs_pct": round(sum(a["hs_pct"] for a in amostras) / n, 1),
        })
    jogadores.sort(key=lambda j: j["media_rating"], reverse=True)

    return {
        "time": team_name,
        "mapa": map_name,
        "jogos": len(games),
        "vitorias": wins,
        "derrotas": len(games) - wins,
        "taxa_vitoria_pct": round(100 * wins / len(games), 1),
        "jogos_contra_esse_adversario": len(against_opponent),
        "jogadores": jogadores,
    }
