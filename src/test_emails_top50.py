# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/test_emails_top50.py
# Comentário: abre export_never_YYYYMMDD*, ordena o DF inteiro por INTEGRACAO (datetime),
# pega TOP 50 e extrai e-mails desse recorte.

import sys
from .config import TARGET_DATE_YYYYMMDD
from .files import resolve_data_para_busca, localizar_arquivo_export_never, abrir_planilha_export_never
from .data_ops import sort_df_by_integracao_datetime, top_n_rows, find_column
from .email_utils import extrair_emails

def run():
    data_cli = sys.argv[1] if len(sys.argv) > 1 else None
    date_str = resolve_data_para_busca(TARGET_DATE_YYYYMMDD or data_cli)
    print(f"🗓️  Usando data para busca: {date_str}")

    caminho, _ = localizar_arquivo_export_never(date_str)
    print(f"📄 Lendo: {caminho}")
    df = abrir_planilha_export_never(caminho)
    print(f"ℹ️  Colunas: {list(df.columns)}  | Linhas: {len(df)}")

    # ✅ Ordena o DataFrame INTEIRO sempre como datetime
    df_sorted, metodo, col_real = sort_df_by_integracao_datetime(df, candidates=("INTEGRACAO", "INTEGRAÇÃO"), ascending=True)
    print(f"✅ Ordenado por '{col_real}' como datetime (método: {metodo})")

    # Preview pós-ordenação (INTEGRACAO + EMAIL, se existir)
    try:
        col_email = find_column(df_sorted, ("EMAIL",))
    except Exception:
        col_email = None

    print("🔹 Preview 5 primeiras linhas já ordenadas:")
    cols_preview = [col_real] + ([col_email] if col_email else [])
    print(df_sorted[cols_preview].head(5).to_string(index=False))

    # 🔸 TOP 50 linhas
    df_top50 = top_n_rows(df_sorted, n=50)
    print(f"🔸 Recorte: {len(df_top50)} linhas (TOP 50 após ordenação).")

    # 📧 E-mails somente do TOP 50
    emails_top50 = extrair_emails(df_top50, coluna_preferida="EMAIL")
    print(f"📧 E-mails únicos do TOP 50: {len(emails_top50)}")
    for i, e in enumerate(emails_top50[:20], 1):
        print(f"   {i:02d}. {e}")

if __name__ == "__main__":
    run()
