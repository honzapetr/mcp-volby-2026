# 🇨🇿 MCP Server: Volby 2026 v České republice

[![CI/CD Pipeline](https://github.com/honzapetr/mcp-volby-2026/actions/workflows/ci.yml/badge.svg)](https://github.com/honzapetr/mcp-volby-2026/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker Compose](https://img.shields.io/badge/docker--compose-ready-blue.svg)](docker-compose.yml)
[![Protocol](https://img.shields.io/badge/MCP-1.30+-green.svg)](https://modelcontextprotocol.io/)

Robustní, modulární a plně parametrizovaný **Model Context Protocol (MCP)** server a **REST API** s živým napojením na oficiální volební feedy **Českého statistického úřadu (ČSÚ)** (`volby.gov.cz` / `volby.cz`) pro volby v České republice v říjnu 2026.

Umožňuje AI modelům v reálném čase přistupovat ke sčítání hlasů, které začíná v sobotu **10. října 2026 ve 14:00**, sledovat volební účast, počty sečtených okrsků, postup do 2. kola Senátu i rozdělení mandátů v zastupitelstvech všech obcí a statutárních měst ČR.

---

## 🌐 Živý běh (Production Instance)

Server je aktivní na Azure cloudu s platným **Let's Encrypt HTTPS** certifikátem:
* **Základní HTTPS URL**: `https://volby2026-honzapetr.polandcentral.cloudapp.azure.com`
* **Healthcheck**: `https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/health`
* **MCP SSE Endpoint**: `https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/sse`
* **MCP Streamable HTTP Endpoint**: `https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/mcp`
* **REST OpenAPI specifikace**: `https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/openapi.json`
* **Swagger UI dokumentace**: `https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/docs`

---

## 🔌 Jak napojit MCP server na AI klienty

Server podporuje **všechny moderní MCP i REST protokoly**:
- **SSE Transport** (`GET /sse`, `POST /messages`) pro Claude Code
- **Streamable HTTP JSON-RPC 2.0** (`POST /sse`, `POST /mcp`) pro Google Antigravity, Cursor, Codex
- **REST OpenAPI 3.0** (`/api/*`, `/openapi.json`) pro ChatGPT Custom GPT Actions

### 1. Claude Code (CLI)
Spusťte v terminálu:
```bash
claude mcp add --transport sse volby-2026 https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/sse
```

### 2. Google Antigravity & Antigravity 2.0
Antigravity používá moderní Streamable HTTP protokol (JSON-RPC over HTTP POST).

1. Otevřete centrální konfigurační soubor MCP serverů:
   * **Windows**: `%USERPROFILE%\.gemini\config\mcp_config.json`
   * **Linux/macOS**: `~/.gemini/config/mcp_config.json`
2. Přidejte záznam do sekce `"mcpServers"`:
   ```json
   {
     "mcpServers": {
       "volby-2026": {
         "serverUrl": "https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/sse"
       }
     }
   }
   ```
3. V nastavení projektu (Project Settings -> Permission Grants) povolte:
   ```json
   "permissionGrants": {
     "allow": ["mcp(volby-2026)"]
   }
   ```
4. V chatu Antigravity stačí napsat `@` nebo se rovnou zeptat na stav voleb.

### 3. Cursor & VSCode (Claude / MCP Extension)
V konfiguračním souboru Cursor MCP (`~/.cursor/mcp.json` nebo v nastavení IDE):
```json
{
  "mcpServers": {
    "volby-2026": {
      "url": "https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/sse"
    }
  }
}
```

### 4. ChatGPT (Custom GPT Actions)
1. V editoru [Custom GPT](https://chatgpt.com/gpts/editor) zvolte **Create new action**.
2. Do pole **Import from URL** vložte:
   ```
   https://volby2026-honzapetr.polandcentral.cloudapp.azure.com/openapi.json
   ```
3. ChatGPT automaticky naimportuje všechny endpointy. Pokud nepoužíváte `API_KEY`, v Authentication nechte **None**.

---

## 🛠️ Dostupné MCP nástroje (Tools)

| Nástroj | Parametry | Popis |
| :--- | :--- | :--- |
| `get_election_overview` | *žádné* | Celkový přehled o sčítání v ČR: stav po 14:00, celková účast, % sečtených okrsků pro Senát a zastupitelstva. |
| `get_senate_results` | `obvod` *(volitelný: str / int)* | Výsledky Senátu za všech 27 obvodů nebo konkrétní obvod (např. `"Cheb"`, `3`, `"Praha 5"`). Zobrazí hlasy, %, zvolení v 1. kole (>50 %) či postupující do 2. kola. |
| `get_municipal_results` | `obec` *(povinný: str)* | Výsledky pro konkrétní město či obec (např. `"Praha"`, `"Brno"`, `"Ostrava"` nebo kód `"554782"`). Vrátí účast, rozdělení mandátů v zastupitelstvu a pořadí stran. |
| `search_municipality_or_district` | `query` *(povinný)*, `limit` *(výchozí 15)* | Inteligentní vyhledávač obcí a senátních obvodů bez ohledu na diakritiku a velikost písmen. |
| `get_live_counting_progress` | *žádné* | Telemetrie a rychlost sčítání: tempo zpracování okrsků a textová zpráva o aktuálním průběhu. |

---

## 🖥️ Zprovoznění na vlastním virtuálním stroji (VM)

Aplikaci můžete nasadit na libovolný virtuální server (Azure, Hetzner, AWS, DigitalOcean, VPS) s libovolnou Linux distribucí (Ubuntu 24.04 LTS doporučeno).

### 1. Požadavky na server
* **Minimální konfigurace**: 1 vCPU, 1 GB RAM (např. Azure `Standard_B1s` cca 8 EUR/měsíc).
* **Otevřené porty ve firewallu / NSG**:
  * `22` (SSH)
  * `80` (HTTP – nutné pro automatické vystavení Let's Encrypt SSL certifikátu)
  * `443` (HTTPS – šifrovaný provoz MCP a API)
* **Nainstalovaný Docker a Docker Compose**:
  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER
  ```

### 2. Klonování a konfigurace
```bash
git clone https://github.com/honzapetr/mcp-volby-2026.git ~/app
cd ~/app
cp .env.example .env
```

V souboru `.env` nastavte svou doménu (např. Azure FQDN nebo vlastní doménu):
```env
DOMAIN=moje-volby-domena.cloudapp.azure.com
PORT=8088
API_KEY=                     # Volitelné: ponechte prázdné pro veřejný server, nebo zadejte tajný Bearer token
CACHE_TTL_SECONDS=30
```

### 3. Spuštění přes Docker Compose
```bash
docker compose up -d --build
```

**Co se automaticky stane:**
1. Zkompiluje se odlehčený produkční Python kontejner `mcp-volby-2026`.
2. Nastartuje se reverzní proxy a load balancer `caddy`.
3. Caddy automaticky kontaktuje Let's Encrypt, vystaví platný TLS certifikát pro vaši doménu a přesměruje veškerý HTTP provoz na zabezpečené HTTPS.

### 4. Správa a údržba
* **Kontrola stavu**: `docker compose ps`
* **Sledování živých logů**: `docker compose logs -f`
* **Zastavení serveru**: `docker compose down`
* **Restart po změně konfigurace**: `docker compose up -d --build`

---

## 🚀 Automatické nasazení přes GitHub Actions (CI/CD)

Repozitář obsahuje workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml), které při každém pushi do větve `main` provede:
1. Automatické testy (Python 3.11 a 3.12).
2. Ověření sestavitelnosti Docker obrazu.
3. Bezpečné nasazení na váš virtuální server přes SSH (`docker compose up -d --build`).
4. Živý healthcheck proti produkční URL.

### Nastavení CI/CD pro vlastní repozitář:
1. Na virtuálním serveru vygenerujte samostatný deploy klíč:
   ```bash
   ssh-keygen -t ed25519 -N '' -f ~/.ssh/github_actions -C 'github-actions-deploy'
   cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys
   ```
2. Zobrazte privátní klíč:
   ```bash
   cat ~/.ssh/github_actions
   ```
3. V GitHub repozitáři přejděte do **Settings** -> **Secrets and variables** -> **Actions** a přidejte:
   * `AZURE_VM_HOST`: doména nebo IP vašeho VM
   * `AZURE_VM_USER`: uživatelské jméno na VM (např. `azureuser`)
   * `AZURE_SSH_KEY`: obsah privátního klíče z předchozího kroku

Každý `git push origin main` od té chvíle automaticky otestuje a zaktualizuje běžící instanci bez výpadku.

---

## ⚖️ Souběh dotazů (Concurrency) & Load Balancing

Server je navržen pro vysokou souběžnou zátěž:
* **Neblokující asynchronní I/O**: Postaveno na `FastAPI` + `uvloop`. Server neblokuje proces při čekání na síťová data a zvládá stovky paralelních požadavků.
* **In-Memory TTL Cache (30s)**: Když se na výsledky v Praze nebo celkový stav sčítání zeptá 100 lidí současně, server pošle dotaz na ČSÚ pouze jednou. Zbylých 99 požadavků dostane data okamžitě z RAM cache (odezva pod 2 ms). Tím je chráněn server i infrastruktura ČSÚ.
* **Caddy Layer 7 Load Balancer**:
  Caddy funguje jako nativní load balancer. Pokud v budoucnu v `docker-compose.yml` navýšíte počet replik aplikace (`mcp-volby`), Caddy automaticky rozděluje zátěž (metodami `round_robin` nebo `least_conn`) s aktivním sledováním healthchecků.

---

## 📁 Architektura kódu

Kód je rozdělen do modulárních vrstev bez jakýchkoliv hardcoded hodnot:
```
src/
├── core/
│   ├── __init__.py
│   └── security.py           # Bearer token autentizace a validace požadavků
├── services/
│   ├── __init__.py
│   └── election_service.py   # Byznys logika voleb (overview, senát, obce, search, progress)
├── mcp/
│   ├── __init__.py
│   ├── tools.py              # Definice schémat a obsluha volání MCP nástrojů
│   └── jsonrpc.py            # JSON-RPC 2.0 dispatcher pro Streamable HTTP (Antigravity)
├── api/
│   ├── __init__.py
│   ├── routes_rest.py        # REST API router (OpenAPI / Swagger / ChatGPT Actions)
│   └── routes_mcp.py         # MCP router (SSE a Streamable HTTP protokoly)
├── parsers/                  # Parsování XML dat ČSÚ a fulltextový vyhledávací index
├── config.py                 # Centralizovaná konfigurace přes Pydantic Settings
├── server.py                 # Štíhlá Application Factory (85 řádků)
└── cli.py                    # CLI rozhraní pro spuštění přes stdio i HTTP
```

---

## 🧪 Testování

```bash
# Spuštění testovací sady
pytest tests/ -v
```

Testy pokrývají:
- Parsování živých struktur ČSÚ (Senát, obce, celá ČR).
- Hraniční stavy: vítěz v 1. kole (>50 %) vs postup do 2. kola.
- Normalizaci diakritiky a fulltextové vyhledávání obcí i obvodů.
- Integrační testy FastAPI a obou MCP transportů (SSE i Streamable HTTP JSON-RPC).

---

## 📄 Licence

Tento projekt je licencován pod licencí [MIT](LICENSE).  
Volební data pocházejí z otevřených dat Českého statistického úřadu (ČSÚ).
