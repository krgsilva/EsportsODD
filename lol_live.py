"""
Integração com a API ao vivo do lolesports.com (a mesma que o próprio site
oficial usa por trás pra mostrar as partidas ao vivo — não é scraping, é a
API JSON pública que o front-end deles chama).

Diferente do resto do app (que lê CSVs locais, sem internet), ESSE módulo
faz requisições reais à internet — só é usado na aba "Ao Vivo".

⚠️ Essa é uma API não-documentada oficialmente pela Riot — funciona porque
é a mesma que o site deles usa, mas pode mudar de formato sem aviso. Se
parar de funcionar, é isso que provavelmente aconteceu. O código abaixo
tenta vários nomes de campo possíveis pra cada informação, exatamente por
causa disso.
"""

import requests
from datetime import datetime

ESPORTS_API = "https://esports-api.lolesports.com/persisted/gw"
FEED_API = "https://feed.lolesports.com/livestats/v1"
# Chave pública usada pelo próprio site lolesports.com no navegador de
# qualquer visitante (não é uma credencial secreta nossa).
API_KEY = "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
HEADERS = {"x-api-key": API_KEY}
TIMEOUT = 10


def _first(d, *keys, default=None):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d.get(k)
    return default


def get_live_matches():
    """Lista as partidas de LoL com algum jogo em andamento ou prestes a
    começar agora — cada mapa (game) de cada partida vira uma entrada
    separada, com o estado dele (in_game / unstarted / completed etc)."""
    resp = requests.get(f"{ESPORTS_API}/getLive", params={"hl": "pt-BR"}, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    events = (data.get("data") or {}).get("schedule", {}).get("events", [])

    matches = []
    for ev in events:
        match = ev.get("match") or {}
        teams = match.get("teams") or []
        if len(teams) != 2:
            continue
        games = match.get("games") or []
        for g in games:
            estado = (g.get("state") or "").lower()
            if estado not in ("inprogress", "in_game", "unstarted", "unneeded"):
                continue
            if estado == "unneeded":
                continue
            matches.append({
                "game_id": g.get("id"),
                "liga": (ev.get("league") or {}).get("name"),
                "time1": teams[0].get("name") or teams[0].get("code"),
                "time2": teams[1].get("name") or teams[1].get("code"),
                "placar1": (teams[0].get("result") or {}).get("gameWins"),
                "placar2": (teams[1].get("result") or {}).get("gameWins"),
                "numero_mapa": g.get("number"),
                "estado_mapa": estado,
                "ao_vivo": estado in ("inprogress", "in_game"),
            })
    # jogos ao vivo primeiro
    matches.sort(key=lambda m: (not m["ao_vivo"], m["numero_mapa"] or 0))
    return matches


def _parse_rfc460(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_scoreboard_side(team_frame, team_metadata):
    """Monta a lista de jogadores de um lado (azul ou vermelho),
    cruzando os números ao vivo (kills/cs/gold/vida) com os metadados
    (nome do jogador, campeão) — vêm em lugares separados na API."""
    meta_by_id = {m.get("participantId"): m for m in (team_metadata or [])}
    jogadores = []
    for p in (team_frame.get("participants") or []):
        pid = p.get("participantId")
        meta = meta_by_id.get(pid, {})
        vida = _first(p, "currentHealth")
        vida_max = _first(p, "maxHealth")
        jogadores.append({
            "jogador": _first(meta, "summonerName", "esportsPlayerId", default="?"),
            "campeao": _first(meta, "championId", "championName"),
            "kills": _first(p, "kills", default=0),
            "deaths": _first(p, "deaths", default=0),
            "assists": _first(p, "assists", default=0),
            "cs": _first(p, "creepScore", "cs", default=0),
            "ouro": _first(p, "totalGold", "currentGold", default=0),
            "nivel": _first(p, "level"),
            "vida": vida, "vida_max": vida_max,
            "vida_pct": round(100 * vida / vida_max, 0) if (vida is not None and vida_max) else None,
            "itens": _first(p, "items", default=[]),
        })
    return jogadores


def get_live_game_state(game_id):
    """Busca o estado atual de um jogo ao vivo: minuto, kills, ouro, draft
    (5 campeões de cada lado), objetivos (torres/dragões/barões) e o
    scoreboard completo dos 10 jogadores (campeão, KDA, CS, ouro, vida,
    itens) — pra montar um painel parecido com o do lolesports.com."""
    resultado = {"minuto": None,
                 "kills_time1": None, "kills_time2": None, "diferenca_ouro": None,
                 "champions_team1": [], "champions_team2": [],
                 "objetivos_time1": {}, "objetivos_time2": {},
                 "jogadores_time1": [], "jogadores_time2": []}

    # Sem "startingTime", a API só devolve uma JANELA recente de frames
    # (por isso o minuto de jogo saía quase zero e os números pareciam
    # travados) — pedindo desde bem no passado, ela devolve os frames
    # desde o início real da partida.
    params = {"startingTime": "2020-01-01T00:00:00.000Z"}
    win = requests.get(f"{FEED_API}/window/{game_id}", params=params, headers=HEADERS, timeout=TIMEOUT)
    win.raise_for_status()
    win_data = win.json()
    frames = win_data.get("frames") or []
    if not frames:
        raise RuntimeError("Esse jogo ainda não tem frames ao vivo (pode não ter começado de verdade).")

    primeiro, ultimo = frames[0], frames[-1]
    t0, t1 = _parse_rfc460(primeiro.get("rfc460Timestamp")), _parse_rfc460(ultimo.get("rfc460Timestamp"))
    if t0 and t1:
        resultado["minuto"] = round((t1 - t0).total_seconds() / 60, 1)

    blue = ultimo.get("blueTeam") or {}
    red = ultimo.get("redTeam") or {}
    resultado["kills_time1"] = _first(blue, "totalKills")
    resultado["kills_time2"] = _first(red, "totalKills")
    ouro_azul = _first(blue, "totalGold")
    ouro_vermelho = _first(red, "totalGold")
    if ouro_azul is not None and ouro_vermelho is not None:
        resultado["diferenca_ouro"] = abs(ouro_azul - ouro_vermelho)
        resultado["ouro_time1"] = ouro_azul
        resultado["ouro_time2"] = ouro_vermelho

    def objetivos(side):
        dragões = side.get("dragons") or []
        return {
            "torres": _first(side, "towers", default=0),
            "inibidores": _first(side, "inhibitors", default=0),
            "baroes": _first(side, "barons", default=0),
            "dragoes": len(dragões) if isinstance(dragões, list) else _first(side, "dragons", default=0),
            "arautos": _first(side, "heralds", default=0),
        }
    resultado["objetivos_time1"] = objetivos(blue)
    resultado["objetivos_time2"] = objetivos(red)

    meta = win_data.get("gameMetadata") or {}
    blue_meta = _first(meta, "blueTeamMetadata", default={}).get("participantMetadata", []) if isinstance(meta.get("blueTeamMetadata"), dict) else []
    red_meta = _first(meta, "redTeamMetadata", default={}).get("participantMetadata", []) if isinstance(meta.get("redTeamMetadata"), dict) else []
    resultado["jogadores_time1"] = _build_scoreboard_side(blue, blue_meta)
    resultado["jogadores_time2"] = _build_scoreboard_side(red, red_meta)
    resultado["champions_team1"] = [j["campeao"] for j in resultado["jogadores_time1"] if j.get("campeao")]
    resultado["champions_team2"] = [j["campeao"] for j in resultado["jogadores_time2"] if j.get("campeao")]

    # Se o draft não veio junto no "window" (varia por partida), busca no
    # "details" como reforço.
    if not resultado["champions_team1"] or not resultado["champions_team2"]:
        try:
            det = requests.get(f"{FEED_API}/details/{game_id}", headers=HEADERS, timeout=TIMEOUT)
            det.raise_for_status()
            det_frames = (det.json().get("frames") or [])
            if det_frames:
                participants = det_frames[-1].get("participants") or []
                blue_champs = [_first(p, "championName", "champion") for p in participants if p.get("teamId") == 100]
                red_champs = [_first(p, "championName", "champion") for p in participants if p.get("teamId") == 200]
                if not resultado["champions_team1"]:
                    resultado["champions_team1"] = [c for c in blue_champs if c]
                if not resultado["champions_team2"]:
                    resultado["champions_team2"] = [c for c in red_champs if c]
        except requests.exceptions.RequestException:
            pass

    return resultado
