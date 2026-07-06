# RTX 5090 Verfuegbarkeits-Watcher

Prueft alle 5 Minuten automatisch (via GitHub Actions) eine Liste von
Produktlinks - egal von welchem Shop - und schickt eine E-Mail, sobald ein
Produkt **verfuegbar** ist **und** der Preis unter dem eingestellten Limit
liegt.

## Neues Produkt hinzufuegen

Einfach den Produktlink in [urls.txt](urls.txt) in eine neue Zeile eintragen
und committen. Name und Preis werden automatisch von der Seite gelesen
(schema.org-Produktdaten, die die meisten groesseren Shops einbetten -
Alternate, Cyberport, Kaufland, MediaMarkt, Saturn, notebooksbilliger, ...).

**Wichtig:** Es sollten Links zu den offiziellen Produktseiten von normalen
Haendlern sein (nicht zu privaten Kleinanzeigen wie eBay Kleinanzeigen) -
nur so ist sichergestellt, dass es sich um neue Ware mit ausgewiesener
Umsatzsteuer handelt.

**Amazon:** Amazon blockiert automatisierte Abfragen von Cloud-Servern
haeufig mit Captchas. Amazon-Links werden versucht, das Ergebnis kann aber
haeufiger "Status unbekannt" sein als bei anderen Shops.

## Preis-Limit aendern

In [.github/workflows/watch.yml](.github/workflows/watch.yml) den Wert von
`MAX_PRICE` anpassen (aktuell 3850 Euro).

## Einmaliges Setup

1. Repo-Secrets anlegen unter **Settings -> Secrets and variables -> Actions**:
   - `SMTP_USER` = deine iCloud-Adresse (z. B. `fdaxner@icloud.com`)
   - `SMTP_PASSWORD` = ein **app-spezifisches Passwort** von
     [account.apple.com](https://account.apple.com) -> Anmeldung & Sicherheit
     -> App-spezifische Passwoerter (das normale iCloud-Passwort funktioniert
     hier nicht)
2. Fertig. Der Workflow unter `.github/workflows/watch.yml` laeuft danach von
   selbst alle 5 Minuten.

Manuell testen: Tab **Actions** -> Workflow "RTX 5090 Verfuegbarkeits-Watcher"
-> **Run workflow**.
