# /mnt/arquivos/Dropbox/Projetos/desativa_watch/src/sgp_resultados.py
# Comentário: pós-consulta robusto para abrir o cliente mesmo quando a grade não expõe <a> “bons”.
# Estratégias:
#   1) Linha do e-mail: tenta clicar <a> válido; fallback: qualquer <a>; data-href/onclick; duplo clique; ENTER.
#   2) Extração de ID no <tr> (data-cliente-id, idcliente, etc.) → navega para /admin/cliente/{id}/ (ou /edit/).
#   3) Global: âncoras de cliente no DOM (filtradas p/ ter ID) ou regex no HTML (href, data-href, onclick).
# Tudo com comentários e modularização.

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Iterable
from time import sleep
import re
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException,
    StaleElementReferenceException,
)

from .config import SERVICO_TV_WAIT_SECONDS
from .frame_utils import iter_frame_paths, switch_to_frame_path

# =========================
# Seletores de resultados
# =========================

SEL_TABELA: Tuple[str, str] = (
    By.XPATH,
    "//table[contains(@class,'table') or contains(@class,'tablelist') or contains(@class,'data')]",
)
SEL_TABELA_LINHAS: Tuple[str, str] = (By.XPATH, "//table//tbody//tr")
SEL_LINKS_CLIENTE_DOM: Tuple[str, str] = (By.XPATH, "//a[contains(@href,'/admin/cliente/')]")
SEL_LINK_EDITAR: Tuple[str, str] = (By.XPATH, "//a[contains(@href,'/admin/cliente/') and contains(@href,'/edit')]")

# =========================
# Regex p/ capturar URLs e IDs
# =========================

# URLs com ID no path  ou em ?id=123  — vindas de href, data-href, onclick
RE_HREF_IDPATH      = re.compile(r'href="(?P<href>[^"]*/admin/cliente/\d+[^"]*)"', re.IGNORECASE)
RE_DATA_HREF_IDPATH = re.compile(r'data-href="(?P<href>[^"]*/admin/cliente/\d+[^"]*)"', re.IGNORECASE)
RE_ONCLICK_IDPATH   = re.compile(r"onclick=\"[^\"']*['\"](?P<href>[^\"']*/admin/cliente/\d+[^\"']*)['\"][^\"']*\"", re.IGNORECASE)
RE_HREF_QS_ID       = re.compile(r'href="(?P<href>[^"]*/admin/cliente/[^"?"]*\?[^"]*\bid=\d+[^"]*)"', re.IGNORECASE)
RE_DATA_HREF_QS_ID  = re.compile(r'data-href="(?P<href>[^"]*/admin/cliente/[^"?"]*\?[^"]*\bid=\d+[^"]*)"', re.IGNORECASE)
RE_ONCLICK_QS_ID    = re.compile(r"onclick=\"[^\"']*['\"](?P<href>[^\"']*/admin/cliente/[^\"']*\?[^\"']*\bid=\d+[^\"']*)['\"][^\"']*\"", re.IGNORECASE)

# ID do cliente embutido em atributos / HTML da linha
RE_ID_INLINE = re.compile(
    r"(?:\b(idcliente|cliente_id|id-cliente|idCliente|clienteId)\b[^0-9]{0,20})(?P<id>\d+)",
    re.IGNORECASE,
)
RE_ID_INNER  = re.compile(r"/admin/cliente/(?P<id>\d+)", re.IGNORECASE)

NO_RESULT_PATTERNS = (
    "Nenhum registro encontrado",
    "Nenhum resultado encontrado",
    "Não há registros",
    "Sem resultados",
)

# =========================
# Helpers genéricos
# =========================

def _safe_find(driver, by, sel):
    try:
        return driver.find_elements(by, sel)
    except Exception:
        return []

def _page_has_email(driver, email_low: str) -> bool:
    try:
        return email_low in (driver.page_source or "").lower()
    except Exception:
        return False


def _page_has_no_result_message(driver) -> bool:
    try:
        src_low = (driver.page_source or "").lower()
    except Exception:
        return False
    return any(msg.lower() in src_low for msg in NO_RESULT_PATTERNS)

def _amostra_hrefs(anchors, n=5) -> List[str]:
    out = []
    for a in anchors[:n]:
        try:
            href = a.get_attribute("href")
            if href:
                out.append(href)
        except Exception:
            pass
    return out

def _href_has_id(href: str) -> bool:
    if not href:
        return False
    href_low = href.lower()
    return "/admin/cliente/" in href_low and (re.search(r"/admin/cliente/\d+", href_low) or re.search(r"[?&]id=\d+", href_low))

def _is_cliente_href(href: str) -> bool:
    if not _href_has_id(href):
        return False
    href_low = href.lower()
    return not any(s in href_low for s in ("/list", "/search", "/add/", "/relatorio"))

def _extract_cliente_hrefs_from_html(driver, max_n: int = 10) -> List[str]:
    """Extrai URLs absolutas /admin/cliente/<id> (ou ?id=123) do HTML (href, data-href, onclick)."""
    try:
        html = driver.page_source or ""
    except Exception:
        html = ""
    base = driver.current_url

    raw = []
    for pattern in (
        RE_HREF_IDPATH, RE_DATA_HREF_IDPATH, RE_ONCLICK_IDPATH,
        RE_HREF_QS_ID,  RE_DATA_HREF_QS_ID,  RE_ONCLICK_QS_ID,
    ):
        for m in pattern.finditer(html):
            raw.append(m.group("href"))

    hrefs: List[str] = []
    seen = set()
    for h in raw:
        absu = urljoin(base, h)
        if _is_cliente_href(absu) and absu not in seen:
            hrefs.append(absu)
            seen.add(absu)
        if len(hrefs) >= max_n:
            break
    return hrefs

def _click(driver, el) -> None:
    try:
        el.click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", el)

def _wait_url_contains(driver, needles: Iterable[str], timeout: int = 6) -> bool:
    """Espera a URL conter qualquer substring de needles."""
    try:
        WebDriverWait(driver, timeout).until(lambda d: any(n in (d.current_url or "") for n in needles))
        return True
    except TimeoutException:
        return False


def _snapshot_context(driver, email_low: str, path: Tuple[int, ...]) -> Dict:
    anchors_dom = _safe_find(driver, *SEL_LINKS_CLIENTE_DOM)
    rows = _safe_find(driver, *SEL_TABELA_LINHAS)
    parsed_hrefs = _extract_cliente_hrefs_from_html(driver, max_n=10)
    email_present = _page_has_email(driver, email_low)
    none_msg = _page_has_no_result_message(driver)

    anchors_validos = []
    for a in anchors_dom:
        try:
            href = a.get_attribute("href") or ""
            if _is_cliente_href(href):
                anchors_validos.append(a)
        except Exception:
            pass

    score = (
        (20 if anchors_validos else 0)
        + (10 if parsed_hrefs else 0)
        + (5 if rows else 0)
        + (3 if email_present else 0)
        + (1 if none_msg else 0)
    )
    found = bool(anchors_validos or rows or parsed_hrefs or email_present or none_msg)
    return {
        "path": tuple(path),
        "found": found,
        "anchors_cliente": len(anchors_validos),
        "rows_total": len(rows),
        "email_present": email_present,
        "none_msg": none_msg,
        "sample_hrefs": _amostra_hrefs(anchors_validos, n=5),
        "parsed_hrefs": parsed_hrefs[:5],
        "score": score,
    }


def localizar_contexto_resultado(driver, email: str, max_depth: int = 4) -> Dict:
    """
    Varre o topo e iframes procurando o contexto onde os resultados foram renderizados.
    Se encontrar sinais, já deixa o driver no melhor contexto encontrado.
    """
    email_low = (email or "").lower()
    best = {
        "path": (),
        "found": False,
        "anchors_cliente": 0,
        "rows_total": 0,
        "email_present": False,
        "none_msg": False,
        "sample_hrefs": [],
        "parsed_hrefs": [],
        "score": -1,
    }

    for path in iter_frame_paths(driver, max_depth=max_depth):
        try:
            switch_to_frame_path(driver, path)
            snap = _snapshot_context(driver, email_low, path)
        except Exception:
            continue
        if snap["score"] > best["score"]:
            best = snap

    switch_to_frame_path(driver, best["path"])
    return best

# =========================
# Helpers focados na LINHA da grade
# =========================

def _linha_contem_email(tr, email_low: str) -> bool:
    try:
        txt = (tr.get_attribute("innerText") or "").lower()
        return email_low in txt
    except Exception:
        return False

def _extract_id_from_tr(tr) -> Optional[str]:
    """Coleta um possível ID de cliente a partir de atributos/HTML da <tr>."""
    # 1) atributos clássicos
    for attr in ("data-cliente-id", "data-id", "data-idcliente", "data-id-cliente", "cliente-id", "idcliente", "cliente_id"):
        try:
            v = tr.get_attribute(attr) or ""
            m = re.search(r"\d+", v)
            if m:
                return m.group(0)
        except Exception:
            pass
    # 2) onclick/data-href com ID
    try:
        oc = tr.get_attribute("onclick") or ""
        m = RE_ID_INNER.search(oc)
        if m:
            return m.group("id")
    except Exception:
        pass
    try:
        dh = tr.get_attribute("data-href") or ""
        m = RE_ID_INNER.search(dh)
        if m:
            return m.group("id")
    except Exception:
        pass
    # 3) innerHTML/innerText procurando padrões
    try:
        html = tr.get_attribute("innerHTML") or ""
        m = RE_ID_INLINE.search(html) or RE_ID_INNER.search(html)
        if m:
            return m.group("id")
    except Exception:
        pass
    try:
        txt = tr.get_attribute("innerText") or ""
        m = RE_ID_INLINE.search(txt)
        if m:
            return m.group("id")
    except Exception:
        pass
    return None

def _abrir_por_duplo_clique(driver, tr) -> bool:
    """Tenta abrir o cliente com duplo clique na linha (caso o grid use handler JS)."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tr)
    except Exception:
        pass
    try:
        ActionChains(driver).move_to_element(tr).double_click(tr).perform()
        if _wait_url_contains(driver, ("/admin/cliente/",), timeout=5):
            return True
    except WebDriverException:
        pass
    return False

def _abrir_por_enter(driver, tr) -> bool:
    """Tenta abrir via ENTER focando a linha."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", tr)
    except Exception:
        pass
    try:
        tr.click()
        tr.send_keys(Keys.ENTER)
        if _wait_url_contains(driver, ("/admin/cliente/",), timeout=5):
            return True
    except WebDriverException:
        pass
    return False

# =========================
# API
# =========================

def aguardar_resultado_busca_cliente(driver, email: str, timeout: float | None = None) -> Dict:
    """
    Espera por indícios de resultado:
      - linhas na tabela (se houver),
      - anchors /admin/cliente/ no DOM (filtrados p/ conter ID),
      - presença do e-mail no HTML,
      - hrefs /admin/cliente/<id> (ou ?id=123) extraídos do HTML.
    Retorna dict: {found, anchors_cliente, rows_total, email_present, sample_hrefs, parsed_hrefs}
    """
    email_low = (email or "").lower()
    if timeout is None:
        timeout = max(6.0, SERVICO_TV_WAIT_SECONDS * 2.0)

    t, step = 0.0, 0.2
    best = {
        "path": (),
        "found": False,
        "anchors_cliente": 0,
        "rows_total": 0,
        "email_present": False,
        "none_msg": False,
        "sample_hrefs": [],
        "parsed_hrefs": [],
        "score": -1,
    }

    while t < timeout:
        snap = localizar_contexto_resultado(driver, email, max_depth=4)
        if snap["score"] > best["score"]:
            best = snap
        if snap["found"]:
            break
        sleep(step); t += step

    return {
        "found": best["found"],
        "anchors_cliente": best["anchors_cliente"],
        "rows_total": best["rows_total"],
        "email_present": best["email_present"],
        "none_msg": best["none_msg"],
        "sample_hrefs": best["sample_hrefs"],
        "parsed_hrefs": best["parsed_hrefs"],
        "frame_path": list(best["path"]),
    }

def clicar_resultado_por_email(driver, email: str, retries: int = 3) -> None:
    """
    Abre o cliente correspondente ao e-mail.
    Ordem:
      1) Linha com o e-mail:
         1.a) clica <a> /admin/cliente/<id> (ou /edit) na linha;
         1.b) fallback: qualquer <a> visível na linha;
         1.c) fallback: data-href / onclick do <tr>;
         1.d) fallback: duplo clique;
         1.e) fallback: ENTER focando a linha;
         1.f) fallback: extrai ID do <tr> e navega p/ /admin/cliente/{id}/.
      2) Global: primeiro <a> válido no DOM.
      3) Global: regex no HTML (href/data-href/onclick) → driver.get(...).
    """
    email_low = (email or "").lower()
    last_exc: Optional[Exception] = None

    for _ in range(retries):
        try:
            localizar_contexto_resultado(driver, email, max_depth=4)
        except Exception as e:
            last_exc = e

        # 1) percorre linhas da tabela procurando a que contém o e-mail
        try:
            trs = _safe_find(driver, *SEL_TABELA_LINHAS)
            encontrou_linha_email = False
            for tr in trs:
                if not _linha_contem_email(tr, email_low):
                    continue
                encontrou_linha_email = True

                # (1.a) clica âncora válida na linha
                try:
                    a = tr.find_element(By.XPATH, ".//a[contains(@href,'/admin/cliente/')]")
                    href = a.get_attribute("href") or ""
                    if _is_cliente_href(href) and a.is_displayed():
                        driver.get(href); return
                except Exception as e:
                    last_exc = e

                # (1.b) qualquer <a> visível na linha (às vezes dispara JS que redireciona)
                try:
                    for a in tr.find_elements(By.XPATH, ".//a[@href]"):
                        if a.is_displayed():
                            _click(driver, a)
                            if _wait_url_contains(driver, ("/admin/cliente/",), timeout=4):
                                return
                except Exception as e:
                    last_exc = e

                # (1.c) data-href / onclick no <tr>
                try:
                    dh = tr.get_attribute("data-href") or ""
                    if _is_cliente_href(dh):
                        driver.get(urljoin(driver.current_url, dh)); return
                    oc = tr.get_attribute("onclick") or ""
                    m = re.search(r"['\"]([^\"']*/admin/cliente/[^\"']*)['\"]", oc, re.IGNORECASE)
                    if m and _is_cliente_href(m.group(1)):
                        driver.get(urljoin(driver.current_url, m.group(1))); return
                except Exception as e:
                    last_exc = e

                # (1.d) duplo clique + espera URL mudar
                if _abrir_por_duplo_clique(driver, tr): return

                # (1.e) ENTER
                if _abrir_por_enter(driver, tr): return

                # (1.f) extrai ID do <tr> e navega
                cid = _extract_id_from_tr(tr)
                if cid:
                    driver.get(urljoin(driver.current_url, f"/admin/cliente/{cid}/")); return

                # achamos a linha mas não conseguimos abrir — continuar fallbacks globais
                break
            if trs and not encontrou_linha_email:
                raise TimeoutException(
                    f"Nenhuma linha do resultado contém o e-mail consultado: {email}"
                )
        except StaleElementReferenceException as e:
            last_exc = e
        except TimeoutException as e:
            last_exc = e
            break

        # 2) qualquer âncora válida no DOM
        try:
            anchors = _safe_find(driver, *SEL_LINKS_CLIENTE_DOM)
            for a in anchors:
                try:
                    href = a.get_attribute("href") or ""
                    if _is_cliente_href(href) and a.is_displayed():
                        driver.get(href); return
                except StaleElementReferenceException as e:
                    last_exc = e; continue
                except Exception as e:
                    last_exc = e; continue
        except Exception as e:
            last_exc = e

        # 3) regex no HTML bruto (href, data-href, onclick)
        try:
            hrefs = _extract_cliente_hrefs_from_html(driver, max_n=5)
            if hrefs:
                driver.get(hrefs[0]); return
        except Exception as e:
            last_exc = e

        sleep(0.25)

    raise TimeoutException(f"Não foi possível abrir o cliente após tentativas. Último erro: {last_exc}")

def entrar_em_modo_edicao_no_cliente(driver, timeout: int = 20) -> None:
    """
    Dentro da página do cliente, tenta abrir /edit/ (com fallbacks).
    """
    if "/admin/cliente/" in (driver.current_url or "") and "/edit/" in (driver.current_url or ""):
        return

    try:
        el = WebDriverWait(driver, min(timeout, 5)).until(EC.element_to_be_clickable(SEL_LINK_EDITAR))
        try:
            el.click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", el)
        WebDriverWait(driver, min(timeout, 6)).until(lambda d: "/edit/" in (d.current_url or ""))
        return
    except TimeoutException:
        pass

    FALLBACKS = [
        (By.CSS_SELECTOR, "a.edit"),
        (By.XPATH, "//a[@title='Editar' or contains(@aria-label,'Editar')]"),
        (By.XPATH, "//*[self::a or self::button][@title='Editar' or contains(@class,'edit') or contains(@aria-label,'Editar')]"),
        (By.XPATH, "//i[contains(@class,'fa-pencil') or contains(@class,'glyphicon-pencil')]/ancestor::a[1]"),
    ]
    for by, sel in FALLBACKS:
        try:
            el = WebDriverWait(driver, min(timeout, 4)).until(EC.element_to_be_clickable((by, sel)))
            try:
                el.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", el)
            WebDriverWait(driver, min(timeout, 6)).until(lambda d: "/edit/" in (d.current_url or ""))
            return
        except TimeoutException:
            continue

    raise TimeoutException("Botão/Link 'Editar' não encontrado na página do cliente.")
