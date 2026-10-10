---
name: czech-elections-analyst
description: Expert analyst and guide for Czech elections (Senate and Municipal elections 2026), ČSÚ open data processing, counting bias mitigation protocols, political coalition modeling, and MCP server tool utilization.
---

# Czech Elections 2026 Analyst Skill (`czech-elections-analyst`)

Tento skill slouží jako autoritativní metodická a operační příručka pro analýzu voleb v České republice v roce 2026 (Volby do Senátu Parlamentu ČR a volby do zastupitelstev obcí), interpretaci živých otevřených dat Českého statistického úřadu (ČSÚ) a efektivní práci s nástroji serveru Model Context Protocol (**MCP volby 2026**).

---

## 1. Architektura volebního systému a datových zdrojů ČSÚ

V říjnu 2026 probíhají v České republice souběžně dva odlišné volební procesy:

```
                                  ┌───────────────────────────────┐
                                  │   ČSÚ Open Data & OData API   │
                                  │   (volby.gov.cz / volby.cz)   │
                                  └──────────────┬────────────────┘
                                                 │
                        ┌────────────────────────┴────────────────────────┐
                        ▼                                                 ▼
          ┌───────────────────────────┐                     ┌───────────────────────────┐
          │      SENÁT PČR 2026       │                     │  ZASTUPITELSTVA OBCÍ 2026 │
          │  Dvoukolový většinový     │                     │  Poměrný systém, panašov. │
          │  Obměna 27 obvodů (1/3)   │                     │  6 249+ obcí, 60 000+ mand│
          └─────────────┬─────────────┘                     └─────────────┬─────────────┘
                        │                                                 │
                        │ HTTP XML / ZIP JSON                             │ HTTP XML / ZIP JSON
                        ▼                                                 ▼
          ┌─────────────────────────────────────────────────────────────────────────────┐
          │                         MCP SERVER VOLBY CR 2026                            │
          │             FastAPI + SSE Streamable HTTP (/sse, /mcp, :8088)               │
          ├─────────────────────────────────────────────────────────────────────────────┤
          │ • In-Memory TTL Cache (30s)          • Registry & Číselníky (kvcoco, serk)  │
          │ • Accent-insensitive search          • OData XML parsery                    │
          │ • Analytický engine (MWC koalice)    • Telemetrie & rychlost sčítání        │
          └─────────────────────────────────────────────────────────────────────────────┘
```

### Přehled volebních systémů
1. **Volby do Senátu Parlamentu ČR (obměna 27 z 81 obvodů, modulo 3 = 0, obvody č. 3, 6, ..., 81):**
   - **Volební systém:** Dvoukolový většinový (Two-round runoff system).
   - **1. kolo:** Pokud kandidát získá více než 50,00 % platných hlasů, je přímo zvolen senátorem (`elected_round_1 = True`).
   - **2. kolo (o týden později):** Pokud nikdo nepřekročí 50 %, postupují dva nejsilnější kandidáti (`advances_to_round_2 = True`). Ve 2. kole vítězí kandidát s prostou většinou hlasů (`elected_round_2 = True`).
2. **Volby do zastupitelstev obcí (komunální volby v 6 249 obcích a městech):**
   - **Volební systém:** Poměrný volební systém s možností panašování (volič může volit celou stranu, vybírat kandidáty napříč stranami, nebo kombinovat obojí).
   - **Klauzule:** 5 % platných hlasů pro vstup do skrutinia.
   - **Rozdělování mandátů:** Upravená d'Hondtova metoda (nebo Sainte-Laguë pro malé obce).

---

## 2. Protokol mitigace zkreslení průběžného sčítání (Counting Bias Protocol)

Během volebního odpoledne (sobota 14:00 – 22:00) dochází k systematickému statistickému zkreslení výsledků v důsledku nestejné rychlosti zpracování okrsků. Analytik **musí** aplikovat následující zásady:

### A. Venkovské vs. městské zkreslení (Rural-Urban Bias)
- **14:30 – 16:00:** Sčítají se malé venkovské okrsky (100–300 voličů). Rychle rostou procenta ANO, SPD a nezávislých lokálních sdružení.
- **16:30 – 19:30:** Začínají nabíhat okresní a krajská města.
- **18:00 – 21:00:** Jako poslední přicházejí velké městské aglomerace (Praha, Brno, Ostrava, Plzeň), kde okrsky čítají 800–1 200 voličů a složité panašování trvá nejdéle. Teprve zde prudce stoupají zisky liberálních a středopravicových formací (SPOLU, Piráti, STAN).

### B. Závazná pravidla pro reportování a interpretaci
1. **Zákaz vyhlašování vítěze před koncem sčítání:**
   - Pokud `is_completed == False`, hodnota `winner` je striktně `None`.
   - Využívá se výhradně pole `leading_party` doplněné o informaci o procentu sečtených okrsků (např. *„Průběžně vede strana X při 42,5 % sečtených okrsků“*).
2. **Bezpečnostní odstup (Runoff Safety Margin) v Senátu:**
   - Do postupu do 2. kola nelze kandidáty s jistotou potvrdit, pokud rozdíl mezi 2. a 3. kandidátem (`cutoff_margin_votes`) je menší než odhadovaný počet dosud nesečtených hlasů v obvodu:
     $$\text{Zbývající hlasy} \approx (\text{OKRSKY\_CELKEM} - \text{OKRSKY\_ZPRAC}) \times \bar{V}_{\text{okrsek}}$$
3. **Telemetrie a tempo:**
   - Vždy zkontroluj `get_live_counting_progress` pro zjištění celkového tempa sčítání v ČR.

---

## 3. Matematické a analytické metriky

MCP server automaticky počítá následující analytické indikátory:

### A. Senátní metriky
- **Náskok lídra (Lead Margin):**
  $$\text{lead\_margin\_votes} = V_1 - V_2$$
  $$\text{lead\_margin\_pct} = P_1 - P_2$$
  *Interpretace:* Míra dominance prvního kandidáta. V 1. kole ukazuje šanci na vítězství hned v 1. kole (>50 %), ve 2. kole určuje konečný mandát.
- **Odskok pro postup (Cutoff Margin):**
  $$\text{cutoff\_margin\_votes} = V_2 - V_3$$
  $$\text{cutoff\_margin\_pct} = P_2 - P_3$$
  *Interpretace:* Klíčový ukazatel dramatičnosti souboje o postupové 2. místo.

### B. Komunální metriky
- **Většinová hranice (Majority Seats):**
  $$\text{majority\_seats} = \lfloor \frac{\text{total\_seats}}{2} \rfloor + 1$$
- **Propadlé hlasy (Wasted Votes Percentage):**
  $$\text{wasted\_votes\_pct} = \begin{cases} \sum_{p \in \mathcal{P}, \text{seats}(p) = 0} \text{votes\_pct}(p) & \text{po sečtení (is\_completed = True)} \\ \sum_{p \in \mathcal{P}, \text{votes\_pct}(p) < 5.0} \text{votes\_pct}(p) & \text{během sčítání (is\_completed = False)} \end{cases}$$
  *Interpretace:* Součet procent všech kandidátních listin, které nepřekročily 5% uzavírací klauzuli a nezískaly mandát. Během sčítání (dokud nejsou mandáty rozděleny) se počítají strany pod 5 %, po sečtení se sčítají všechny strany s 0 mandáty. Vysoké procento (>15 %) signalizuje vysokou fragmentaci a snazší dosažení většiny pro úspěšné strany.

### C. Teorie minimálních vítězných koalic (Minimal Winning Coalitions - MWC)
Dle Rikerovy teorie koalic (*Theory of Political Coalitions*) jsou nejstabilnější a nejčastěji vznikající takové vládní většiny, kde žádná členská strana není přebytečná:
- Koalice $C \subseteq \mathcal{P}$ je **vítězná**, pokud:
  $$\sum_{p \in C} \text{seats}(p) \ge \text{majority\_seats}$$
- Koalice $C$ je **minimální vítězná (MWC)**, pokud pro každou stranu $p \in C$ platí:
  $$\sum_{q \in C \setminus \{p\}} \text{seats}(q) < \text{majority\_seats}$$
MCP nástroj `get_coalition_scenarios` automaticky generuje všechny relevantní scénáře seřazené dle:
1. `is_minimal_winning` (MWC mají prioritu),
2. `parties_count` (menší počet stran = vyšší stabilita a nižší transakční náklady vyjednávání),
3. `majority_margin` (optimální těsná většina bez přebytečných partnerů).
Pokud strana získá jednobarevnou většinu (`single_party_majority`), je jednobarevná většina jediným MWC scénářem.

---

## 4. MCP Nástroje a jejich využití

Server **volby-cr-2026** exponuje následující sadu specializovaných nástrojů:

| Název nástroje | Vstupní parametry | Popis a výstup |
|---|---|---|
| `get_election_overview` | *(žádné)* | Celostátní souhrn voleb: stav sčítání, účast, zpracované okrsky pro Senát i Obce. |
| `get_senate_results` | `obvod` *(volitelné: číslo nebo název)* | Výsledky Senátu za všech 27 volených obvodů nebo konkrétní obvod (včetně 2. kola, stran, lead/cutoff margin). |
| `get_senate_district_breakdown` | `obvod` *(povinné: číslo nebo název)* | Hlasy pro kandidáty po jednotlivých obcích senátního obvodu (včetně stranické příslušnosti a lídrů obcí). |
| `get_municipal_results` | `obec` *(povinné: název nebo kód)* | Výsledky komunálních voleb v obci: mandáty, hlasy, `majority_seats`, `wasted_votes_pct`, `winner`/`leading_party`, kompletní kandidátní listiny se stranickou příslušností (`political_affiliation`), navrhující stranou, věkem, povoláním, jmenný seznam kandidátů (hlasy/křížky) a zvolení zastupitelé (`elected_representatives`). |
| `get_coalition_scenarios` | `obec` *(povinné: název nebo kód)* | Povolební koaliční matematika: jednobarevné většiny a minimální vítězné koalice (MWC). |
| `search_municipality_or_district` | `query` *(povinné: str)*, `limit` *(int)* | Vyhledávač obcí a senátních obvodů s tolerancí diakritiky a číselných kódů. |
| `get_live_counting_progress` | *(žádné)* | Živá telemetrie rychlosti sčítání a průběžný stavový komentář. |
| `get_precinct_counting_speed` | `election_type`, `order`, `obec`, `obvod`, `okrsek`, `limit` | Zjištění časů odevzdání a schválení zápisů okrskových volebních komisí (`DATUM_CAS_ZPRAC`). Pořadí nejpomalejších i nejrychlejších komisí v ČR, obci či obvodu. |

---


## 5. Ukázkové analytické pracovní postupy (Workflows)

### Scénář 1: Hodnocení situace v senátním obvodu
1. Zavolej `get_senate_results(obvod="Cheb")` (nebo číslo `3`).
2. Vyhodnoť stav:
   - Pokud `is_completed == True` a `candidates[0].elected_round_1 == True`: kandidát zvolen v 1. kole.
   - Pokud `is_completed == True` a nikdo nemá >50 %: identifikuj 1. a 2. kandidáta postupující do 2. kola. Zkontroluj `cutoff_margin` (jak těsně postoupil druhý před třetím).
   - Pokud probíhá 2. kolo: sleduj `votes_round_2`, `votes_pct_round_2` a `lead_margin`. V případě rovnosti hlasů rozhoduje dle zákona los.
3. Zavolej `get_senate_district_breakdown(obvod=3)` pro analýzu geografické podpory:
   - Který kandidát ovládl centrální město (Cheb)?
   - Kdo dominoval na venkově a menších obcích (Aš, Františkovy Lázně)?

### Scénář 2: Analýza povolebního vyjednávání na radnici
1. Zavolej `get_municipal_results(obec="Praha")`.
2. Zkontroluj základní parametry:
   - Celkem mandátů (`total_seats` = 65), potřebná většina (`majority_seats` = 33).
   - Propadlé hlasy (`wasted_votes_pct`).
   - Stav sčítání (`is_completed`, `winner` po sečtení nebo `leading_party` během sčítání).
3. Zavolej `get_coalition_scenarios(obec="Praha")`.
4. Analyzuj vygenerované koaliční varianty:
   - Existuje jednobarevná většina (`single_party_majority`)?
   - Existuje 2-koalice s pohodlnou většinou?
   - Kdo drží pozici klíčového jazýčku na vahách (*kingmakera*)?

---

## 6. Integrace a konfigurace MCP klienta

Server lze snadno nakonfigurovat v libovolném MCP klientovi (Claude Desktop, Cursor, Gemini CLI, Antigravity):

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "volby-cr-2026": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "C:/Users/jan.petr/OneDrive - dolphinconsulting.cz/Projects/MCP_volby_2026"
    }
  }
}
```

### Síťové připojení přes Streamable HTTP / SSE endpoint
Pokud server běží samostatně (např. přes `uvicorn src.server:app --port 8088`):
- **SSE URL:** `http://localhost:8088/sse`
- **Streamable HTTP POST:** `http://localhost:8088/mcp`
- **REST OpenAPI docs:** `http://localhost:8088/docs`
