# Social Media Poster

Postet ein Bild-Set + Text gleichzeitig als:
- Facebook-Beitrag mit mehreren Bildern (Seite "May-Finanz")
- Instagram-Karussell (max. 10 Bilder)
- LinkedIn-Beitrag (nur Titelbild, LinkedIn unterstützt kein natives Mehrbild-Post)

## Benutzung

1. Neuen Ordner unter `posts/pending/` anlegen, z.B. `posts/pending/2026-07-22-sommerzinsen/`
2. Bilder hineinlegen, nummeriert in gewünschter Reihenfolge: `01.jpg`, `02.jpg`, ...
3. Datei `caption.txt` mit dem Post-Text in denselben Ordner legen
4. Commit + Push auf `main`

Das startet automatisch den GitHub-Actions-Workflow, der auf allen drei Plattformen postet.
Nach erfolgreichem Posten wird der Ordner automatisch nach `posts/done/` verschoben (per Commit).
Schlägt ein Post fehl, bleibt er in `posts/pending/` liegen und eine `error.log` beschreibt den Fehler.

Ein manueller Lauf ist auch über den "Run workflow"-Button unter GitHub → Actions → "Post to Facebook, Instagram & LinkedIn" möglich.

## Einmaliges Setup: GitHub Secrets

Unter **Repo → Settings → Secrets and variables → Actions → New repository secret** folgende Secrets anlegen:

| Secret | Wert |
|---|---|
| `FB_PAGE_ID` | `233685493343710` (May-Finanz Facebook-Seite) |
| `FB_PAGE_ACCESS_TOKEN` | siehe unten |
| `IG_USER_ID` | `17841428461594051` (verknüpftes Instagram-Konto matthias.may.finanz) |
| `LINKEDIN_PERSON_URN` | siehe unten, Format `urn:li:person:XXXXXXX` |
| `LINKEDIN_ACCESS_TOKEN` | siehe unten |

Das Repo muss **Public** sein (Settings → General → Danger Zone → "Change visibility"), damit die
Bild-URLs (`raw.githubusercontent.com/...`) von Facebook/Instagram/LinkedIn abgerufen werden können.
Das ist unproblematisch, da die Bilder ohnehin für öffentliche Social-Media-Posts gedacht sind.

### Facebook Page Access Token (auch für Instagram genutzt)

1. Auf [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer/) gehen, mit deinem Facebook-Account einloggen
2. Eine eigene App auswählen/erstellen (Business-Typ)
3. Berechtigungen hinzufügen: `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`
4. "Generate Access Token" klicken, Login bestätigen
5. Diesen User-Token gegen einen **langlebigen Token** tauschen (Tool: "Access Token Debugger" → "Extend Access Token")
6. Mit dem langlebigen User-Token einen Page-Token holen: `GET /me/accounts?access_token=<LANGLEBIGER_TOKEN>` → den `access_token` in der Antwort für die Seite "May-Finanz" nehmen — das ist `FB_PAGE_ACCESS_TOKEN`. Page-Tokens aus einem langlebigen User-Token laufen praktisch nicht ab.

### LinkedIn Access Token

1. Auf [developer.linkedin.com](https://www.linkedin.com/developers/apps) eine neue App erstellen (an eine LinkedIn-Company-Page gebunden, z.B. May-Finanz)
2. Unter "Products" das Produkt **"Share on LinkedIn"** hinzufügen (sofort verfügbar, keine Freigabe nötig)
3. Unter "Auth" die Redirect-URL `https://www.linkedin.com/developers/tools/oauth/redirect` eintragen (LinkedIns eigenes Test-Tool)
4. Im "OAuth 2.0 tools"-Tab einen dreistufigen Login mit Scope `w_member_social` durchführen → liefert einen Access Token (60 Tage gültig, danach muss dieser Schritt wiederholt werden)
5. Die eigene Person-URN herausfinden: `GET https://api.linkedin.com/v2/userinfo` mit dem Token im `Authorization: Bearer ...`-Header → Feld `sub` ist deine Member-ID → `urn:li:person:<sub>`

## Wartung

- LinkedIn-Token läuft nach 60 Tagen ab → Schritt 4 oben wiederholen und `LINKEDIN_ACCESS_TOKEN`-Secret aktualisieren
- Facebook Page Token aus einem langlebigen User-Token läuft i.d.R. nicht ab, außer das Passwort/die App-Berechtigung wird geändert
