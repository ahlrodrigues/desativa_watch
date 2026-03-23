# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/config.py
# Comentário: acrescenta modo SERVICO_TV_REOPEN_MODE='new_tab'.

import os
from dotenv import load_dotenv
load_dotenv()

def _as_bool(v, default=False):
    if v is None: return default
    return str(v).strip().lower() in ("1","true","on","yes","y")

def _as_choice(value, choices, default):
    if not value: return default
    v = str(value).strip().lower()
    return v if v in choices else default

SGP_BASE_URL = os.getenv("SGP_BASE_URL","").rstrip("/")
SGP_USER = os.getenv("SGP_USER","")
SGP_PASS = os.getenv("SGP_PASS","")

HEADLESS = _as_bool(os.getenv("HEADLESS","true"), True)
IMPLICIT_WAIT = int(os.getenv("IMPLICIT_WAIT","5"))
PAGELOAD_TIMEOUT = int(os.getenv("PAGELOAD_TIMEOUT","60"))
LANG = os.getenv("LANG","pt-BR")

NAV_REQUIRES_HOVER = _as_bool(os.getenv("NAV_REQUIRES_HOVER","false"), False)
MENU_IFRAME_NAME_OR_ID = (os.getenv("MENU_IFRAME_NAME_OR_ID") or "").strip() or None

STRICT_INPUT_ASSIGNMENT = _as_bool(os.getenv("STRICT_INPUT_ASSIGNMENT","true"), True)

DOWNLOADS_DIR = os.path.expanduser(os.getenv("DOWNLOADS_DIR","~/Downloads")).rstrip("/")
TARGET_DATE_YYYYMMDD = (os.getenv("TARGET_DATE_YYYYMMDD") or "").strip()

SERVICO_TV_WAIT_SECONDS = float(os.getenv("SERVICO_TV_WAIT_SECONDS","3.0"))

# ⬇️ agora aceitamos 'new_tab' também
SERVICO_TV_REOPEN_MODE = _as_choice(
    os.getenv("SERVICO_TV_REOPEN_MODE","click_path"),
    choices=("click_path","reload","new_tab"),
    default="click_path",
)
SERVICO_TV_MAX_RETRY_ON_EMPTY = int(os.getenv("SERVICO_TV_MAX_RETRY_ON_EMPTY","1"))
FULL_REOPEN_BETWEEN_EMAILS = _as_bool(os.getenv("FULL_REOPEN_BETWEEN_EMAILS","true"), True)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")

if not SGP_BASE_URL:
    raise ValueError("SGP_BASE_URL não definido no .env")
if not SGP_USER or not SGP_PASS:
    raise ValueError("SGP_USER/SGP_PASS não definidos no .env")
