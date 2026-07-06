# RTX 5090 Verfuegbarkeits-Watcher

Prueft alle 5 Minuten automatisch (via GitHub Actions) eine Liste von
Produktlinks und schickt eine E-Mail, sobald ein Produkt **verfuegbar** ist
**und** der Preis unter dem eingestellten Limit liegt.

## Warum Geizhals statt einzelner Shops?

Die meisten grossen Haendler (Amazon, Kaufland, notebooksbilliger,
Cyberport, MediaMarkt/Saturn, Mindfactory, Caseking, ...) blockieren
automatisierte Abfragen oder laden Preise erst per JavaScript nach - ein
einfaches Skript kommt dort nicht zuverlaessig durch (das wurde getestet:
alle genannten Shops antworten mit Fehler 403 oder liefern keine Preisdaten).

Die Preisvergleichsseite [Geizhals](https://geizhals.de) wird dagegen nicht
blockiert und zeigt automatisch den guenstigsten aktuellen Preis ueber viele
Haendler hinweg direkt im Seitentitel an. Eine einzige Geizhals-Seite pro
Hersteller deckt dadurch indirekt sehr viele Shops gleichzeitig ab.

**Alternate.de ist die Ausnahme:** dort funktioniert die direkte Abfrage
zuverlaessig, deshalb sind zusaetzlich zwei direkte Alternate-Links in
[urls.txt](urls.txt) enthalten.

## Neues Produkt/Modell hinzufuegen

- **Ueber Geizhals (empfohlen fuer neue Hersteller/Modelle):** die passende
  Vergleichsseite suchen (z. B. "geizhals.de MSI RTX 5090") und den Link in
  [urls.txt](urls.txt) eintragen.
- **Direkter Shop-Link:** funktioniert nur zuverlaessig, wenn der Shop
  schema.org-Produktdaten einbettet und keinen Bot-Schutz hat (bei Alternate
  bestaetigt). Bei anderen Shops landet das Ergebnis meist bei "Status
  unbekannt".

Name und Preis werden in beiden Faellen automatisch ausgelesen.

**Wichtig:** Nur Links zu offiziellen Haendler-/Vergleichsseiten verwenden
(keine privaten Kleinanzeigen wie eBay Kleinanzeigen) - so ist sichergestellt,
dass es sich um neue Ware mit ausgewiesener Umsatzsteuer handelt.

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
