"""
Sincronizador automático do CSV 2026 do Oracle's Elixir via Google Drive.

Arquivo remoto:
2026_LoL_esports_match_data_from_OracleElixir.csv
Google Drive file ID:
1hnpbrUpBMS1TZI7IovfpKeZfWJH1Aptm

Uso:
    python sync_oracle_elixir.py

O processo verifica o arquivo a cada 5 minutos e só substitui o CSV
local quando consegue baixar uma versão nova.
"""

import os
import time
import tempfile
from urllib.request import Request, urlopen

FILE_ID = "1hnpbrUpBMS1TZI7IovfpKeZfWJH1Aptm"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOCAL_FILE = os.path.join(DATA_DIR, "oracles_elixir_2026.csv")

CHECK_EVERY_SECONDS = 300  # 5 minutos
DOWNLOAD_URL = f"https://drive.usercontent.google.com/download?id={FILE_ID}&export=download&confirm=t"

def download_file():
    os.makedirs(DATA_DIR, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix="oracles_elixir_",
        suffix=".csv.part",
        dir=DATA_DIR
    )
    os.close(fd)

    try:
        print("[SYNC] Verificando/baixando versão atual do Google Drive...")
        req = Request(
            DOWNLOAD_URL,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urlopen(req, timeout=180) as response, open(temp_path, "wb") as f:
            total = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)

        if total < 1024:
            raise RuntimeError("Download muito pequeno; o Google Drive pode ter retornado uma página de erro.")

        # Substituição atômica: o app nunca fica com um CSV parcialmente baixado.
        os.replace(temp_path, LOCAL_FILE)

        size_mb = total / (1024 * 1024)
        print(f"[SYNC] CSV atualizado: {size_mb:.1f} MB")
        return True

    except Exception as e:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        print(f"[SYNC] Erro ao atualizar: {e}")
        return False


def main():
    print("==============================================")
    print(" Oracle's Elixir - sincronizador automático")
    print("==============================================")
    print(f"Arquivo local: {LOCAL_FILE}")
    print("Intervalo: 5 minutos")
    print("Pressione Ctrl+C para parar.\n")

    # Primeira execução: garante que exista uma cópia.
    if not os.path.exists(LOCAL_FILE):
        download_file()
    else:
        print("[SYNC] CSV local encontrado. Fazendo verificação inicial...")
        download_file()

    while True:
        try:
            time.sleep(CHECK_EVERY_SECONDS)
            download_file()
        except KeyboardInterrupt:
            print("\n[SYNC] Encerrado.")
            break


if __name__ == "__main__":
    main()
