# Alternate Verfuegbarkeits-Watcher

Prueft alle 5 Minuten automatisch (via GitHub Actions) eine Liste von
Alternate-Produktlinks und schickt eine E-Mail, sobald ein Produkt wieder
kaufbar ist.

## Neues Produkt hinzufuegen

Einfach den Alternate-Produktlink in [urls.txt](urls.txt) in eine neue Zeile
eintragen und committen. Der Produktname wird automatisch von der Seite
gelesen, keine weitere Konfiguration noetig.

## Einmaliges Setup

1. Repo-Secrets anlegen unter **Settings -> Secrets and variables -> Actions**:
   - `SMTP_USER` = deine iCloud-Adresse (z. B. `fdaxner@icloud.com`)
   - `SMTP_PASSWORD` = ein **app-spezifisches Passwort** von
     [account.apple.com](https://account.apple.com) -> Anmeldung & Sicherheit
     -> App-spezifische Passwoerter (das normale iCloud-Passwort funktioniert
     hier nicht)
2. Fertig. Der Workflow unter `.github/workflows/watch.yml` laeuft danach von
   selbst alle 5 Minuten.

Manuell testen: Tab **Actions** -> Workflow "Alternate Verfuegbarkeits-Watcher"
-> **Run workflow**.
