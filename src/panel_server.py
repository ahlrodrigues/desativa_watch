from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import BASE_DIR, OUTPUT_DIR
from .email_lists import (
    add_email_to_blacklist,
    add_email_to_greenlist,
    load_blacklist,
    load_greenlist,
    remove_email_from_blacklist,
    remove_email_from_greenlist,
)


PANEL_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Painel Desativa Watch</title>
  <style>
    :root {
      --bg: #f3efe7;
      --panel: #fffaf2;
      --panel-strong: #fff;
      --ink: #231f1a;
      --muted: #6d6458;
      --line: #d9cdbd;
      --accent: #0c7c59;
      --accent-soft: #dff4ea;
      --warn: #b85c38;
      --warn-soft: #fde8df;
      --shadow: 0 20px 45px rgba(81, 58, 34, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(184, 92, 56, 0.12), transparent 32%),
        radial-gradient(circle at top right, rgba(12, 124, 89, 0.12), transparent 28%),
        linear-gradient(180deg, #f8f3eb 0%, var(--bg) 100%);
    }
    .shell {
      width: min(1200px, calc(100vw - 32px));
      margin: 24px auto 40px;
    }
    .hero {
      background: linear-gradient(135deg, rgba(35,31,26,0.96), rgba(73,54,35,0.92));
      color: #fff8ef;
      border-radius: 24px;
      padding: 28px;
      box-shadow: var(--shadow);
      margin-bottom: 20px;
    }
    .hero h1 {
      margin: 0 0 8px;
      font-size: clamp(1.8rem, 3vw, 2.7rem);
      letter-spacing: -0.03em;
    }
    .hero p {
      margin: 0;
      max-width: 780px;
      color: rgba(255, 248, 239, 0.82);
      line-height: 1.5;
    }
    .grid {
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .panel {
      background: var(--panel);
      border: 1px solid rgba(113, 97, 78, 0.12);
      border-radius: 20px;
      padding: 18px;
      box-shadow: var(--shadow);
    }
    .panel h2 {
      margin: 0 0 8px;
      font-size: 1.15rem;
    }
    .panel p {
      margin: 0 0 16px;
      color: var(--muted);
      line-height: 1.45;
    }
    .list-input {
      display: flex;
      gap: 10px;
      margin-bottom: 14px;
    }
    .list-input textarea {
      flex: 1;
      border: 1px solid var(--line);
      background: var(--panel-strong);
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 0.98rem;
      color: var(--ink);
      min-height: 108px;
      resize: vertical;
      font-family: inherit;
    }
    button {
      border: 0;
      border-radius: 12px;
      padding: 12px 16px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.15s ease, opacity 0.15s ease, background 0.15s ease;
    }
    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.55; cursor: not-allowed; transform: none; }
    .btn-primary { background: var(--accent); color: white; }
    .btn-secondary { background: #efe4d5; color: var(--ink); }
    .btn-danger { background: var(--warn-soft); color: var(--warn); }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 12px;
      border-radius: 999px;
      font-size: 0.9rem;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 700;
    }
    .badge.idle {
      background: #ece5db;
      color: #7b6e61;
    }
    .email-list {
      display: flex;
      flex-direction: column;
      gap: 10px;
      max-height: 320px;
      overflow: auto;
      padding-right: 4px;
    }
    .email-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 14px;
      background: var(--panel-strong);
      border: 1px solid rgba(113, 97, 78, 0.12);
    }
    .email-item span {
      word-break: break-word;
      font-size: 0.96rem;
    }
    .run-panel {
      grid-column: 1 / -1;
    }
    .run-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin-bottom: 14px;
    }
    .run-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 14px;
    }
    .log-box {
      background: #1c1b19;
      color: #e7f9f0;
      border-radius: 18px;
      padding: 16px;
      min-height: 360px;
      max-height: 55vh;
      overflow: auto;
      font: 0.92rem/1.5 "Cascadia Code", "Consolas", monospace;
      white-space: pre-wrap;
    }
    .message {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 12px;
      display: none;
      font-weight: 600;
    }
    .message.show { display: block; }
    .message.ok { background: var(--accent-soft); color: var(--accent); }
    .message.err { background: var(--warn-soft); color: var(--warn); }
    .empty {
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 14px;
      padding: 18px;
      text-align: center;
      background: rgba(255,255,255,0.55);
    }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
      .run-panel { grid-column: auto; }
      .shell { width: min(100vw - 20px, 1200px); }
      .hero, .panel { border-radius: 18px; }
      .list-input { flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>Painel Desativa Watch</h1>
      <p>Gerencie as listas operacionais, dispare a execução da automação e acompanhe em tempo real cada passo do processo sem depender do terminal.</p>
    </section>

    <section class="grid">
      <article class="panel">
        <h2>Greenlist <span id="green-count" class="badge idle">0</span></h2>
        <p>E-mails liberados para processamento no próximo lote.</p>
        <div class="list-input">
          <textarea id="green-input" placeholder="Cole um ou vários e-mails, um por linha ou separados por espaço"></textarea>
          <button class="btn-primary" onclick="addEmail('greenlist')">Adicionar</button>
        </div>
        <div id="greenlist" class="email-list"></div>
      </article>

      <article class="panel">
        <h2>Blacklist <span id="black-count" class="badge idle">0</span></h2>
        <p>E-mails bloqueados que nunca devem ser processados.</p>
        <div class="list-input">
          <textarea id="black-input" placeholder="Cole um ou vários e-mails, um por linha ou separados por espaço"></textarea>
          <button class="btn-primary" onclick="addEmail('blacklist')">Adicionar</button>
        </div>
        <div id="blacklist" class="email-list"></div>
      </article>

      <article class="panel run-panel">
        <h2>Execução</h2>
        <p>Quando houver e-mails na greenlist, a automação começa sozinha. O campo de log acompanha a execução em tempo real, incluindo cada passo da automação.</p>
        <div class="run-actions">
          <div id="run-info" class="empty" style="padding:12px 14px; text-align:left;">
            A automação é iniciada automaticamente quando a greenlist tiver e-mails e não existir execução em andamento.
          </div>
          <span id="status-badge" class="badge idle">Parado</span>
        </div>
        <div id="run-meta" class="run-meta"></div>
        <div id="feedback" class="message"></div>
        <div id="log-box" class="log-box">Aguardando execução...</div>
      </article>
    </section>
  </div>

  <script>
    let pollHandle = null;
    let currentStatus = null;

    function showMessage(text, kind = 'ok') {
      const el = document.getElementById('feedback');
      el.textContent = text;
      el.className = `message show ${kind}`;
      clearTimeout(window.__msgTimeout);
      window.__msgTimeout = setTimeout(() => {
        el.className = 'message';
      }, 3200);
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || 'Falha na requisição');
      }
      return data;
    }

    function extractEmails(text) {
      const matches = String(text || '').match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi);
      if (!matches) return [];
      const seen = new Set();
      const emails = [];
      for (const email of matches) {
        const normalized = email.trim().toLowerCase();
        if (!normalized || seen.has(normalized)) continue;
        seen.add(normalized);
        emails.push(normalized);
      }
      return emails;
    }

    function renderList(targetId, emails, listName) {
      const root = document.getElementById(targetId);
      root.innerHTML = '';
      if (!emails.length) {
        root.innerHTML = '<div class="empty">Nenhum e-mail cadastrado.</div>';
        return;
      }
      emails.forEach((email) => {
        const item = document.createElement('div');
        item.className = 'email-item';
        item.innerHTML = `
          <span>${email}</span>
          <button class="btn-danger" type="button">Excluir</button>
        `;
        item.querySelector('button').addEventListener('click', () => removeEmail(listName, email));
        root.appendChild(item);
      });
    }

    async function refreshLists() {
      const data = await api('/api/lists');
      document.getElementById('green-count').textContent = String(data.greenlist.length);
      document.getElementById('black-count').textContent = String(data.blacklist.length);
      renderList('greenlist', data.greenlist, 'greenlist');
      renderList('blacklist', data.blacklist, 'blacklist');
      await ensureAutoRun(data.greenlist.length);
    }

    async function addEmail(listName) {
      const input = document.getElementById(listName === 'greenlist' ? 'green-input' : 'black-input');
      const emails = extractEmails(input.value);
      if (!emails.length) {
        showMessage('Cole pelo menos um e-mail válido.', 'err');
        return;
      }
      for (const email of emails) {
        await api(`/api/lists/${listName}`, {
          method: 'POST',
          body: JSON.stringify({ email }),
        });
      }
      input.value = '';
      await refreshLists();
      showMessage(`${emails.length} e-mail(s) adicionados em ${listName}.`);
    }

    async function removeEmail(listName, email) {
      await api(`/api/lists/${listName}`, {
        method: 'DELETE',
        body: JSON.stringify({ email }),
      });
      await refreshLists();
      showMessage(`E-mail removido de ${listName}.`);
    }

    function renderStatus(data) {
      currentStatus = data;
      const badge = document.getElementById('status-badge');
      const meta = document.getElementById('run-meta');
      const logBox = document.getElementById('log-box');

      badge.textContent = data.running ? 'Executando' : (data.exit_code === 0 ? 'Concluído' : (data.exit_code === null ? 'Parado' : 'Finalizado com aviso'));
      badge.className = `badge ${data.running ? '' : 'idle'}`;

      const bits = [];
      if (data.run_id) bits.push(`execução: ${data.run_id}`);
      if (data.started_at) bits.push(`início: ${data.started_at}`);
      if (data.finished_at) bits.push(`fim: ${data.finished_at}`);
      if (data.exit_code !== null) bits.push(`exit code: ${data.exit_code}`);
      meta.textContent = bits.join(' • ');

      logBox.textContent = data.log_text || 'Aguardando execução...';
      logBox.scrollTop = logBox.scrollHeight;
    }

    async function ensureAutoRun(greenCount) {
      if (greenCount <= 0) return;
      if (currentStatus && currentStatus.running) return;
      try {
        const data = await api('/api/run', { method: 'POST' });
        renderStatus(data);
        showMessage('Greenlist com e-mails detectada. Execução iniciada automaticamente.');
        if (!pollHandle) {
          pollHandle = setInterval(refreshStatus, 2000);
        }
      } catch (err) {
        showMessage(err.message, 'err');
      }
    }

    async function refreshStatus() {
      const data = await api('/api/status');
      renderStatus(data);
      if (!data.running && pollHandle) {
        clearInterval(pollHandle);
        pollHandle = null;
      }
    }

    async function boot() {
      try {
        await refreshStatus();
        await refreshLists();
        if (!pollHandle) {
          pollHandle = setInterval(refreshStatus, 2000);
        }
      } catch (err) {
        showMessage(err.message, 'err');
      }
    }

    boot();
  </script>
</body>
</html>
"""


def _now_human() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _now_file() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass
class RunState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    process: subprocess.Popen[str] | None = None
    run_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    console_log_path: str | None = None
    lines: list[str] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            running = self.process is not None and self.process.poll() is None
            return {
                "running": running,
                "run_id": self.run_id,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "exit_code": self.exit_code,
                "console_log_path": self.console_log_path,
                "log_text": "".join(self.lines[-1200:]),
            }

    def append_line(self, text: str) -> None:
        with self.lock:
            self.lines.append(text)
            if len(self.lines) > 5000:
                self.lines = self.lines[-5000:]
            log_path = self.console_log_path
        if log_path:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(text)


RUN_STATE = RunState()


def _start_run() -> dict[str, Any]:
    with RUN_STATE.lock:
        if RUN_STATE.process is not None and RUN_STATE.process.poll() is None:
            return RUN_STATE.snapshot()

        run_id = _now_file()
        console_log_path = os.path.join(OUTPUT_DIR, f"panel_console_{run_id}.log")
        Path(console_log_path).write_text("", encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["DESATIVA_WATCH_NO_PAUSE"] = "1"

        cmd = [sys.executable, "-u", "-m", "src.main_consulta_tv"]
        process = subprocess.Popen(
            cmd,
            cwd=BASE_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        RUN_STATE.process = process
        RUN_STATE.run_id = run_id
        RUN_STATE.started_at = _now_human()
        RUN_STATE.finished_at = None
        RUN_STATE.exit_code = None
        RUN_STATE.console_log_path = console_log_path
        RUN_STATE.lines = [f"[{RUN_STATE.started_at}] Execução iniciada.\n"]

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            RUN_STATE.append_line(line)

    def watcher() -> None:
        exit_code = process.wait()
        RUN_STATE.append_line(f"\n[{_now_human()}] Processo finalizado com exit code {exit_code}.\n")
        with RUN_STATE.lock:
            RUN_STATE.exit_code = exit_code
            RUN_STATE.finished_at = _now_human()
            RUN_STATE.process = None

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=watcher, daemon=True).start()
    return RUN_STATE.snapshot()


class PanelHandler(BaseHTTPRequestHandler):
    server_version = "DesativaWatchPanel/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(PANEL_HTML)
            return
        if parsed.path == "/api/lists":
            self._send_json({
                "greenlist": load_greenlist(),
                "blacklist": load_blacklist(),
            })
            return
        if parsed.path == "/api/status":
            self._send_json(RUN_STATE.snapshot())
            return
        self._send_json({"error": "Rota não encontrada."}, status=404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/run":
            self._send_json(_start_run())
            return
        if parsed.path in {"/api/lists/greenlist", "/api/lists/blacklist"}:
            data = self._read_json()
            email = str(data.get("email", "")).strip().lower()
            if not email:
                self._send_json({"error": "Informe um e-mail."}, status=400)
                return
            if parsed.path.endswith("greenlist"):
                added = add_email_to_greenlist(email)
            else:
                added = add_email_to_blacklist(email)
            self._send_json({
                "ok": True,
                "changed": added,
                "greenlist": load_greenlist(),
                "blacklist": load_blacklist(),
            })
            return
        self._send_json({"error": "Rota não encontrada."}, status=404)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/api/lists/greenlist", "/api/lists/blacklist"}:
            data = self._read_json()
            email = str(data.get("email", "")).strip().lower()
            if not email:
                self._send_json({"error": "Informe um e-mail."}, status=400)
                return
            if parsed.path.endswith("greenlist"):
                removed = remove_email_from_greenlist(email)
            else:
                removed = remove_email_from_blacklist(email)
            self._send_json({
                "ok": True,
                "changed": removed,
                "greenlist": load_greenlist(),
                "blacklist": load_blacklist(),
            })
            return
        self._send_json({"error": "Rota não encontrada."}, status=404)


def run_server(host: str = "0.0.0.0", port: int = 8781) -> None:
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), PanelHandler)
    print(f"Painel disponível em http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando painel...")
    finally:
        server.server_close()


if __name__ == "__main__":
    host = os.getenv("PANEL_HOST", "0.0.0.0")
    port = int(os.getenv("PANEL_PORT", "8781"))
    run_server(host=host, port=port)
