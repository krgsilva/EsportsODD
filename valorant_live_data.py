"""
Estatísticas "ao vivo" de Valorant, importadas de um CSV que o usuário
mesmo copia/exporta periodicamente (ex: de uma tabela de stats do
vlr.gg) e salva em data/valorant_live/. O app relê o arquivo sempre que
ele muda — é só substituir o arquivo por uma versão mais nova.

O app reconhece automaticamente 2 formatos (pelo número de colunas do
cabeçalho), já que os exports que chegam nunca batem com os nomes de
coluna declarados de verdade (efeito colateral de copiar tabelas de
sites com células de várias linhas):

FORMATO A (14 colunas): Status_Evento,Campeonato,Periodo_Campeonato,
Data_Partida,Mapa,Jogador,Time,Agente,Rating,ACS,Kills,Mortes,
Assistencias,ADR — mas "Jogador" vem com nome+time juntos numa célula só
("Neon\\nLEV"), empurrando tudo depois uma posição pra direita. Confirmado
comparando a faixa de valores de cada coluna com os intervalos reais de
Valorant (rating ~0.4-1.6, ACS ~100-300 etc).

FORMATO B (8 colunas): Campeonato,Data_Partida,Mapa,Jogador,Time,
Personagem,Kills,Mortes — aqui "Campeonato" vem com informação extra
grudada (status, premiação, datas), e "Personagem/Kills/Mortes" na
real são Mapas jogados / ACS / Rating (mesmo tipo de deslocamento,
confirmado do mesmo jeito).

Limitação conhecida: nenhum dos dois formatos traz o nome do agente
jogado de verdade — só (no Formato A) as porcentagens de pick sem saber
qual agente é qual, ou (no Formato B) nada.
"""

import csv
import os
import re
import glob

_DATA_DIR_LIVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "valorant_live")
os.makedirs(_DATA_DIR_LIVE, exist_ok=True)

_cache = {"mtimes": None, "rows": [], "campeonatos": [], "mapas": []}


def _files():
    return sorted(glob.glob(os.path.join(_DATA_DIR_LIVE, "*.csv")))


def _to_float(v, default=None):
    if v is None:
        return default
    s = str(v).strip().replace("%", "")
    if s in ("", "-"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _clean(s):
    return " ".join((s or "").replace("\t", " ").split()).strip()


_STATUS_WORD_RE = re.compile(r"\s+(ongoing|completed|upcoming)\b.*$", re.IGNORECASE)


def _clean_campeonato_com_status_grudado(s):
    """Remove o texto de status/premiação/data que fica grudado no nome
    do campeonato no Formato B (ex: 'VCT 2026: China Stage 2 ongoing
    Status $250,000 Prize Pool Jul 9—Aug 23 Dates Region' -> 'VCT 2026:
    China Stage 2')."""
    s = _clean(s)
    return _STATUS_WORD_RE.sub("", s).strip()


_EMPTY_ROW_TEMPLATE = {
    "status_evento": None, "campeonato": "", "periodo": None, "data": "", "mapa": "",
    "jogador": "", "time": "", "agentes_pick_raw": None,
    "mapas_jogados": None, "rounds_jogados": None, "rating": None, "acs": None,
    "kd": None, "kast_pct": None, "adr": None,
}


def _parse_row_formato_a(r):
    jogador_raw = r[5]
    if "\n" in jogador_raw:
        nome, time_tag = jogador_raw.split("\n", 1)
    else:
        nome, time_tag = jogador_raw, ""
    row = dict(_EMPTY_ROW_TEMPLATE)
    row.update({
        "status_evento": _clean(r[0]),
        "campeonato": _clean(r[1]),
        "periodo": _clean(r[2]),
        "data": _clean(r[3]),
        "mapa": _clean(r[4]),
        "jogador": _clean(nome),
        "time": _clean(time_tag),
        "agentes_pick_raw": _clean(r[6]),
        "mapas_jogados": _to_float(r[7]),
        "rounds_jogados": _to_float(r[8]),
        "rating": _to_float(r[9]),
        "acs": _to_float(r[10]),
        "kd": _to_float(r[11]),
        "kast_pct": _to_float(r[12]),
        "adr": _to_float(r[13]),
    })
    return row


def _parse_row_formato_b(r):
    row = dict(_EMPTY_ROW_TEMPLATE)
    row.update({
        "campeonato": _clean_campeonato_com_status_grudado(r[0]),
        "data": _clean(r[1]),
        "mapa": _clean(r[2]),
        "jogador": _clean(r[3]),
        "time": _clean(r[4]),
        "mapas_jogados": _to_float(r[5]),
        "acs": _to_float(r[6]),
        "rating": _to_float(r[7]),
    })
    return row


def _load():
    paths = _files()
    if not paths:
        result = {"mtimes": None, "rows": [], "campeonatos": [], "mapas": []}
        _cache.update(result)
        return _cache

    mtimes = tuple(sorted((p, os.path.getmtime(p)) for p in paths))
    if _cache["mtimes"] == mtimes:
        return _cache

    rows = []
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                continue
            n = len(header)
            if n >= 14:
                parse_fn, min_cols = _parse_row_formato_a, 14
            elif n >= 8:
                parse_fn, min_cols = _parse_row_formato_b, 8
            else:
                continue  # formato não reconhecido, pula esse arquivo
            for r in reader:
                if len(r) < min_cols:
                    continue
                row = parse_fn(r)
                if row["jogador"] and row["campeonato"]:
                    rows.append(row)

    campeonatos = sorted({r["campeonato"] for r in rows if r["campeonato"]})
    mapas = sorted({r["mapa"] for r in rows if r["mapa"]})
    result = {"mtimes": mtimes, "rows": rows, "campeonatos": campeonatos, "mapas": mapas}
    _cache.update(result)
    return _cache


def live_status():
    data = _load()
    return {
        "disponivel": bool(data["rows"]),
        "linhas": len(data["rows"]),
        "campeonatos": data["campeonatos"],
        "mapas": data["mapas"],
        "arquivos": [os.path.basename(p) for p in _files()],
    }


def live_rows(campeonato=None, mapa=None, time=None):
    data = _load()
    rows = data["rows"]
    if campeonato:
        rows = [r for r in rows if r["campeonato"] == campeonato]
    if mapa:
        rows = [r for r in rows if r["mapa"] == mapa]
    if time:
        rows = [r for r in rows if r["time"].strip().lower() == time.strip().lower()]
    return rows


def live_teams_in_campeonato(campeonato):
    rows = live_rows(campeonato=campeonato)
    return sorted({r["time"] for r in rows if r["time"]})


def live_maps_for_teams(campeonato, team1, team2):
    rows = live_rows(campeonato=campeonato)
    t1, t2 = team1.strip().lower(), team2.strip().lower()
    mapas = {r["mapa"] for r in rows if r["time"].strip().lower() in (t1, t2) and r["mapa"]}
    return sorted(mapas)


def live_team_map_detail(campeonato, time, mapa):
    rows = live_rows(campeonato=campeonato, mapa=mapa, time=time)
    if not rows:
        return None
    rows = sorted(rows, key=lambda r: (r["rating"] if r["rating"] is not None else -1), reverse=True)
    return {"time": time, "mapa": mapa, "campeonato": campeonato, "jogadores": rows}
