import json
import requests
from bs4 import BeautifulSoup

def buscar_dados():
    # URL de exemplo (substitua pela URL exata da sua fonte de dados)
    url = "https://www.vlr.gg/stats"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # Exemplo de estrutura de dados para o seu site
        dados_atualizados = {
            "ultima_atualizacao": "2026-08-08",
            "times": []
        }

        # Extração de dados da tabela (ajuste seletores conforme a fonte)
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 6:
                jogador_info = {
                    "jogador": cols[0].text.strip(),
                    "agente": cols[1].text.strip(),
                    "rating": cols[2].text.strip(),
                    "acs": cols[3].text.strip(),
                    "kills": cols[4].text.strip(),
                    "mortes": cols[5].text.strip(),
                }
                # Adiciona ao objeto final
                dados_atualizados["times"].append(jogador_info)

        # Salva ou atualiza o arquivo JSON no seu servidor
        with open("dados_times.json", "w", encoding="utf-8") as f:
            json.dump(dados_atualizados, f, ensure_ascii=False, indent=4)

        print("✔ Arquivos de dados atualizados com sucesso!")

    except Exception as e:
        print(f"❌ Erro ao atualizar dados: {e}")

if __name__ == "__main__":
    buscar_dados()