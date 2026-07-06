# -*- coding: utf-8 -*-
"""
Alternate.de Verfuegbarkeits-Watcher (Cloud-Variante fuer GitHub Actions)
--------------------------------------------------------------------------
Wird von .github/workflows/watch.yml alle 5 Minuten automatisch ausgefuehrt.

Neues Produkt hinzufuegen: einfach den Link in urls.txt eintragen (eine URL
pro Zeile). Der Produktname wird automatisch von der Seite gelesen.

Merkt sich den letzten bekannten Status in state.json, damit nicht bei jedem
Lauf erneut eine Mail verschickt wird.
"""

import json
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

import requests

HERE = Path(__file__).parent
URLS_FILE = HERE / "urls.txt"
STATE_FILE = HERE / "state.json"
HEARTBEAT_FILE = HERE / "last_checked.txt"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9"}

# Solange dieser Text auf der Seite steht, ist das Produkt NICHT kaufbar.
UNAVAILABLE_TEXT = "kann derzeit nicht gekauft werden"

# E-Mail-Konfiguration kommt aus Umgebungsvariablen (siehe workflow-Datei).
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.mail.me.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER)
MAIL_TO = os.environ.get("MAIL_TO", "fdaxner@icloud.com")


def log(msg):
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC] {msg}", flush=True)


def load_urls():
    urls = []
    for line in URLS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def check_product(url):
    """
    Rueckgabe: (name, available) mit available in {True, False, None}.
    None bedeutet: Status konnte nicht sicher bestimmt werden.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    except requests.RequestException as e:
        log(f"  ! Netzwerkfehler bei {url}: {e}")
        return url, None

    if resp.status_code != 200:
        log(f"  ! HTTP {resp.status_code} bei {url}")
        return url, None

    html = resp.text
    if len(html) < 5000:
        log(f"  ! Antwort verdaechtig kurz ({len(html)} Zeichen) - moegliche Blockade")
        return url, None

    title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    name = title_match.group(1).strip() if title_match else url

    blocked = UNAVAILABLE_TEXT.lower() in html.lower()
    return name, (not blocked)


def send_mail(name, url):
    msg = EmailMessage()
    msg["Subject"] = f"WIEDER VERFUEGBAR: {name}"
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    now = datetime.now(timezone.utc).astimezone()
    msg.set_content(
        f"Gute Nachricht!\n\n"
        f"{name} ist bei Alternate wieder kaufbar.\n\n"
        f"Direkt zum Produkt:\n{url}\n\n"
        f"Gefunden am {now:%d.%m.%Y um %H:%M:%S} Uhr.\n"
    )
    msg.add_alternative(
        f"""\
        <html><body style="font-family:Segoe UI,Arial,sans-serif">
          <h2 style="color:#158000">Wieder verfuegbar!</h2>
          <p><b>{name}</b> ist bei Alternate wieder kaufbar.</p>
          <p><a href="{url}" style="font-size:18px;font-weight:bold;color:#0a58ca">
                &#10148; Jetzt zum Produkt</a></p>
          <p style="color:#888">Gefunden am {now:%d.%m.%Y um %H:%M:%S} Uhr.</p>
        </body></html>
        """,
        subtype="html",
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    log(f"  -> Mail verschickt an {MAIL_TO}")


def main():
    urls = load_urls()
    state = load_state()
    changed = False

    for url in urls:
        log(f"Pruefe: {url}")
        name, available = check_product(url)

        if available is True:
            log(f"  => VERFUEGBAR! ({name})")
            if not state.get(url, False):
                try:
                    send_mail(name, url)
                except Exception as e:
                    log(f"  ! Mailversand fehlgeschlagen: {e}")
                    continue
                state[url] = True
                changed = True
            else:
                log("  (bereits benachrichtigt)")
        elif available is False:
            log(f"  => nicht verfuegbar ({name})")
            if state.get(url, False) is not False:
                changed = True
            state[url] = False
        else:
            log("  => Status unbekannt, ueberspringe (Status bleibt unveraendert)")

    if changed:
        save_state(state)
        log("state.json aktualisiert")

    # Heartbeat-Datei wird bei jedem Lauf geschrieben. Das sorgt fuer einen
    # regelmaessigen Commit, damit GitHub den Scheduled Workflow nicht wegen
    # Inaktivitaet nach 60 Tagen automatisch deaktiviert.
    HEARTBEAT_FILE.write_text(
        f"Letzter Check: {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
