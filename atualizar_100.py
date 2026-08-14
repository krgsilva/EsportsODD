import json
import requests
from bs4 import BeautifulSoup

def extrair_dados_completos():
    # Lista com todos os mapas do jogo/competitivos
    mapas = [
        "ascent", "bind", "breeze", "fracture", 
        "haven", "icebox", "lotus", "pearl", 
        "split", "sunset", "abyss"
    ]
    
    base_url = "https://www.vlr.gg/stats" 
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    dados_finais = {
        "filtro_partidas": "Ultimos 20",
        "mapas": {}
    }

    for mapa in mapas:
        print(f"Coletando dados do mapa: {mapa.capitalize()}...")
        dados_finais["mapas"][mapa] = []

        url_mapa = f"{base_url}?map={mapa}"
        
        try:
            response = requests.get(url_mapa, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            blocos_time = soup.find_all("div", class_="team-card")

            for bloco in blocos_time:
                nome_time = bloco.find("h2").text.strip() if bloco.find("h2") else "Time Desconhecido"
                vitorias = bloco.find("span", class_="wins").text.strip() if bloco.find("span", class_="wins") else "0"
                derrotas = bloco.find("span", class_="losses").text.strip() if bloco.find("span", class_="losses") else "0"
                aproveitamento = bloco.find("span", class_="winrate").text.strip() if bloco.find("span", class_="winrate") else "0%"
                mapas_jogados = bloco.find("span", class_="played").text.strip() if bloco.find("span", class_="played") else "0"

                time_info = {
                    "time": nome_time,
                    "estatisticas_time": {
                        "vitorias": int(vitorias),
                        "derrotas": int(derrotas),
                        "aproveitamento": aproveitamento,
                        "mapas_jogados": int(mapas_jogados)
                    },
                    "jogadores": []
                }

                tabela = bloco.find("table")
                if tabela:
                    linhas = tabela.find_all("tr")[1:]
                    for linha in linhas:
                        colunas = linha.find_all("td")
                        if len(colunas) >= 8:
                            jogador_data = {
                                "jogador": colunas[0].text.strip(),
                                "agente": colunas[1].text.strip(),
                                "rating": float(colunas[2].text.strip() or 0),
                                "acs": float(colunas[3].text.strip() or 0),
                                "kills": float(colunas[4].text.strip() or 0),
                                "mortes": float(colunas[5].text.strip() or 0),
                                "assistencias": float(colunas[6].text.strip() or 0),
                                "adr": float(colunas[7].text.strip() or 0)
                            }
                            time_info["jogadores"].append(jogador_data)

                dados_finais["mapas"][mapa].append(time_info)

        except Exception as e:
            print(f"Erro ao raspar dados do mapa {mapa}: {e}")

    with open("dados_completos.json", "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, ensure_ascii=False, indent=4)

    print("\n Base de dados com TODOS os mapas atualizada com sucesso!")

if __name__ == "__main__":
    extrair_dados_completos()