# FH-SWF MCP Server

Ein Model Context Protocol (MCP) Server für die Fachhochschule Südwestfalen, entwickelt mit FastMCP, der zentrale Hochschulinformationen über eine einheitliche Tool-Schnittstelle bereitstellt.

## Schnelleinstieg

### Voraussetzungen
- Python 3.13+
- Neo4j Datenbank

### Installation
#### lokale Installation
```bash
# Virtuelles Environment erstellen und Abhängigkeiten installieren
uv venv
uv sync

# Environment aktivieren (Windows)
.venv\Scripts\activate

# MCP-Server starten
uv run main.py
```

### Konfiguration
`.env` Datei erstellen:
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
CALENDLY_API_TOKEN=your_token  # optional für die Verwendung von Calendly
BIBLIOTHEK_API_KEY=your_token  # optional für die Suche in der Bibliothek
FASTMCP_LOG_LEVEL=INFO  # optional: DEBUG, INFO, WARNING, ERROR, CRITICAL (Standard: INFO)
MCP_KEY_FILE_PATH=.keys/mcp-private.json  # Pfad zur JWE Private Key Datei (Kubernetes)
MCP_ISSUER=your_url # Die Server URL auf der die applikation läuft
```

### Server starten
```bash
# Environment aktivieren
.venv\Scripts\activate  # Windows
# oder
source .venv/bin/activate  # Linux/Mac

# Anwendung starten
uv run main.py
```

## Verfügbare Tools

Die Implementierung enthält Tools zum Zugriff auf Informationen aus den folgenden Bereichen:

| Tool | Beschreibung |
|------|-------------|
| **Studiengänge** | Informationen zu Studienprogrammen und Prüfungsordnungen |
| **VPIS** | Vorlesungsverzeichnis: Kurse, Räume, Dozenten, Termine |
| **Mensa** | Speiseplan der Mensa an 4 Standorten (Iserlohn, Hagen, Meschede, Soest) |
| **Bibliothek** | Bibliotheksinformationen und -ressourcen |
| **FAQ** | Häufig gestellte Fragen der FH-SWF |
| **News & Events** | Nachrichten und Veranstaltungen |
| **Calendly** | Verfügbare Termine für Besprechungen |
| **Portale** | Informationen zu den Login Portalen |

## Projektstruktur

```
ProjektKI/
├── main.py                                     # Haupteinstiegspunkt — startet den MCP-Server
├── pyproject.toml                              # Projektmetadaten & Abhängigkeiten (für `uv` / packaging)
├── uv.lock                                     # Lockfile für `uv`
├── requirements.txt                            # Python Abhängigkeiten
├── .env                                        # Lokale Umgebungsvariablen (nicht ins VCS)
├── Dockerfile                                  # Docker-Build-Anweisungen
├── k8s/
│   ├── deployment.yaml                         # K8s-Deployment
│   ├── ingress.yaml                            # K8s-Ingress
│   ├── kustomization.yaml                      # Kustomize-Konfiguration
│   ├── neo4j.yaml                              # Neo4j-Konfiguration
│   ├── pvc.yaml                                # Persistent-Volume-Konfiguration
│   └── secret.yaml                             # Kubernetes-Secret
├── src/                                        # Quellcode des MCP-Servers
│   ├── __init__.py                             # Initialisiert `mcp` und `Neo4jHandler`
│   ├── bib_mcp.py                              # Bibliothekssuche
│   ├── calendly_mcp.py                         # Calendly-Integration
│   ├── faq_mcp.py                              # FAQ-Tools
│   ├── graphdata_mcp.py                        # Zugriff auf Studiengangsdaten (Neo4j)
│   ├── mensa.py                                # Mensa-Speiseplan
│   ├── news_events_mcp.py                      # News & Events Tools
│   ├── portale_mcp.py                          # Loginportal-Informationen
│   ├── vpis_mcp.py                             # VPIS Tools
│   └── common/                                 # Gemeinsame Utilities und Handler
│       ├── __init__.py
│       ├── Neo4jHandler.py                     # Wrapper/Helper für Neo4j-Operationen
│       ├── neo4j_help_function.py              # Hilfsfunktionen für Neo4j
│       ├── pdfCrawler.py                       # PDF-Crawler
│       ├── study_programs.py                   # Studiengangsinformationen
│       ├── calendly.py                         # Calendly-API-Wrapper
│       └── vpis.py                             # VPIS Daten laden
├── data_preprocessing/                         # Skripte und Notebooks zur Datenaufbereitung
│   └── scripts/
│       ├── graphdatenbank.ipynb                # Aufbau der Graphdatenbank
│       ├── employee_information.py             # Mitarbeitenden Informationen
│       ├── PDF_Preprocess.ipynb                # Notebook zum Vorverarbeiten der Modulhandbücher 
│       ├── TableExtraction.ipynb               # Notebook zur Extraktion von Modulinformationen aus den vorverarbeiteten Modulhandbüchern 
│       ├── docling_pruefungsordnungen.ipynb    # Notebook zur Umwandlung der Prüfungsordnungen in Markdown-Dateien
│       └── vpis.ipynb                          # VPIS Daten auslesen
└── data/                                       # Daten
```

## Entwicklung

### Neues Tool hinzufügen
1. `src/new_tool_mcp.py` erstellen
3. Funktionen mit `@mcp.tool()` dekorieren
4. In `main.py` importieren

### Datenverarbeitung
- `data_preprocessing/scripts/graphdatenbank.ipynb` - Notebook zum Einfügen der Informationen in die Datenbank
- `data_preprocessing/scripts/employee_information.py` - Sammlung von Mitarbeiterdaten
- `data_preprocessing/scripts/vpis.ipynb` - Notebook zum Auslesen von Informationen aus dem VPIS
- `data_preprocessing/scripts/PDF_Preprocess.ipynb` - Notebook zum Vorverarbeiten der Modulhandbücher
- `data_preprocessing/scripts/TableExtraction.ipynb` - Notebook zur Extraktion von Modulinformationen aus den vorverarbeiteten Modulhandbüchern
- `data_preprocessing/scripts/docling_pruefungsordnungen.ipynb` - Notebook zur Umwandlung der Prüfungsordnungen in Markdown-Dateien

## Authentifizierung (mcp-auth-middleware)

Der MCP-Server verwendet [mcp-auth-middleware](https://pypi.org/project/mcp-auth-middleware/) für die JWE-Token-Authentifizierung. Damit können Benutzerinformationen (Claims) end-to-end verschlüsselt vom Client an den Server übertragen und in Tools über `get_user()` abgerufen werden.

### Lokale Entwicklung

#### 1. RSA-Schlüsselpaar generieren

```bash
mcp-auth-middleware generate
```

Ausgabe:
```
Keys generated (JWKS format):
  Private: .keys/mcp-private.json
  Public:  .keys/mcp-public.json
```

> **Wichtig:** `.keys/` sofort in `.gitignore` eintragen.

#### 2. `.env` Datei erweitern

```env
MCP_KEY_FILE_PATH=.keys/mcp-private.json
```

### Kubernetes Deployment

#### 1. Schlüssel generieren und als Secret anlegen

```bash
mcp-server-keys | kubectl apply -f -
```

Danach lokale Schlüssel sicher löschen:

```bash
mcp-auth-middleware clean
```

#### 2. Alternative: Schlüssel über Remote-GUI anlegen (ohne kubectl / deployment.yaml)

Anleitung für die Einrichtung über eine Kubernetes-Web-Oberfläche (Rancher, Kubernetes Dashboard, Lens, etc.).

##### Schritt 1: Schlüssel lokal generieren

```bash
uv run mcp-auth-middleware generate
```

Erzeugt `.keys/mcp-private.json` (Private Key) und `.keys/mcp-public.json` (Public Key) im JWKS-Format.

##### Schritt 2: Secret in der GUI anlegen

1. In der Kubernetes-GUI zum richtigen **Namespace** navigieren
2. **Secrets** → **Create** → Typ **Opaque**
3. **Name:** `mcp-server-keys`
4. **Key/Value-Paar:**
   - **Key:** `mcp_jwks`
   - **Value:** Kompletten Inhalt von `.keys/mcp-private.json` einfügen

> **Wichtig:** Der Key muss exakt `mcp_jwks` lauten.

Falls die GUI einen **YAML-Editor** bietet, alternativ:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-server-keys
  namespace: <DEIN_NAMESPACE>
type: Opaque
stringData:
  mcp_jwks: |
    <Inhalt von .keys/mcp-private.json hier einfügen>
```

##### Schritt 3: Deployment prüfen

In der GUI unter **Deployments** → `fh-swf-mcp-deployment` → **Edit** sicherstellen:

| Einstellung | Wert |
|-------------|------|
| **Volume** (Secret) | Name: `mcp-secret-volume`, Secret: `mcp-server-keys`, Items: `mcp_jwks` → `key.json` |
| **Volume Mount** | Pfad: `/etc/mcp/secrets`, Read Only: `true` |
| **Env-Variable** | `MCP_KEY_FILE_PATH` = `/etc/mcp/secrets/key.json` |

##### Schritt 4: Deployment neu starten

In der GUI **Rollout Restart** / **Redeploy** für `fh-swf-mcp-deployment` auslösen.

##### Schritt 5: Aufräumen & Prüfen

Lokale Schlüssel löschen:
```bash
mcp-auth-middleware clean
```

In der GUI prüfen:
- Pod-Status = `Running`
- Keine Key-Fehlermeldungen in den Pod-Logs

> **Troubleshooting:**
> - **CrashLoopBackOff / FileNotFoundError:** Volume-Mount oder `MCP_KEY_FILE_PATH` falsch konfiguriert
> - **Invalid key:** JSON-Inhalt von `mcp_jwks` prüfen (keine abgeschnittenen Zeichen, kein doppeltes Base64-Encoding)
> - **Secret nicht sichtbar:** Muss im selben Namespace wie das Deployment liegen
