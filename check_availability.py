# -*- coding: utf-8 -*-
"""
RTX-5090-Watcher (Cloud-Variante fuer GitHub Actions)
--------------------------------------------------------------------------
Wird von .github/workflows/watch.yml alle 5 Minuten automatisch ausgefuehrt.

Neues Produkt hinzufuegen: einfach den Produktlink in urls.txt eintragen
(eine URL pro Zeile) - egal von welchem Shop. Name und Preis werden
automatisch von der Seite gelesen (schema.org-Produktdaten, die die meisten
groesseren Shops einbetten).

Es wird nur benachrichtigt, wenn ein Produkt VERFUEGBAR ist UND der Preis
MAX_PRICE nicht ueberschreitet.

Merkt sich den letzten bekannten Status in state.json, damit nicht bei jedem
Lauf erneut eine Mail verschickt wird.

Hinweis Amazon: Amazon blockiert automatisierte Abfragen von Cloud-Servern
haeufig mit Captchas. Amazon-Links werden versucht, koennen aber oefter als
"Status unbekannt" enden als bei anderen Shops.
"""

import json
import os
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse

import requests

HERE = Path(__file__).parent
URLS_FILE = HERE / "urls.txt"
STATE_FILE = HERE / "state.json"
HEARTBEAT_FILE = HERE / "last_checked.txt"

# Nur benachrichtigen, wenn der Preis hoechstens so hoch ist (in Euro).
MAX_PRICE = float(os.environ.get("MAX_PRICE", "3850"))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "de-DE,de;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Shopspezifischer Sperrtext, der zusaetzlich zu den schema.org-Daten
# geprueft wird, weil manche Shops im JSON-LD faelschlich "InStock" melden,
# obwohl der Artikel gerade nicht kaufbar ist (bei Alternate.de beobachtet).
DOMAIN_UNAVAILABLE_TEXT = {
    "www.alternate.de": "kann derzeit nicht gekauft werden",
    "alternate.de": "kann derzeit nicht gekauft werden",
}

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


def _walk_json(node):
    """Liefert nacheinander alle dict-Knoten in einer beliebig verschachtelten JSON-Struktur."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_json(item)


def extract_price_and_availability(html):
    """
    Liest Preis + Verfuegbarkeit aus eingebetteten schema.org-Produktdaten
    (JSON-LD "application/ld+json"), so wie es die meisten groesseren
    Onlineshops (Alternate, Cyberport, Kaufland, MediaMarkt, Saturn, ...)
    einbetten.

    Rueckgabe: (price: float|None, availability: bool|None)
    availability=True  -> InStock/PreOrder/BackOrder (kaufbar/bestellbar)
    availability=False -> OutOfStock
    availability=None  -> nicht gefunden
    """
    best_price = None
    availability = None

    for match in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>([\s\S]*?)</script>', html
    ):
        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        for node in _walk_json(data):
            node_type = node.get("@type")
            types = node_type if isinstance(node_type, list) else [node_type]
            if not any(isinstance(t, str) and "Product" in t for t in types):
                continue

            offers = node.get("offers")
            offer_list = offers if isinstance(offers, list) else [offers] if offers else []

            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                price_raw = offer.get("price") or offer.get("lowPrice")
                if price_raw is not None:
                    try:
                        price_val = float(str(price_raw).replace(",", "."))
                        if best_price is None or price_val < best_price:
                            best_price = price_val
                    except ValueError:
                        pass

                avail_raw = offer.get("availability", "")
                if isinstance(avail_raw, str):
                    if "InStock" in avail_raw or "PreOrder" in avail_raw or "BackOrder" in avail_raw:
                        availability = True
                    elif "OutOfStock" in avail_raw or "Discontinued" in avail_raw:
                        availability = False

    # Fallback ueber generische Meta-Tags, falls kein JSON-LD gefunden wurde.
    if best_price is None:
        m = re.search(r'<meta[^>]*property="product:price:amount"[^>]*content="([^"]+)"', html)
        if not m:
            m = re.search(r'<meta[^>]*itemprop="price"[^>]*content="([^"]+)"', html)
        if m:
            try:
                best_price = float(m.group(1).replace(",", "."))
            except ValueError:
                pass

    return best_price, availability


def extract_name(html):
    m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
    if m:
        import html as html_module
        return html_module.unescape(m.group(1).strip())
    m = re.search(r"<title>([^<]+)</title>", html)
    if m:
        import html as html_module
        return html_module.unescape(m.group(1).strip())
    return None


def check_product(url):
    """
    Rueckgabe: dict mit name, price, buyable (bool|None).
    buyable=None bedeutet: Status konnte nicht sicher bestimmt werden
    (Netzwerkfehler, Blockade, oder kein Preis/Verfuegbarkeit auslesbar).
    """
    domain = urlparse(url).netloc.lower()

    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
    except requests.RequestException as e:
        log(f"  ! Netzwerkfehler: {e}")
        return {"name": url, "price": None, "buyable": None}

    if resp.status_code != 200:
        log(f"  ! HTTP {resp.status_code} (evtl. Bot-Schutz, z.B. bei Amazon)")
        return {"name": url, "price": None, "buyable": None}

    html = resp.text
    if len(html) < 3000:
        log(f"  ! Antwort verdaechtig kurz ({len(html)} Zeichen) - moegliche Blockade")
        return {"name": url, "price": None, "buyable": None}

    name = extract_name(html) or url
    price, availability = extract_price_and_availability(html)

    # Shopspezifische Zusatzpruefung (siehe DOMAIN_UNAVAILABLE_TEXT oben).
    unavailable_text = DOMAIN_UNAVAILABLE_TEXT.get(domain)
    if unavailable_text and unavailable_text.lower() in html.lower():
        availability = False

    if price is None or availability is None:
        log(f"  ? Preis/Verfuegbarkeit nicht sicher auslesbar (price={price}, availability={availability})")
        return {"name": name, "price": price, "buyable": None}

    buyable = availability and price <= MAX_PRICE
    return {"name": name, "price": price, "buyable": buyable}


def send_mail(name, url, price):
    msg = EmailMessage()
    msg["Subject"] = f"VERFUEGBAR unter {MAX_PRICE:.0f} EUR: {name}"
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    now = datetime.now(timezone.utc).astimezone()
    msg.set_content(
        f"Gute Nachricht!\n\n"
        f"{name} ist fuer {price:.2f} EUR verfuegbar (Limit: {MAX_PRICE:.0f} EUR).\n\n"
        f"Direkt zum Produkt:\n{url}\n\n"
        f"Gefunden am {now:%d.%m.%Y um %H:%M:%S} Uhr.\n"
    )
    msg.add_alternative(
        f"""\
        <html><body style="font-family:Segoe UI,Arial,sans-serif">
          <h2 style="color:#158000">Verfuegbar &amp; im Budget!</h2>
          <p><b>{name}</b></p>
          <p style="font-size:20px"><b>{price:.2f} EUR</b> (Limit: {MAX_PRICE:.0f} EUR)</p>
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

    log(f"Preis-Limit: {MAX_PRICE:.2f} EUR")

    for url in urls:
        log(f"Pruefe: {url}")
        result = check_product(url)
        name, price, buyable = result["name"], result["price"], result["buyable"]

        if buyable is True:
            price_str = f"{price:.2f} EUR" if price is not None else "?"
            log(f"  => KAUFBAR im Budget! ({name}, {price_str})")
            if not state.get(url, False):
                try:
                    send_mail(name, url, price)
                except Exception as e:
                    log(f"  ! Mailversand fehlgeschlagen: {e}")
                    continue
                state[url] = True
                changed = True
            else:
                log("  (bereits benachrichtigt)")
        elif buyable is False:
            price_str = f"{price:.2f} EUR" if price is not None else "?"
            log(f"  => nicht kaufbar/zu teuer ({name}, {price_str})")
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
