# 🇨🇿 MCP Server: Volby 2026 v České republice

[![CI](https://github.com/dolphinconsulting/mcp-volby-2026/actions/workflows/ci.yml/badge.svg)](https://github.com/dolphinconsulting/mcp-volby-2026/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)
[![Protocol](https://img.shields.io/badge/MCP-1.13+-green.svg)](https://modelcontextprotocol.io/)

Robustní a vysoce modulární **Model Context Protocol (MCP)** server a **REST API** s živým napojením na oficiální data **Českého statistického úřadu (ČSÚ)** (`volby.gov.cz` / `volby.cz`) pro volby v České republice konané v říjnu 2026.

Umožňuje AI modelům v reálném čase přistupovat ke sčítání hlasů, které začíná v sobotu **10. října 2026 ve 14:00**, zjišťovat volební účast, počty sečtených okrsků, pořadí kandidátů do Senátu i rozdělení mandátů v zastupitelstvech obcí a statutárních měst.

---

## 🗳️ Kontext a specifika voleb v ČR 2026

V říjnu 2026 se v ČR konají **dvoje volby**:
1. **Volby do Senátu Parlamentu ČR (1. kolo)**: Volí se 27 senátorů (obměna 1/3 Senátu, obvody č. 3, 6, 9 … 81). Pokud nikdo v obvodu nezíská >50 %, postupují 2 nejlepší do 2. kola (16.–17. 10. 2026).
2. **Volby do zastupitelstev obcí (komunální volby)**: Volí se nová zastupitelstva ve všech **6 249 obcích**, statutárních městech a hl. m. Praze.

> [!NOTE]
> **Co primátorské volby?**
> Přímé primátorské volby v ČR ze zákona **neexistují**. Primátory (ve statutárních městech a Praze) a starosty (v obcích) volí nově ustavené zastupitelstvo ze svých členů na ustavujícím zasedání. Občané tedy volí primátora nepřímo volbou zastupitelstva. Server proto pro každé město (Praha, Brno, Ostrava, Plzeň…) vrací kompletní složení zastupitelstva, zisky stran a mandáty.

---

## 🏗️ Architektura a integrace klientů

Server je postaven na bázi **FastAPI + official MCP Python SDK** a poskytuje **duální rozhraní**:
- **MCP Protokol přes Server-Sent Events (SSE)** na `/sse` a `/messages` – nativní podpora pro **Claude Code**, **Antigravity**, **Cursor**, **Claude Desktop**.
- **REST OpenAPI 3.0** na `/api/*` se schématem na `/openapi.json` a Swagger UI na `/docs` – přímá podpora pro **ChatGPT Custom GPT Actions** i libovolné HTTP klienty.

```
                  ┌──────────────────────────────────────────────┐
                  │    Český statistický úřad (ČSÚ / volby.cz)    │
                  │  (vysledky.xml, obvody, obce, číselníky OFN)  │
                  └───────────────────────┬──────────────────────┘
                                          │ HTTP (XML / JSON)
                                          ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   MCP Server Volby 2026 (Docker)                      │
│                                                                        │
│  ┌─────────────────────────┐         ┌──────────────────────────────┐  │
│  │   CSU Asynchronous      │         │   In-Memory Cache (TTL)      │  │
│  │   Client (httpx)        │◄───────►│   & Codebook Search Index    │  │
│  └────────────┬────────────┘         └──────────────┬───────────────┘  │
│               │                                     │                  │
│               ▼                                     ▼                  │
│  ┌─────────────────────────┐         ┌──────────────────────────────┐  │
│  │ XML/JSON Parsers        │         │ Security & Auth (Bearer)     │  │
│  │ (Senát, Obce, Okresy)   │         │ Rate-limit & Error Handling  │  │
│  └────────────┬────────────┘         └──────────────┬───────────────┘  │
│               │                                     │                  │
│               ▼                                     ▼                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                       FastAPI Engine                             │  │
│  │     MCP SSE (/sse & /messages)  │  REST OpenAPI (/openapi.json)  │  │
│  └──────────────────┬───────────────────────────────┬───────────────┘  │
└─────────────────────┼───────────────────────────────┼──────────────────┘
                      │                               │
        ┌─────────────┴─────────────┐                 │
        ▼                           ▼                 ▼
   Claude Code           Antigravity / Cursor      ChatGPT (Actions/MCP)
```

---

## 🛠️ Dostupné MCP nástroje (Tools)

| Nástroj | Parametry | Popis |
| :--- | :--- | :--- |
| `get_election_overview` | *žádné* | Vrátí celkový přehled o sčítání v ČR: stav po 14:00, celková účast, % sečtených okrsků pro Senát a zastupitelstva. |
| `get_senate_results` | `obvod` *(volitelný: str / int)* | Výsledky Senátu za všech 27 obvodů nebo konkrétní obvod (např. `"Cheb"`, `3`, `"Praha 5"`). Zobrazí hlasy, %, zvolení v 1. kole (>50 %) či postupující do 2. kola. |
| `get_municipal_results` | `obec` *(povinný: str)* | Výsledky pro konkrétní město či obec (např. `"Praha"`, `"Brno"`, `"Ostrava"` nebo kód `"554782"`). Vrátí účast, rozdělení mandátů v zastupitelstvu a pořadí stran. |
| `search_municipality_or_district` | `query` *(povinný)*, `limit` *(výchozí 15)* | Inteligentní vyhledávač obcí a senátních obvodů bez ohledu na diakritiku a velikost písmen. |
| `get_live_counting_progress` | *žádné* | Telemetrie a rychlost sčítání: tempo zpracování okrsků a textová zpráva o aktuálním průběhu. |

---

## 🚀 Rychlý start (Lokální Docker)

### 1. Klonování a příprava prostředí
```bash
git clone https://github.com/dolphinconsulting/mcp-volby-2026.git
cd mcp-volby-2026
cp .env.example .env
```

### 2. Spuštění v Dockeru
```bash
docker compose up --build -d
```
Server nastartuje na portu **8088** (konfigurovatelné v `.env`):
- Healthcheck: `http://localhost:8088/health`
- Swagger UI dokumentace: `http://localhost:8088/docs`
- OpenAPI specifikace: `http://localhost:8088/openapi.json`
- MCP SSE Endpoint: `http://localhost:8088/sse`

---

## 🔌 Návod na připojení z AI klientů

### 1. Claude Code
Pro připojení k běžícímu serveru:
```bash
# Přes HTTP/SSE:
claude mcp add --transport sse volby-2026 http://localhost:8088/sse

# Pokud je nastaven API_KEY:
claude mcp add --transport sse volby-2026 http://localhost:8088/sse --header "Authorization: Bearer <TOKEN>"
```

Nebo pro přímé lokální spuštění přes stdio:
```bash
claude mcp add volby-2026 docker run -i --rm mcp-volby-2026:latest python -m src.cli --transport stdio
```

### 2. ChatGPT (Custom GPT Actions)
1. Otevřete [ChatGPT](https://chatgpt.com) -> **Explore GPTs** -> **Create a GPT**.
2. V záložce **Configure** sjeďte dolů na **Actions** a zvolte **Create new action**.
3. Do pole **Schema** zadejte URL vašeho nasazeného serveru:
   ```
   https://<vase-domena>:8088/openapi.json
   ```
4. Pokud máte nastaven `API_KEY`, v Authentication zvolte **API Key** -> **Bearer** a zadejte váš klíč.
5. ChatGPT automaticky načte všechny endpointy (overview, senát, obce, search, progress) a může na ně okamžitě odpovídat.

### 3. Google Antigravity / Cursor / Claude Desktop
Do konfiguračního souboru (`settings.json` nebo `mcp_config.json`):
```json
{
  "mcpServers": {
    "volby_cr_2026": {
      "url": "http://localhost:8088/sse",
      "headers": {
        "Authorization": "Bearer <VAS_VOLITELNY_TOKEN>"
      }
    }
  }
}
```

---

## ☁️ Nasazení na Azure VM

1. **Vytvoření virtuálního stroje**:
   - OS: Ubuntu 24.04 LTS (např. Standard_B2s).
   - Otevřete porty `80`, `443` a `8088` v NSG (Network Security Group).
2. **Klonování a spuštění**:
   ```bash
   git clone https://github.com/dolphinconsulting/mcp-volby-2026.git
   cd mcp-volby-2026
   cp .env.example .env
   # Nastavte API_KEY v .env
   docker compose up --build -d
   ```
3. **Automatické HTTPS přes Caddy (doporučeno pro ChatGPT a vzdálené MCP)**:
   V `docker-compose.yml` odkomentujte sekci `caddy`, zkopírujte `Caddyfile.example` do `Caddyfile`, doplňte vaši Azure doménu a spusťte:
   ```bash
   cp Caddyfile.example Caddyfile
   DOMAIN=volby2026.westeurope.cloudapp.azure.com docker compose up -d
   ```
   Caddy automaticky získá bezplatný Let's Encrypt SSL certifikát a zajistí bezproblémové SSE streamování.

---

## 🧪 Testování a evaluace

```bash
# Spuštění kompletní testovací sady
pytest tests/ -v
```

Projekt obsahuje 14+ automatizovaných unit a integračních testů ověřujících:
- Parsování živých XML schémat ČSÚ pro rok 2026.
- Správnost detekce vítězů v 1. kole (>50 %) a postupujících do 2. kola Senátu.
- Rozdělení mandátů a seřazení stran v komunálních volbách.
- Vyhledávání a normalizaci diakritiky (Praha, Brno, Cheb, Plzeň...).
- Odolnost proti výpadkům a chybným stavům ČSÚ.

---

## 📄 Licence

Tento projekt je licencován pod licencí [MIT](LICENSE).
Data pocházejí z oficiálních otevřených dat Českého statistického úřadu (ČSÚ).
