# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/test_open_planilha.py
# Comentário: teste simples que:
#   1) Resolve a data alvo (YYYYMMDD);
#   2) Localiza o arquivo export_never_YYYYMMDD*.xlsx no Downloads;
#   3) Abre a planilha e imprime um resumo (linhas, colunas).

import sys
from .config import TARGET_DATE_YYYYMMDD
from .files import resolve_data_para_busca, localizar_arquivo_export_never, abrir_planilha_export_never

def run():
    # 1) Decide a data a usar (ENV > argumento CLI > hoje)
    #    - Você pode rodar:  python -m src.test_open_planilha 20250811
    data_cli = sys.argv[1] if len(sys.argv) > 1 else None
    date_str = resolve_data_para_busca(TARGET_DATE_YYYYMMDD or data_cli)

    print(f"🗓️  Usando data para busca: {date_str}")

    # 2) Localiza o arquivo
    caminho, todos = localizar_arquivo_export_never(date_str)
    print(f"🔎 Arquivos encontrados ({len(todos)}):")
    for p in todos:
        print(f"   - {p}")
    print(f"📄 Selecionado (mais recente): {caminho}")

    # 3) Abre a planilha e exibe um resumo básico
    df = abrir_planilha_export_never(caminho)
    print("✅ Planilha aberta com sucesso!")
    print(f"   Linhas: {len(df):,}")
    print(f"   Colunas: {list(df.columns)}")

if __name__ == "__main__":
    run()
