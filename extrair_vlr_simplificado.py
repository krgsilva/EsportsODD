import csv
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

# Lista com todos os mapas do Valorant
MAPAS = [
    "ascent", "bind", "breeze", "corrode", "fracture", 
    "haven", "icebox", "lotus", "pearl", "split", 
    "summit", "sunset", "abyss"
]

def obter_eventos_em_andamento():
    """Busca campeonatos diretamente na aba de eventos da VLR.gg"""
    urls_busca = [
        "https://www.vlr.gg/events",
        "https://www.vlr.gg/"
    ]
    eventos = []

    for url in urls_busca:
        try:
            res = requests.get(url, headers=HEADERS, timeout=12)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.content, "html.parser")
            
            # Encontra todos os links contendo /event/
            for a in soup.find_all("a", href=True):
                href = a["href"]
                
                # Exemplo de URL esperada: /event/2096/vct-2026-americas-stage-2
                match = re.search(r'/event/(\d+)/?([^/#\?]+)?', href)
                if match:
                    event_id = match.group(1)
                    slug_part = match.group(2) if match.group(2) else ""
                    
                    # Evita links de subpáginas como /event/stats/ ou /event/matches/
                    if slug_part in ["stats", "matches", "agents", "overview"]:
                        continue

                    slug_completo = f"{event_id}/{slug_part}" if slug_part else event_id

                    # Pega o nome do evento
                    nome = a.text.strip().replace('\n', ' ')
                    nome = re.sub(r'\s+', ' ', nome)
                    
                    if not nome or len(nome) < 3:
                        nome = f"Evento {event_id}"

                    # Adiciona se ainda não estiver na lista
                    if not any(e["id"] == event_id for e in eventos):
                        eventos.append({
                            "id": event_id,
                            "nome": nome,
                            "slug": slug_completo
                        })
                        print(f"Torneio localizado: {nome} (ID: {event_id})")

            if eventos:
                break # Se encontrou eventos na primeira URL, não precisa ir para a próxima

        except Exception as e:
            print(f"Erro ao acessar {url}: {e}")

    return eventos


def extrair_estatisticas_simplificadas():
    print("Buscando campeonatos no VLR.gg...")
    torneios = obter_eventos_em_andamento()
    
    if not torneios:
        print("\nNenhum evento localizado automaticamente. Verifique sua conexão com a internet.")
        return

    print(f"\nTotal de torneios encontrados: {len(torneios)}")
    dados_simplificados = []

    for torneo in torneios:
        print(f"\nExtraindo estatísticas do torneio: {torneo['nome']}...")
        
        for mapa in MAPAS:
            url_stats = f"https://www.vlr.gg/event/stats/{torneo['slug']}?map={mapa}"
            
            try:
                res = requests.get(url_stats, headers=HEADERS, timeout=10)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.content, "html.parser")
                    tabela = soup.find("table")
                    
                    if tabela:
                        linhas = tabela.find_all("tr")[1:]
                        for linha in linhas:
                            cols = [col.text.strip() for col in linha.find_all("td")]
                            
                            if len(cols) >= 7:
                                data_partida = linha.get("data-date", datetime.now().strftime("%Y-%m-%d"))
                                
                                # Limpeza do nome do jogador e do time
                                raw_jogador = cols[0].split('\n')
                                jogador_nome = raw_jogador[0].strip()
                                time_tag = raw_jogador[1].strip() if len(raw_jogador) > 1 else (cols[1] if len(cols) > 1 else "")

                                dados_simplificados.append({
                                    "Campeonato": torneo['nome'],
                                    "Data_Partida": data_partida,
                                    "Mapa": mapa.capitalize(),
                                    "Jogador": jogador_nome,
                                    "Time": time_tag,
                                    "Personagem": cols[2] if len(cols) > 2 else "N/A", # Agente
                                    "Kills": cols[5] if len(cols) > 5 else "0",       # Total Kills
                                    "Mortes": cols[6] if len(cols) > 6 else "0"       # Total Mortes
                                })
            except Exception as e:
                print(f"Erro ao ler mapa {mapa}: {e}")

    # Salva o arquivo CSV
    arquivo_out = "estatisticas_simplificadas_vct.csv"
    if dados_simplificados:
        campos = ["Campeonato", "Data_Partida", "Mapa", "Jogador", "Time", "Personagem", "Kills", "Mortes"]
        with open(arquivo_out, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()
            writer.writerows(dados_simplificados)
        print(f"\nSucesso! Arquivo '{arquivo_out}' criado com {len(dados_simplificados)} linhas!")
    else:
        print("\nNenhuma tabela de estatísticas foi encontrada para os eventos listados.")

if __name__ == "__main__":
    extrair_estatisticas_simplificadas()