import csv
import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Lista completa de todos os mapas do Valorant
MAPAS = [
    "ascent", "bind", "breeze", "corrode", "fracture", 
    "haven", "icebox", "lotus", "pearl", "split", 
    "summit", "sunset", "abyss"
]

def obter_eventos_em_andamento():
    """Busca dinamicamente todos os campeonatos na seção ONGOING EVENTS."""
    url_vlr = "https://www.vlr.gg/"
    eventos = []

    try:
        res = requests.get(url_vlr, headers=HEADERS)
        if res.status_code != 200:
            print(f"Erro ao acessar {url_vlr}: Status {res.status_code}")
            return eventos

        soup = BeautifulSoup(res.content, "html.parser")
        
        sidebar_modules = soup.find_all("div", class_="module") or soup.find_all("div", class_="wf-card")
        
        target_container = None
        for mod in sidebar_modules:
            header_text = mod.text.upper()
            if "ONGOING EVENTS" in header_text or "EVENTS" in header_text:
                target_container = mod
                break

        links_eventos = target_container.find_all("a") if target_container else soup.select("a[href*='/event/']")

        for a in links_eventos:
            href = a.get("href", "")
            if "/event/" in href:
                partes = href.strip("/").split("/")
                if len(partes) >= 2:
                    event_id = partes[1]
                    slug_evento = f"{event_id}/{partes[2]}" if len(partes) > 2 else event_id

                    nome_elem = a.find(class_="event-item-title") or a.find("div", class_="title")
                    nome = nome_elem.text.strip() if nome_elem else a.text.strip().split("\n")[0]

                    dates_elem = a.find(class_="event-item-dates") or a.find("span", class_="dates")
                    datas = dates_elem.text.strip() if dates_elem else "Em Andamento"

                    if not any(e["id"] == event_id for e in eventos):
                        eventos.append({
                            "id": event_id,
                            "nome": nome,
                            "slug": slug_evento,
                            "datas": datas
                        })
                        print(f" Torneio localizado: {nome} ({datas})")

    except Exception as e:
        print(f"Erro ao capturar lista de campeonatos: {e}")

    return eventos


def extrair_estatisticas():
    torneios_ativos = obter_eventos_em_andamento()
    
    if not torneios_ativos:
        print("Nenhum campeonato em andamento localizado no momento.")
        return

    dados_finais = []

    for torneo in torneios_ativos:
        print(f"\nExtraindo dados do torneio: {torneo['nome']}...")
        
        for mapa in MAPAS:
            url_stats = f"https://www.vlr.gg/event/stats/{torneo['slug']}?map={mapa}"
            
            try:
                res = requests.get(url_stats, headers=HEADERS)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.content, "html.parser")
                    tabela = soup.find("table")
                    
                    if tabela:
                        linhas = tabela.find_all("tr")[1:]
                        for linha in linhas:
                            cols = [col.text.strip() for col in linha.find_all("td")]
                            if len(cols) >= 8:
                                data_partida = linha.get("data-date", datetime.now().strftime("%Y-%m-%d"))

                                dados_finais.append({
                                    "Status_Evento": "ONGOING",
                                    "Campeonato": torneo['nome'],
                                    "Periodo_Campeonato": torneo['datas'],
                                    "Data_Partida": data_partida,
                                    "Mapa": mapa.capitalize(),
                                    "Jogador": cols[0],
                                    "Time": cols[1],
                                    "Agente": cols[2],
                                    "Rating": cols[3],
                                    "ACS": cols[4],
                                    "Kills": cols[5],
                                    "Mortes": cols[6],
                                    "Assistencias": cols[7],
                                    "ADR": cols[8] if len(cols) > 8 else "0"
                                })
            except Exception as e:
                print(f"Erro na requisição para o mapa {mapa}: {e}")

    arquivo_csv = "estatisticas_todos_os_mapas_vct.csv"
    if dados_finais:
        chaves = dados_finais[0].keys()
        with open(arquivo_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=chaves)
            writer.writeheader()
            writer.writerows(dados_finais)
        print(f"\n Base de dados com TODOS os mapas salva em '{arquivo_csv}' ({len(dados_finais)} registros)!")

if __name__ == "__main__":
    extrair_estatisticas()