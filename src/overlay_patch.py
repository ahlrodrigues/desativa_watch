# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/overlay_patch.py
# Comentário: utilitários para lidar com a overlay de "pré-busca" (.pre-search).
# - Injeta JS que esconde a overlay em eventos de chegada (load/pageshow/ajaxStop)
# - Aguarda a overlay sumir de forma explícita (WebDriverWait invisibility)
# - Força esconder (band-aid) se o site não esconder sozinho
#
# Configurável via variáveis de ambiente (opcional):
#   PRE_SEARCH_SELECTOR      -> seletor CSS da overlay (padrão: ".pre-search")
#   OVERLAY_WAIT_TIMEOUT     -> timeout padrão para aguardar invisibilidade (padrão: "12")
#   OVERLAY_FORCE_HIDE       -> "true"/"false": se true, força esconder ao final do wait

from __future__ import annotations
import os
from typing import Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def _sel() -> str:
    """Lê o seletor da overlay do ambiente (padrão .pre-search)."""
    return (os.getenv("PRE_SEARCH_SELECTOR") or ".pre-search").strip()

def _wait_timeout(default: int = 12) -> int:
    """Timeout padrão para aguardar invisibilidade (segundos)."""
    try:
        return int(os.getenv("OVERLAY_WAIT_TIMEOUT") or default)
    except Exception:
        return default

def _force_hide_enabled() -> bool:
    """Se true, força esconder a overlay após o wait (último recurso)."""
    return (os.getenv("OVERLAY_FORCE_HIDE") or "false").strip().lower() in ("1", "true", "yes", "y")

def inject_overlay_auto_hide(driver) -> None:
    """
    Injeta JS para garantir que a overlay seja escondida em:
      - load/pageshow/DOMContentLoaded
      - ajaxStop (se jQuery estiver presente)
    """
    script = f"""
    (function() {{
      var SEL = {repr(_sel())};

      function hideOverlay() {{
        try {{
          var els = document.querySelectorAll(SEL);
          els.forEach(function(el) {{
            // esconde com prioridade
            el.style.setProperty('display', 'none', 'important');
            el.style.setProperty('visibility', 'hidden', 'important');
            el.style.setProperty('pointer-events', 'none', 'important');
            el.classList.add('overlay-hidden-by-robot');
          }});
        }} catch (e) {{}}
      }}

      // Esconde na chegada/volta de página
      window.addEventListener('load', hideOverlay, true);
      window.addEventListener('pageshow', hideOverlay, true);
      document.addEventListener('DOMContentLoaded', hideOverlay, true);

      // Se jQuery existe, esconde ao finalizar Ajax
      try {{
        if (window.jQuery) {{
          jQuery(document).ajaxStop(hideOverlay);
        }}
      }} catch (e) {{}}

      // Observa inserção da overlay e esconde
      try {{
        var mo = new MutationObserver(function(muts) {{
          muts.forEach(function(m) {{
            if (!m.addedNodes) return;
            m.addedNodes.forEach(function(n) {{
              try {{
                if (n.nodeType === 1 && n.matches && n.matches(SEL)) {{
                  hideOverlay();
                }}
              }} catch(e) {{}}
            }});
          }});
        }});
        mo.observe(document.documentElement, {{ childList: true, subtree: true }});
      }} catch (e) {{}}

      // Chama uma vez agora
      hideOverlay();
    }})();"""
    try:
        driver.execute_script(script)
    except Exception:
        pass

def wait_overlay_gone(driver, timeout: Optional[int] = None) -> bool:
    """
    Aguarda a overlay ficar invisível ou ausente.
    Retorna True se sumiu, False se ainda existe após timeout.
    """
    timeout = _wait_timeout() if timeout is None else timeout
    try:
        WebDriverWait(driver, timeout).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, _sel()))
        )
        return True
    except Exception:
        return False

def force_hide_overlay(driver) -> None:
    """
    Força esconder a overlay imediatamente (band-aid para testes).
    """
    try:
        driver.execute_script(
            """
            (function(SEL){
              try{
                var els=document.querySelectorAll(SEL);
                els.forEach(function(el){
                  el.style.setProperty('display','none','important');
                  el.style.setProperty('visibility','hidden','important');
                  el.style.setProperty('pointer-events','none','important');
                  el.classList.add('overlay-hidden-by-robot');
                });
              }catch(e){}
            })(arguments[0]);
            """,
            _sel(),
        )
    except Exception:
        pass

def ensure_overlay_after_submit(driver, timeout: Optional[int] = None) -> None:
    """
    Pipeline recomendado após o clique em 'Consultar':
      1) injeta auto-hide (idempotente)
      2) aguarda a overlay sumir
      3) se habilitado por env, força esconder como fallback
    """
    inject_overlay_auto_hide(driver)
    ok = wait_overlay_gone(driver, timeout=timeout)
    if not ok and _force_hide_enabled():
        force_hide_overlay(driver)
