"""
Módulo de Análise e Comparação de Confrontos no Valorant.
Lê o CSV de estatísticas ao vivo e fornece funções para comparação entre dois times,
além de uma interface visual pronta para Streamlit.
"""

import csv
import glob
import os
import pandas as pd
import streamlit as st

_DATA_DIR_LIVE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "valorant_live"
)
os.makedirs(_DATA_DIR_LIVE, exist_ok=True)

_cache = {"mtimes": None, "df": pd.DataFrame()}


def _files():
    return sorted(glob.glob(os.path.join(_DATA_DIR_LIVE, "*.csv")))


def _to_float(v, default=0.0):
    if v is None:
        return default
    s = str(v).strip().replace("%", "")
    if s in ("", "-", "N/A"):
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _clean(s):
    return " ".join((s or "").replace("\t", " ").split()).strip()


def carregar_dados():
    """Lê todos os CSVs da pasta data/valorant_live e retorna um DataFrame limpo."""
    paths = _files()
    if not paths:
        return pd.DataFrame()

    mtimes = tuple(sorted((p, os.path.getmtime(p)) for p in paths))
    if _cache["mtimes"] == mtimes and not _cache["df"].empty:
        return _cache["df"]

    rows = []
    for path in paths:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            try:
                header = [h.strip() for h in next(reader)]
            except StopIteration:
                continue

            num_cols = len(header)

            for r in reader:
                if len(r) < 5:
                    continue

                if num_cols < 14:  # Formato Simplificado (8 Colunas)
                    campeonato = _clean(r[0])
                    data_partida = _clean(r[1])
                    mapa = _clean(r[2])
                    jogador = _clean(r[3])
                    time_tag = _clean(r[4])
                    personagem = _clean(r[5])
                    kills = _to_float(r[6])
                    mortes = _to_float(r[7])
                else:  # Formato Legado (14 Colunas)
                    campeonato = _clean(r[1])
                    data_partida = _clean(r[3])
                    mapa = _clean(r[4])
                    jogador_raw = r[5]
                    if "\n" in jogador_raw:
                        jogador, time_tag = jogador_raw.split("\n", 1)
                    else:
                        jogador, time_tag = jogador_raw, r[6] if len(r) > 6 else ""
                    jogador = _clean(jogador)
                    time_tag = _clean(time_tag)
                    personagem = _clean(r[7]) if len(r) > 7 else "Desconhecido"
                    kills = _to_float(r[10]) if len(r) > 10 else 0.0
                    mortes = _to_float(r[11]) if len(r) > 11 else 0.0

                rows.append({
                    "Campeonato": campeonato,
                    "Data": data_partida,
                    "Mapa": mapa,
                    "Jogador": jogador,
                    "Time": time_tag,
                    "Personagem": personagem,
                    "Kills": kills,
                    "Mortes": mortes,
                })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["KD"] = (df["Kills"] / df["Mortes"].replace(0, 1)).round(2)
    _cache.update({"mtimes": mtimes, "df": df})
    return df


def obter_filtros():
    """Retorna a lista de campeonatos, times e mapas disponíveis."""
    df = carregar_dados()
    if df.empty:
        return {"campeonatos": [], "times": [], "mapas": []}

    campeonatos = sorted(df["Campeonato"].unique().tolist())
    times = sorted(df["Time"].unique().tolist())
    mapas = sorted(df["Mapa"].unique().tolist())
    return {"campeonatos": campeonatos, "times": times, "mapas": mapas}


def analisar_time_no_mapa(time_nome, campeonato, mapa=None, limite_mapas=20):
    """Calcula estatísticas agregadas e desempenho dos jogadores de um time."""
    df = carregar_dados()
    if df.empty:
        return None

    # Filtra por campeonato e time
    sub = df[(df["Campeonato"] == campeonato) & (df["Time"] == time_nome)]
    if mapa:
        sub = sub[sub["Mapa"] == mapa]

    if sub.empty:
        return None

    # Limita ao histórico recente de partidas se desejado
    datas_recentes = sub["Data"].unique()[:limite_mapas]
    sub = sub[sub["Data"].isin(datas_recentes)]

    # Agrupamento por Jogador
    stats_jogadores = sub.groupby("Jogador").agg(
        Personagem=("Personagem", lambda x: ", ".join(x.unique())),
        Mapas_Jogados=("Mapa", "count"),
        Kills_Medias=("Kills", lambda x: round(x.mean(), 1)),
        Mortes_Medias=("Mortes", lambda x: round(x.mean(), 1)),
        KD_Medio=("KD", lambda x: round(x.mean(), 2))
    ).reset_index()

    # Totais do Time
    total_mapas = sub["Mapa"].nunique()
    total_kills = sub["Kills"].sum()
    total_mortes = sub["Mortes"].sum()

    return {
        "time": time_nome,
        "mapa": mapa or "Todos os Mapas",
        "total_mapas": total_mapas,
        "total_kills": total_kills,
        "total_mortes": total_mortes,
        "jogadores": stats_jogadores
    }


# ==============================================================================
# INTERFACE GRÁFICA (STREAMLIT)
# ==============================================================================
def renderizar_interface():
    st.title("⚔️ Análise de Confronto — Valorant")

    filtros = obter_filtros()
    if not filtros["campeonatos"]:
        st.warning("Nenhum dado encontrado na pasta `data/valorant_live`. Adicione o arquivo CSV.")
        return

    # Seção 01: Escolha o Campeonato
    st.subheader("01. Escolha o Campeonato")
    campeonato_sel = st.selectbox("Campeonato", filtros["campeonatos"])

    # Filtra times que pertencem ao campeonato selecionado
    df = carregar_dados()
    times_do_champ = sorted(df[df["Campeonato"] == campeonato_sel]["Time"].unique().tolist())

    # Seção 02: Confronto
    st.subheader("02. Confronto")
    col1, col2 = st.columns(2)
    with col1:
        time1 = st.selectbox("Time 1", times_do_champ, index=0 if len(times_do_champ) > 0 else 0)
    with col2:
        idx_t2 = 1 if len(times_do_champ) > 1 else 0
        time2 = st.selectbox("Time 2", times_do_champ, index=idx_t2)

    limite_mapas = st.select_slider(
        "Mapas recentes de cada time a considerar",
        options=[5, 10, 15, 20, 30],
        value=20
    )

    btn_comparar = st.button("COMPARAR TIMES", use_container_width=True)

    if btn_comparar or "comparou" in st.session_state:
        st.session_state["comparou"] = True

        # Seletor de Mapas (Tabs de mapas disponíveis)
        mapas_champ = sorted(df[df["Campeonato"] == campeonato_sel]["Mapa"].unique().tolist())
        mapa_sel = st.radio("Selecione o Mapa para detalhamento:", ["Todos"] + mapas_champ, horizontal=True)

        mapa_filtro = None if mapa_sel == "Todos" else mapa_sel

        # Análise dos Dois Times
        res1 = analisar_time_no_mapa(time1, campeonato_sel, mapa_filtro, limite_mapas)
        res2 = analisar_time_no_mapa(time2, campeonato_sel, mapa_filtro, limite_mapas)

        st.markdown("---")

        # Exibição do Time 1
        if res1:
            st.markdown(f"### {res1['mapa']} — {res1['time']}")
            st.caption(f"**{res1['total_mapas']}** mapa(s) registrado(s) | **{res1['total_kills']}** Abates Totais | **{res1['total_mortes']}** Mortes Totais")
            st.dataframe(res1["jogadores"], use_container_width=True)
        else:
            st.info(f"Sem dados para {time1} no mapa selecionado.")

        # Exibição do Time 2
        if res2:
            st.markdown(f"### {res2['mapa']} — {res2['time']}")
            st.caption(f"**{res2['total_mapas']}** mapa(s) registrado(s) | **{res2['total_kills']}** Abates Totais | **{res2['total_mortes']}** Mortes Totais")
            st.dataframe(res2["jogadores"], use_container_width=True)
        else:
            st.info(f"Sem dados para {time2} no mapa selecionado.")


if __name__ == "__main__":
    renderizar_interface()