# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/debug_utils.py
# Comentário: helpers para gerar artefatos de debug (screenshot e HTML) em data/output/.

import os
from datetime import datetime

from .config import OUTPUT_DIR

def _ts():
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def dump_page_artifacts(driver, prefix="page"):
    """Salva screenshot e HTML da página atual para debug."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = os.path.join(OUTPUT_DIR, f"{prefix}_{_ts()}")
    png = base + ".png"
    html = base + ".html"
    try:
        driver.save_screenshot(png)
    except Exception:
        pass
    try:
        source = driver.page_source
        with open(html, "w", encoding="utf-8") as f:
            f.write(source)
    except Exception:
        pass
    print(f"🧩 Artefatos salvos para debug: {png} / {html}")
