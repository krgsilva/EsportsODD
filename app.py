"""
Analisador de Odds de E-sports (LoL) - Backend local
================================================================
Le o histórico de partidas a partir de um arquivo CSV baixado uma vez da
Oracle's Elixir (oracleselixir.com) e guardado em data/oracles_elixir.csv.
Tudo roda 100% local a partir daí: sem depender de internet, sem rate
limit, sem espera - só reiniciar o app depois de atualizar o CSV quando
quiser dados mais recentes.

Isso é uma ferramenta de apoio estatístico. Não é garantia de resultado
nem recomendação financeira - aposta envolve risco.

Como rodar:
    1. Baixe o CSV em https://oracleselixir.com/tools/downloads (link
       "Google Drive" no fim da página) e salve como
       data/oracles_elixir.csv (veja data/LEIA-ME.txt)
    2. pip install -r requirements.txt
    3. python app.py
Depois abra http://localhost:5000 no navegador.
"""

from flask import Flask, jsonify, request, send_from_directory
import csv
import os
import glob
import datetime
import valorant_data as vdata
import valorant_live_data as vlive
import lol_live

app = Flask(__name__, static_folder="static", static_url_path="")

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(_DATA_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Carregamento do CSV da Oracle's Elixir
# ---------------------------------------------------------------------------

def _csv_file_paths():
    """Aceita data/oracles_elixir.csv e também qualquer
    data/oracles_elixir*.csv (ex: oracles_elixir_2025.csv,
    oracles_elixir_2026.csv) — assim dá pra juntar vários anos."""
    paths = sorted(glob.glob(os.path.join(_DATA_DIR, "oracles_elixir*.csv")))
    return paths


def to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def to_bool01(v):
    """Converte '1'/'0'/'True'/'False'/'' pra 1, 0 ou None (desconhecido)."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("1", "true"):
        return 1
    if s in ("0", "false"):
        return 0
    return None


_games_cache = {"mtimes": None, "games": [], "by_team": {}, "tournaments": {}, "by_champion": {}, "by_champion_team": {}}


def _load_games():
    """Lê todos os CSVs da Oracle's Elixir encontrados em data/ e monta,
    pra cada time em cada jogo, um registro normalizado (do ponto de vista
    daquele time — a favor/contra/total, lado, adversário etc). Resultado
    fica em cache em memória, e só reprocessa se algum arquivo mudou."""
    paths = _csv_file_paths()
    if not paths:
        _games_cache.update({"mtimes": None, "games": [], "by_team": {}, "tournaments": {}, "diagnostico": {}, "by_champion": {}, "by_champion_team": {}})
        return _games_cache

    mtimes = tuple(sorted((p, os.path.getmtime(p)) for p in paths))
    if _games_cache["mtimes"] == mtimes:
        return _games_cache

    by_gameid = {}
    ligas_no_arquivo = {}  # liga -> quantas linhas de time (cru, antes de qualquer filtro)
    anos_no_arquivo = set()
    champion_picks = []
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pos = (row.get("position") or "").strip().lower()
                if pos != "team":
                    champ = (row.get("champion") or "").strip()
                    if champ:
                        champion_picks.append({
                            "champion": champ,
                            "team": (row.get("teamname") or "").strip(),
                            "gamelength_min": round(to_float(row.get("gamelength")) / 60, 1),
                            "date": (row.get("date") or "")[:10],
                            "gameid": row.get("gameid"),
                            "won": to_bool01(row.get("result")) == 1,
                        })
                    continue
                liga = (row.get("league") or "").strip()
                if liga:
                    ligas_no_arquivo[liga] = ligas_no_arquivo.get(liga, 0) + 1
                ano = (row.get("year") or "").strip()
                if ano:
                    anos_no_arquivo.add(ano)
                gid = row.get("gameid")
                if not gid:
                    continue
                by_gameid.setdefault(gid, []).append(row)

    games = []
    jogos_incompletos = 0
    ligas_com_jogos_incompletos = {}
    for gid, rows in by_gameid.items():
        # Agrupa por nome de time (não só conta linhas) — isso protege
        # contra arquivos duplicados na pasta data/ (mesmo gameid lido mais
        # de uma vez), que senão fariam o app achar 4/6 linhas de time pra
        # um jogo que só tem 2 times de verdade.
        por_time = {}
        for r in rows:
            nome_time = (r.get("teamname") or "").strip()
            if nome_time:
                por_time[nome_time] = r  # a última ocorrência prevalece
        rows_dedup = list(por_time.values())
        if len(rows_dedup) != 2:
            jogos_incompletos += 1
            liga = (rows_dedup[0].get("league") or "").strip() if rows_dedup else "?"
            ligas_com_jogos_incompletos[liga] = ligas_com_jogos_incompletos.get(liga, 0) + 1
            continue  # dado incompleto pra esse jogo, pula
        a, b = rows_dedup
        for me, opp in ((a, b), (b, a)):
            g = _build_game_record(me, opp)
            if g:
                g["gameid"] = gid
                games.append(g)

    # mais recente primeiro
    games.sort(key=lambda g: g["date"] or "", reverse=True)

    by_team = {}
    tournaments = {}
    for g in games:
        by_team.setdefault(g["team"], []).append(g)
        tid = g["tournament_id"]
        t = tournaments.setdefault(tid, {
            "id": tid, "label": g["tournament_label"], "league": g["league"],
            "split": g["split"], "year": g["year"], "teams": set(),
            "min_date": g["date"], "max_date": g["date"], "jogos": 0,
        })
        t["teams"].add(g["team"])
        t["jogos"] += 1
        if g["date"]:
            if not t["min_date"] or g["date"] < t["min_date"]:
                t["min_date"] = g["date"]
            if not t["max_date"] or g["date"] > t["max_date"]:
                t["max_date"] = g["date"]

    diagnostico = {
        "ligas_no_arquivo": sorted(ligas_no_arquivo.keys()),
        "anos_no_arquivo": sorted(anos_no_arquivo, reverse=True),
        "jogos_incompletos_ignorados": jogos_incompletos,
        "ligas_com_jogos_incompletos": ligas_com_jogos_incompletos,
    }

    # Cruza cada pick de campeão com o total de kills da partida em que ele
    # apareceu (pra saber o "ritmo de kills" médio de cada campeão), usando
    # o gameid+time como chave — o registro de time daquele jogo já tem o
    # kills_total certinho.
    kills_total_by_gameid_team = {(g["gameid"], g["team"]): g["kills_total"] for g in games}
    for p in champion_picks:
        p["kills_total_da_partida"] = kills_total_by_gameid_team.get((p["gameid"], p["team"]))

    by_champion = {}
    by_champion_team = {}
    for p in champion_picks:
        by_champion.setdefault(p["champion"], []).append(p)
        key = (p["champion"], p["team"])
        by_champion_team.setdefault(key, []).append(p)

    _games_cache.update({
        "mtimes": mtimes, "games": games, "by_team": by_team, "tournaments": tournaments,
        "diagnostico": diagnostico, "by_champion": by_champion, "by_champion_team": by_champion_team,
    })
    return _games_cache


def _build_game_record(me, opp):
    def f(row, *keys):
        for k in keys:
            if row.get(k) not in (None, ""):
                return to_float(row.get(k))
        return 0.0

    def f_nullable(row, key):
        v = row.get(key)
        if v in (None, ""):
            return None
        return to_float(v)

    league = (me.get("league") or "").strip()
    split = (me.get("split") or "").strip()
    year = (me.get("year") or "").strip()
    if not league or not year:
        return None
    tournament_id = f"{league}||{split}||{year}"
    tournament_label = f"{league} {split} {year}".replace("  ", " ").strip()

    side = "azul" if (me.get("side") or "").strip().lower() == "blue" else "vermelho"
    result = to_bool01(me.get("result"))
    date = (me.get("date") or "")[:10]

    kills_for = f(me, "kills")
    kills_against = f(me, "deaths")
    towers_for = f(me, "towers")
    towers_against = f(me, "opp_towers")
    dragons_for = f(me, "dragons")
    dragons_against = f(me, "opp_dragons")
    barons_for = f(me, "barons")
    barons_against = f(me, "opp_barons")
    inhib_for = f(me, "inhibitors")
    inhib_against = f(me, "opp_inhibitors")
    gold_for = f(me, "totalgold", "earnedgold")
    gold_against = f(opp, "totalgold", "earnedgold")

    k10_for = f_nullable(me, "killsat10")
    k10_against = f_nullable(me, "opp_killsat10")
    k15_for = f_nullable(me, "killsat15")
    k15_against = f_nullable(me, "opp_killsat15")
    golddiff10 = f_nullable(me, "golddiffat10")
    golddiff15 = f_nullable(me, "golddiffat15")

    return {
        "team": (me.get("teamname") or "").strip(),
        "opponent": (opp.get("teamname") or "").strip(),
        "date": date,
        "tournament_id": tournament_id,
        "tournament_label": tournament_label,
        "league": league, "split": split, "year": year,
        "patch": me.get("patch"),
        "side": side,
        "won": result == 1,
        "game_length_min": round(f(me, "gamelength") / 60, 1),
        "kills_for": kills_for, "kills_against": kills_against, "kills_total": kills_for + kills_against,
        "towers_for": towers_for, "towers_against": towers_against, "towers_total": towers_for + towers_against,
        "dragons_for": dragons_for, "dragons_against": dragons_against, "dragons_total": dragons_for + dragons_against,
        "barons_for": barons_for, "barons_against": barons_against, "barons_total": barons_for + barons_against,
        "inhibitors_for": inhib_for, "inhibitors_against": inhib_against, "inhibitors_total": inhib_for + inhib_against,
        "gold_for": gold_for, "gold_against": gold_against,
        "kills10_total": (k10_for + k10_against) if (k10_for is not None and k10_against is not None) else None,
        "kills15_total": (k15_for + k15_against) if (k15_for is not None and k15_against is not None) else None,
        "golddiff10": golddiff10, "golddiff15": golddiff15,
        "first_blood": to_bool01(me.get("firstblood")),
        "first_tower": to_bool01(me.get("firsttower")),
        "first_dragon": to_bool01(me.get("firstdragon")),
        "first_herald": to_bool01(me.get("firstherald")),
        "first_baron": to_bool01(me.get("firstbaron")),
    }


def csv_status():
    data = _load_games()
    if not data["games"]:
        return {
            "disponivel": False,
            "arquivos_procurados": ["data/oracles_elixir.csv", "data/oracles_elixir_<algo>.csv"],
            "diagnostico": data.get("diagnostico", {}),
        }
    dates = [g["date"] for g in data["games"] if g["date"]]
    anos = sorted({t["year"] for t in data["tournaments"].values()}, reverse=True)
    return {
        "disponivel": True,
        "jogos": len(data["games"]) // 2,
        "times": len(data["by_team"]),
        "campeonatos": len(data["tournaments"]),
        "atualizado_ate": max(dates) if dates else None,
        "anos_disponiveis": anos,
        "arquivos_carregados": [os.path.basename(p) for p in _csv_file_paths()],
        "diagnostico": data.get("diagnostico", {}),
    }


def team_games(team_name, tournament_id=None, limit=None):
    data = _load_games()
    games = data["by_team"].get(team_name, [])
    if tournament_id:
        games = [g for g in games if g["tournament_id"] == tournament_id]
    if limit:
        games = games[:limit]
    return games


def teams_in_tournament(tournament_id):
    data = _load_games()
    t = data["tournaments"].get(tournament_id)
    if not t:
        return []
    return sorted(t["teams"])


def tournaments_for_year(year):
    data = _load_games()
    hoje = datetime.date.today().isoformat()
    out = []
    for t in data["tournaments"].values():
        if t["year"] != str(year):
            continue
        max_date = t["max_date"] or ""
        status = "em_andamento" if max_date and (datetime.date.today() - datetime.date.fromisoformat(max_date)).days <= 21 else "encerrado"
        out.append({
            "id": t["id"], "label": t["label"], "league": t["league"], "split": t["split"],
            "jogos": t["jogos"], "times": len(t["teams"]),
            "min_date": t["min_date"], "max_date": t["max_date"], "status": status,
        })
    out.sort(key=lambda x: x["max_date"] or "", reverse=True)
    return out


# ---------------------------------------------------------------------------
# Cálculos estatísticos (independem da fonte dos dados)
# ---------------------------------------------------------------------------

def avg(games, key):
    if not games:
        return 0.0
    return round(sum(g[key] for g in games) / len(games), 2)


def hit_rate_over(games, key, line):
    if not games:
        return None
    over = sum(1 for g in games if g[key] > line)
    return round(100 * over / len(games), 1)


def build_summary(games):
    if not games:
        return None
    wins = sum(1 for g in games if g["won"])
    return {
        "jogos_analisados": len(games),
        "vitorias": wins,
        "taxa_vitoria_pct": round(100 * wins / len(games), 1),
        "media_duracao_min": avg(games, "game_length_min"),
        "kills": {"media_a_favor": avg(games, "kills_for"), "media_contra": avg(games, "kills_against"), "media_total_jogo": avg(games, "kills_total")},
        "torres": {"media_a_favor": avg(games, "towers_for"), "media_contra": avg(games, "towers_against"), "media_total_jogo": avg(games, "towers_total")},
        "dragoes": {"media_a_favor": avg(games, "dragons_for"), "media_contra": avg(games, "dragons_against"), "media_total_jogo": avg(games, "dragons_total")},
        "baroes": {"media_a_favor": avg(games, "barons_for"), "media_contra": avg(games, "barons_against"), "media_total_jogo": avg(games, "barons_total")},
        "inibidores": {"media_a_favor": avg(games, "inhibitors_for"), "media_contra": avg(games, "inhibitors_against"), "media_total_jogo": avg(games, "inhibitors_total")},
        "ouro": {"media_a_favor": avg(games, "gold_for"), "media_contra": avg(games, "gold_against")},
    }


def build_side_summary(games):
    azul = [g for g in games if g["side"] == "azul"]
    vermelho = [g for g in games if g["side"] == "vermelho"]

    def side_block(gs):
        if not gs:
            return None
        wins = sum(1 for g in gs if g["won"])
        return {"jogos": len(gs), "taxa_vitoria_pct": round(100 * wins / len(gs), 1)}

    return {"azul": side_block(azul), "vermelho": side_block(vermelho)}


def build_recent_form(games, n=10):
    recent = games[:n]
    if not recent:
        return None
    wins = sum(1 for g in recent if g["won"])
    return {"jogos": len(recent), "taxa_vitoria_pct": round(100 * wins / len(recent), 1)}


def head_to_head_from_games(games1, team2_name):
    t2_lower = team2_name.strip().lower()
    confrontos = [g for g in games1 if g["opponent"].strip().lower() == t2_lower]
    if not confrontos:
        return None
    wins1 = sum(1 for g in confrontos if g["won"])
    return {
        "jogos": len(confrontos),
        "vitorias_time1": wins1,
        "vitorias_time2": len(confrontos) - wins1,
        "ultimos_resultados": [
            {"data": g["date"], "vencedor": "time1" if g["won"] else "time2"} for g in confrontos[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Mercados "por jogo", no estilo das abas do gol.gg (Win Rate, First Blood,
# First Tower, First Dragon, First Herald, First Nashor, Most Kills, Total
# Kills/Towers/Dragons/Nashors/Inhibitors, Game Time). Como agora os dados
# de first blood/tower/dragon/herald/baron vêm jogo a jogo (não só a média
# geral), TODOS os mercados abaixo ganham Overall + lado azul/vermelho +
# Recent Form + Past Faceoffs completos.
# ---------------------------------------------------------------------------

GAME_METRICS = [
    {"key": "win", "label": "Win Rate", "type": "rate"},
    {"key": "first_blood", "label": "First Blood", "type": "rate"},
    {"key": "first_tower", "label": "First Tower", "type": "rate"},
    {"key": "first_dragon", "label": "First Dragon", "type": "rate"},
    {"key": "first_herald", "label": "First Herald", "type": "rate"},
    {"key": "first_baron", "label": "First Nashor", "type": "rate"},
    {"key": "most_kills", "label": "Kill Handicap (margem)", "type": "avg", "signed": True},
    {"key": "kills_avg", "label": "Total Kills", "type": "avg"},
    {"key": "kills10_avg", "label": "Total Kills até 10 min", "type": "avg", "parent": "kills_avg"},
    {"key": "kills15_avg", "label": "Total Kills até 15 min", "type": "avg", "parent": "kills_avg"},
    {"key": "towers_avg", "label": "Total Towers", "type": "avg"},
    {"key": "dragons_avg", "label": "Total Dragons", "type": "avg"},
    {"key": "barons_avg", "label": "Total Nashors", "type": "avg"},
    {"key": "inhibitors_avg", "label": "Total Inhibitors", "type": "avg"},
    {"key": "gamelength_avg", "label": "Game Time", "type": "avg"},
]


def _game_metric_value(g, key):
    return {
        "win": 1 if g["won"] else 0,
        "first_blood": g["first_blood"],
        "first_tower": g["first_tower"],
        "first_dragon": g["first_dragon"],
        "first_herald": g["first_herald"],
        "first_baron": g["first_baron"],
        # Margem de kills (handicap): positivo = o time ganhou de X kills,
        # negativo = perdeu de X kills. É esse número que diz qual linha de
        # handicap (ex: -4.5 kills) teria batido naquele jogo.
        "most_kills": g["kills_for"] - g["kills_against"],
        # Totais de MAPA (os dois times somados) — o que decide over/under
        # nos mercados de "Total Kills/Towers/Dragons/Nashors/Inibidores"
        # da bet365, não só o que aquele time fez sozinho.
        "kills_avg": g["kills_total"],
        "kills10_avg": g["kills10_total"],
        "kills15_avg": g["kills15_total"],
        "towers_avg": g["towers_total"],
        "dragons_avg": g["dragons_total"],
        "barons_avg": g["barons_total"],
        "inhibitors_avg": g["inhibitors_total"],
        "gamelength_avg": g["game_length_min"],
    }.get(key)


def _summarize_metric(values, is_rate):
    values = [v for v in values if v is not None]
    if not values:
        return None
    if is_rate:
        return {"pct": round(100 * sum(values) / len(values), 1), "jogos": len(values)}
    return {"media": round(sum(values) / len(values), 2), "jogos": len(values)}


def build_metric_block(games, metric_key, is_rate, h2h_games=None):
    def val(g):
        return _game_metric_value(g, metric_key)

    def seq(gs, n):
        out = []
        for g in gs:
            v = val(g)
            if v is None:
                continue
            out.append({"data": g["date"], "adversario": g["opponent"], "valor": v})
            if len(out) >= n:
                break
        return out

    azul = [g for g in games if g["side"] == "azul"]
    vermelho = [g for g in games if g["side"] == "vermelho"]

    block = {
        "overall": _summarize_metric([val(g) for g in games], is_rate),
        "overall_azul": _summarize_metric([val(g) for g in azul], is_rate),
        "overall_vermelho": _summarize_metric([val(g) for g in vermelho], is_rate),
        "recent_5": _summarize_metric([val(g) for g in games[:5]], is_rate),
        "recent_10": _summarize_metric([val(g) for g in games[:10]], is_rate),
        "recent_5_seq": seq(games, 5),
        "recent_10_seq": seq(games, 10),
    }

    if h2h_games is not None:
        block["confronto_direto"] = {
            "summary": _summarize_metric([val(g) for g in h2h_games], is_rate),
            "seq": seq(h2h_games, 15),
        }
    else:
        block["confronto_direto"] = None

    return block


def build_all_metrics(games, h2h_games):
    return {m["key"]: build_metric_block(games, m["key"], m["type"] == "rate", h2h_games) for m in GAME_METRICS}


MARKET_KEY_MAP = {
    "kills": "kills_total",
    "towers": "towers_total",
    "dragons": "dragons_total",
    "barons": "barons_total",
    "inhibitors": "inhibitors_total",
}

THRESHOLDS = {
    "kills": [22.5, 24.5, 26.5, 28.5, 30.5],
    "towers": [9.5, 10.5, 11.5, 12.5, 13.5],
    "dragons": [3.5, 4.5, 5.5],
    "barons": [0.5, 1.5],
    "inhibitors": [0.5, 1.5],
}


def build_tournament_table(tournament_id):
    teams = teams_in_tournament(tournament_id)
    table = []
    for team in teams:
        games = team_games(team, tournament_id=tournament_id)
        summary = build_summary(games)
        if not summary:
            continue
        limiares = {}
        for mercado, key in MARKET_KEY_MAP.items():
            limiares[mercado] = {str(l): hit_rate_over(games, key, l) for l in THRESHOLDS[mercado]}
        table.append({
            "time": team,
            "resumo": summary,
            "limiares": limiares,
            "primeiras_jogadas": {
                "jogos": len(games),
                "first_blood_pct": _pct(games, "first_blood"),
                "first_tower_pct": _pct(games, "first_tower"),
                "first_dragon_pct": _pct(games, "first_dragon"),
                "first_herald_pct": _pct(games, "first_herald"),
                "first_baron_pct": _pct(games, "first_baron"),
            },
        })
    table.sort(key=lambda r: r["resumo"]["taxa_vitoria_pct"], reverse=True)
    return table


def _pct(games, key):
    vals = [g[key] for g in games if g[key] is not None]
    if not vals:
        return None
    return round(100 * sum(vals) / len(vals), 1)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/csv-status")
def api_csv_status():
    return jsonify(csv_status())


@app.route("/api/years")
def api_years():
    status = csv_status()
    if not status["disponivel"]:
        return jsonify([])
    return jsonify(status["anos_disponiveis"])


@app.route("/api/tournaments")
def api_tournaments():
    year = request.args.get("year", "").strip()
    if not year:
        return jsonify({"erro": "Informe o parâmetro 'year'"}), 400
    status = csv_status()
    if not status["disponivel"]:
        return jsonify({"erro": "CSV da Oracle's Elixir não encontrado. Veja data/LEIA-ME.txt"}), 404
    return jsonify(tournaments_for_year(year))


@app.route("/api/teams-in-tournament")
def api_teams_in_tournament():
    tid = request.args.get("tournament", "").strip()
    if not tid:
        return jsonify({"erro": "Informe o parâmetro 'tournament'"}), 400
    teams = teams_in_tournament(tid)
    if not teams:
        return jsonify({"erro": "Nenhum time encontrado para esse campeonato."}), 404
    return jsonify(teams)


@app.route("/api/tournament-table")
def api_tournament_table():
    tid = request.args.get("tournament", "").strip()
    if not tid:
        return jsonify({"erro": "Informe o parâmetro 'tournament'"}), 400
    table = build_tournament_table(tid)
    if not table:
        return jsonify({"erro": "Nenhum dado de jogo encontrado pra esse campeonato."}), 404
    return jsonify({"limiares_disponiveis": THRESHOLDS, "times": table})


# ---------------------------------------------------------------------------
# "Game Time LIVE" — duração estimada a partir de um draft (10 campeões)
# ---------------------------------------------------------------------------

def champion_list():
    data = _load_games()
    return sorted(data["by_champion"].keys())


def _champion_avg(picks):
    if not picks:
        return None
    return {
        "jogos": len(picks),
        "media_duracao_min": round(sum(p["gamelength_min"] for p in picks) / len(picks), 1),
    }


def champion_pick_stats(champion, team):
    data = _load_games()
    global_stats = _champion_avg(data["by_champion"].get(champion, []))
    team_stats = _champion_avg(data["by_champion_team"].get((champion, team), []))
    # Usa a média específica do time com esse campeão quando ele já jogou
    # com ele antes; senão cai pra média geral do campeão (com qualquer time).
    if team_stats:
        media_usada, fonte = team_stats["media_duracao_min"], "time"
    elif global_stats:
        media_usada, fonte = global_stats["media_duracao_min"], "geral"
    else:
        media_usada, fonte = None, None
    return {
        "campeao": champion, "time": team,
        "geral": global_stats, "do_time": team_stats,
        "media_usada": media_usada, "fonte_usada": fonte,
    }


@app.route("/api/champions")
def api_champions():
    return jsonify(champion_list())


@app.route("/api/draft-time", methods=["POST"])
def api_draft_time():
    body = request.get_json(force=True, silent=True) or {}
    team1 = (body.get("team1") or "").strip()
    team2 = (body.get("team2") or "").strip()
    champs1 = [c.strip() for c in (body.get("champions_team1") or []) if c and c.strip()]
    champs2 = [c.strip() for c in (body.get("champions_team2") or []) if c and c.strip()]

    if not team1 or not team2 or not champs1 or not champs2:
        return jsonify({"erro": "Informe 'team1', 'team2', 'champions_team1' e 'champions_team2'"}), 400

    picks = []
    for c in champs1:
        picks.append(champion_pick_stats(c, team1))
    for c in champs2:
        picks.append(champion_pick_stats(c, team2))

    usaveis = [p["media_usada"] for p in picks if p["media_usada"] is not None]
    previsao = round(sum(usaveis) / len(usaveis), 1) if usaveis else None

    return jsonify({
        "picks": picks,
        "campeoes_sem_dado": [p["campeao"] for p in picks if p["media_usada"] is None],
        "duracao_prevista_min": previsao,
        "baseado_em": len(usaveis),
        "de_total": len(picks),
    })


# ---------------------------------------------------------------------------
# "Linha ao vivo" de Total Kills — dado o minuto atual (+ placar de kills e
# diferença de ouro), estima qual seria a linha "justa" de kills até aquele
# momento, e projeta o total final da partida no ritmo atual.
# ---------------------------------------------------------------------------

def _avg(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def build_kill_pace_anchors(games):
    """Monta pontos (minuto, kills_totais_esperados_até_ali) a partir do
    histórico: 0min=0 kills, ~10min, ~15min, e duração média = total médio
    de kills do jogo inteiro. Só usa os pontos que o dataset realmente tem."""
    anchors = [(0.0, 0.0)]
    k10 = _avg([g["kills10_total"] for g in games])
    if k10 is not None:
        anchors.append((10.0, k10))
    k15 = _avg([g["kills15_total"] for g in games])
    if k15 is not None:
        anchors.append((15.0, k15))
    avg_length = _avg([g["game_length_min"] for g in games])
    avg_total = _avg([g["kills_total"] for g in games])
    if avg_length and avg_total is not None:
        anchors.append((avg_length, avg_total))
    anchors.sort(key=lambda a: a[0])
    # remove pontos duplicados/inconsistentes (tempo não pode repetir)
    dedup = []
    for t, v in anchors:
        if dedup and abs(dedup[-1][0] - t) < 0.01:
            continue
        dedup.append((t, v))
    return dedup


def interpolate_anchors(anchors, minuto):
    if not anchors:
        return None
    if minuto <= anchors[0][0]:
        return anchors[0][1]
    if minuto >= anchors[-1][0]:
        # extrapola linearmente com o ritmo do último trecho conhecido
        if len(anchors) < 2:
            return anchors[-1][1]
        (t0, v0), (t1, v1) = anchors[-2], anchors[-1]
        if t1 == t0:
            return v1
        ritmo = (v1 - v0) / (t1 - t0)
        return max(0.0, v1 + ritmo * (minuto - t1))
    for i in range(len(anchors) - 1):
        t0, v0 = anchors[i]
        t1, v1 = anchors[i + 1]
        if t0 <= minuto <= t1:
            if t1 == t0:
                return v0
            frac = (minuto - t0) / (t1 - t0)
            return v0 + (v1 - v0) * frac
    return anchors[-1][1]


def avg_golddiff_abs_near(games, minuto):
    """Média do |diferença de ouro| histórica no checkpoint mais próximo
    (10 ou 15 min) disponível, só pra dar contexto sobre se o jogo atual
    está mais ou menos decidido que o normal nesse momento."""
    key = "golddiff10" if minuto <= 12.5 else "golddiff15"
    vals = [abs(g[key]) for g in games if g.get(key) is not None]
    return round(_avg(vals), 0) if vals else None


def champion_kill_pace(champion):
    data = _load_games()
    picks = [p for p in data["by_champion"].get(champion, []) if p.get("kills_total_da_partida") is not None]
    if not picks:
        return None
    return {
        "jogos": len(picks),
        "media_kills_partida": round(sum(p["kills_total_da_partida"] for p in picks) / len(picks), 1),
    }


def match_team_name(nome_api):
    """Tenta achar, no nosso dataset (Oracle's Elixir), o nome de time que
    corresponde ao nome que veio da API ao vivo da lolesports (podem vir
    escritos de forma um pouco diferente)."""
    if not nome_api:
        return None
    data = _load_games()
    nomes = list(data["by_team"].keys())
    alvo = nome_api.strip().lower()
    for n in nomes:
        if n.lower() == alvo:
            return n
    for n in nomes:
        if alvo in n.lower() or n.lower() in alvo:
            return n
    return None


@app.route("/api/lol-live/matches")
def api_lol_live_matches():
    try:
        matches = lol_live.get_live_matches()
    except Exception as e:
        return jsonify({"erro": f"Falha ao consultar a API ao vivo da lolesports: {e}"}), 502
    for m in matches:
        m["time1_no_dataset"] = match_team_name(m["time1"])
        m["time2_no_dataset"] = match_team_name(m["time2"])
    return jsonify(matches)


@app.route("/api/lol-live/state")
def api_lol_live_state():
    game_id = request.args.get("gameId", "").strip()
    if not game_id:
        return jsonify({"erro": "Informe 'gameId'"}), 400
    try:
        estado = lol_live.get_live_game_state(game_id)
    except Exception as e:
        return jsonify({"erro": f"Falha ao consultar o estado ao vivo: {e}"}), 502
    return jsonify(estado)


@app.route("/api/live-kill-line", methods=["POST"])
def api_live_kill_line():
    body = request.get_json(force=True, silent=True) or {}
    team1 = (body.get("team1") or "").strip()
    team2 = (body.get("team2") or "").strip()
    minuto = to_float(body.get("minuto"), None)
    kills_t1 = to_float(body.get("kills_time1"), None)
    kills_t2 = to_float(body.get("kills_time2"), None)
    diferenca_ouro = to_float(body.get("diferenca_ouro"), None)
    champs1 = [c.strip() for c in (body.get("champions_team1") or []) if c and c.strip()]
    champs2 = [c.strip() for c in (body.get("champions_team2") or []) if c and c.strip()]

    if not team1 or not team2 or minuto is None:
        return jsonify({"erro": "Informe 'team1', 'team2' e 'minuto'"}), 400

    games1 = team_games(team1)
    games2 = team_games(team2)
    h2h = [g for g in games1 if g["opponent"].strip().lower() == team2.strip().lower()]
    # prioriza o confronto direto se tiver amostra razoável; senão usa o
    # histórico geral dos dois times somado.
    base_games = h2h if len(h2h) >= 5 else (games1 + games2)

    anchors = build_kill_pace_anchors(base_games)
    if len(anchors) < 2:
        return jsonify({"erro": "Histórico insuficiente pra esses times (falta killsat10/killsat15 no CSV)."}), 404

    linha_base = _avg([g["kills_total"] for g in base_games])  # "linha" que a casa abriria no pré-jogo
    avg_length = _avg([g["game_length_min"] for g in base_games])

    # 1) Ajuste pela composição (5 campeões de cada time): compara o ritmo
    # médio de kills desses 10 campeões (em qualquer time/jogo) com a média
    # do confronto entre esses 2 times, e escala a curva toda por isso.
    composicao_info = []
    for c in champs1 + champs2:
        stats = champion_kill_pace(c)
        composicao_info.append({"campeao": c, **(stats or {"jogos": 0, "media_kills_partida": None})})
    usaveis_comp = [p["media_kills_partida"] for p in composicao_info if p.get("jogos", 0) >= 3 and p.get("media_kills_partida") is not None]
    composicao_ratio = None
    if usaveis_comp and linha_base:
        media_comp = sum(usaveis_comp) / len(usaveis_comp)
        composicao_ratio = max(0.7, min(1.3, media_comp / linha_base))
        anchors = [(t, v * composicao_ratio) for t, v in anchors]

    linha_justa = linha_base * composicao_ratio if (linha_base and composicao_ratio) else linha_base

    media_ouro_hist = avg_golddiff_abs_near(base_games, minuto)

    resultado = {
        "amostra": "confronto direto" if base_games is h2h else "histórico geral dos 2 times",
        "jogos_na_amostra": len(base_games),
        "minuto": minuto,
        "linha_base_pre_jogo": round(linha_base, 1) if linha_base else None,
        "duracao_media_historica_min": round(avg_length, 1) if avg_length else None,
        "media_ouro_diferenca_nesse_momento_historico": media_ouro_hist,
    }
    if composicao_ratio is not None:
        resultado["ajuste_por_composicao_pct"] = round((composicao_ratio - 1) * 100, 1)
        resultado["composicao_detalhe"] = composicao_info

    # 2) Ajuste pelo RITMO (se o placar atual foi informado): compara o total
    # de kills até agora com o que era esperado até esse minuto — se o jogo
    # está mais violento ou mais parado que o normal, puxa a linha cheia
    # (não só o "até aqui") pra cima ou pra baixo.
    ajuste_ritmo = 1.0
    if kills_t1 is not None and kills_t2 is not None:
        linha_ate_o_minuto = interpolate_anchors(anchors, minuto)
        total_atual = kills_t1 + kills_t2
        resultado["total_atual_informado"] = total_atual
        resultado["linha_esperada_ate_o_minuto"] = round(linha_ate_o_minuto, 1) if linha_ate_o_minuto is not None else None
        if linha_ate_o_minuto and linha_ate_o_minuto > 0:
            ajuste_ritmo = total_atual / linha_ate_o_minuto
            resultado["ritmo_vs_esperado_pct"] = round((ajuste_ritmo - 1) * 100, 1)

    # 3) Ajuste pela diferença de ouro informada (jogo mais/menos decidido
    # que o normal pra esse momento).
    ajuste_ouro = 1.0
    if diferenca_ouro is not None and media_ouro_hist and media_ouro_hist > 0:
        excesso = (abs(diferenca_ouro) - media_ouro_hist) / media_ouro_hist
        ajuste_ouro = 1 + max(-0.15, min(0.15, excesso * 0.1))  # limitado a ±15%
        resultado["ajuste_por_ouro_pct"] = round((ajuste_ouro - 1) * 100, 1)

    if linha_justa is not None:
        linha_justa_agora = linha_justa * ajuste_ritmo * ajuste_ouro
        resultado["linha_justa_agora"] = round(linha_justa_agora, 1)

    return jsonify(resultado)


@app.route("/api/compare", methods=["POST"])
def api_compare():
    body = request.get_json(force=True, silent=True) or {}
    team1 = (body.get("team1") or "").strip()
    team2 = (body.get("team2") or "").strip()
    limit = int(body.get("limit", 20))
    tournament = (body.get("tournament") or "").strip() or None

    if not team1 or not team2:
        return jsonify({"erro": "Informe 'team1' e 'team2'"}), 400

    games1 = team_games(team1, tournament_id=tournament, limit=limit)
    games2 = team_games(team2, tournament_id=tournament, limit=limit)

    if not games1 or not games2:
        faltando = team1 if not games1 else team2
        return jsonify({"erro": f"Nenhuma partida encontrada para '{faltando}' nesse recorte."}), 404

    # Past Faceoffs usa o HISTÓRICO COMPLETO de cada time (todos os
    # campeonatos, sem limite de "últimos N jogos") — assim um confronto
    # direto que aconteceu antes da janela de jogos analisada continua
    # aparecendo.
    t2_lower = team2.strip().lower()
    t1_lower = team1.strip().lower()
    h2h_games1 = [g for g in team_games(team1) if g["opponent"].strip().lower() == t2_lower]
    h2h_games2 = [g for g in team_games(team2) if g["opponent"].strip().lower() == t1_lower]

    def full_team_block(nome, games, h2h_games):
        limiares = {}
        for mercado, key in MARKET_KEY_MAP.items():
            limiares[mercado] = {str(l): hit_rate_over(games, key, l) for l in THRESHOLDS[mercado]}
        return {
            "nome": nome,
            "resumo": build_summary(games),
            "por_lado": build_side_summary(games),
            "forma_recente_5": build_recent_form(games, 5),
            "forma_recente_10": build_recent_form(games, 10),
            "limiares": limiares,
            "metricas": build_all_metrics(games, h2h_games),
        }

    confronto_direto = head_to_head_from_games(h2h_games1, team2)

    return jsonify({
        "time1": full_team_block(team1, games1, h2h_games1),
        "time2": full_team_block(team2, games2, h2h_games2),
        "limiares_disponiveis": THRESHOLDS,
        "confronto_direto": confronto_direto,
        "mercados_disponiveis": GAME_METRICS,
    })


# ---------------------------------------------------------------------------
# Rotas — Valorant (VCT)
# ---------------------------------------------------------------------------

@app.route("/api/valorant/csv-status")
def api_v_csv_status():
    return jsonify(vdata.v_csv_status())


@app.route("/api/valorant/years")
def api_v_years():
    return jsonify(vdata.v_years())


@app.route("/api/valorant/tournaments")
def api_v_tournaments():
    year = request.args.get("year", "").strip()
    if not year:
        return jsonify({"erro": "Informe o parâmetro 'year'"}), 400
    return jsonify(vdata.v_tournaments_for_year(year))


@app.route("/api/valorant/teams-in-tournament")
def api_v_teams():
    tid = request.args.get("tournament", "").strip()
    if not tid:
        return jsonify({"erro": "Informe o parâmetro 'tournament'"}), 400
    teams = vdata.v_teams_in_tournament(tid)
    if not teams:
        return jsonify({"erro": "Nenhum time encontrado pra esse campeonato."}), 404
    return jsonify(teams)


@app.route("/api/valorant/maps")
def api_v_maps():
    team1 = request.args.get("team1", "").strip()
    team2 = request.args.get("team2", "").strip()
    tid = request.args.get("tournament", "").strip() or None
    if not team1 or not team2:
        return jsonify({"erro": "Informe 'team1' e 'team2'"}), 400
    return jsonify(vdata.v_maps_available(team1, team2, tournament_id=tid))


@app.route("/api/valorant/compare", methods=["POST"])
def api_v_compare():
    body = request.get_json(force=True, silent=True) or {}
    team1 = (body.get("team1") or "").strip()
    team2 = (body.get("team2") or "").strip()
    limit = int(body.get("limit", 20))
    tournament = (body.get("tournament") or "").strip() or None

    if not team1 or not team2:
        return jsonify({"erro": "Informe 'team1' e 'team2'"}), 400

    games1_disp = vdata.v_team_games(team1, tournament_id=tournament, limit=limit)
    games2_disp = vdata.v_team_games(team2, tournament_id=tournament, limit=limit)
    if not games1_disp or not games2_disp:
        faltando = team1 if not games1_disp else team2
        return jsonify({"erro": f"Nenhum mapa encontrado para '{faltando}' nesse recorte."}), 404

    games1_full = vdata.v_team_games(team1)
    games2_full = vdata.v_team_games(team2)

    def block(nome, games_disp, games_full, opponent):
        return {
            "nome": nome,
            "overall": vdata.v_win_summary(games_disp),
            "recent_5": vdata.v_recent_form(games_disp, 5),
            "recent_10": vdata.v_recent_form(games_disp, 10),
            "confronto_direto": vdata.v_head_to_head(games_full, opponent),
        }

    return jsonify({
        "time1": block(team1, games1_disp, games1_full, team2),
        "time2": block(team2, games2_disp, games2_full, team1),
    })


@app.route("/api/valorant/map-detail")
def api_v_map_detail():
    team1 = request.args.get("team1", "").strip()
    team2 = request.args.get("team2", "").strip()
    mapa = request.args.get("map", "").strip()
    tid = request.args.get("tournament", "").strip() or None
    if not team1 or not team2 or not mapa:
        return jsonify({"erro": "Informe 'team1', 'team2' e 'map'"}), 400
    d1 = vdata.v_map_detail(team1, team2, mapa, tournament_id=tid)
    d2 = vdata.v_map_detail(team2, team1, mapa, tournament_id=tid)
    return jsonify({"time1": d1, "time2": d2})


# ---------------------------------------------------------------------------
# Rotas — Valorant "stats ao vivo" (importado de CSV manual, ex: vlr.gg)
# ---------------------------------------------------------------------------

@app.route("/api/valorant-live/status")
def api_vlive_status():
    return jsonify(vlive.live_status())


@app.route("/api/valorant-live/rows")
def api_vlive_rows():
    campeonato = request.args.get("campeonato") or None
    mapa = request.args.get("mapa") or None
    rows = vlive.live_rows(campeonato=campeonato, mapa=mapa)
    return jsonify(rows)


@app.route("/api/valorant-live/teams")
def api_vlive_teams():
    campeonato = request.args.get("campeonato", "").strip()
    if not campeonato:
        return jsonify({"erro": "Informe 'campeonato'"}), 400
    return jsonify(vlive.live_teams_in_campeonato(campeonato))


@app.route("/api/valorant-live/maps")
def api_vlive_maps():
    campeonato = request.args.get("campeonato", "").strip()
    team1 = request.args.get("team1", "").strip()
    team2 = request.args.get("team2", "").strip()
    if not campeonato or not team1 or not team2:
        return jsonify({"erro": "Informe 'campeonato', 'team1' e 'team2'"}), 400
    return jsonify(vlive.live_maps_for_teams(campeonato, team1, team2))


@app.route("/api/valorant-live/map-detail")
def api_vlive_map_detail():
    campeonato = request.args.get("campeonato", "").strip()
    team1 = request.args.get("team1", "").strip()
    team2 = request.args.get("team2", "").strip()
    mapa = request.args.get("map", "").strip()
    if not campeonato or not team1 or not team2 or not mapa:
        return jsonify({"erro": "Informe 'campeonato', 'team1', 'team2' e 'map'"}), 400
    return jsonify({
        "time1": vlive.live_team_map_detail(campeonato, team1, mapa),
        "time2": vlive.live_team_map_detail(campeonato, team2, mapa),
    })


if __name__ == "__main__":
    print("Rodando em http://localhost:5000")
    app.run(debug=True, port=5000, threaded=True)
