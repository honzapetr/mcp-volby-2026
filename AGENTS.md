# 🤖 Agent Guide & Instructions (`AGENTS.md`)

Vítejte v repozitáři **`mcp-volby-2026`** (Model Context Protocol server a REST API pro volby v České republice v říjnu 2026). Tento dokument slouží jako centrální instrukční příručka pro autonomní AI agenty (Google Antigravity, Claude Code, Cursor, GitHub Copilot Workspace, OpenAI Assistants).

---

## 1. Povinné skilly pro AI agenty (Agent Skills)

Pokud jako AI asistent pracujete s tímto repozitářem nebo odpovídáte uživatelům na otázky k volbám v ČR, **musíte se řídit specializovaným analytickým skillem**:

### 🎯 Skill: `czech-elections-analyst`
* **Umístění v repozitáři:** [`.gemini/skills/czech-elections-analyst/SKILL.md`](.gemini/skills/czech-elections-analyst/SKILL.md)
* **Globální instalace:** `~/.gemini/config/skills/czech-elections-analyst/SKILL.md` (ve Windows `%USERPROFILE%\.gemini\config\skills\czech-elections-analyst\SKILL.md`)
* **Účel skillu:** 
  Poskytuje autoritativní politologické a statistické know-how pro správné vyhodnocování otevřených dat ČSÚ, předcházení interpretativním chybám při průběžném sčítání a modelování povolebních koalic.

#### Klíčové protokoly definované ve skillu:
1. **Protokol mitigace sčítacího zkreslení (Counting Bias Mitigation):**
   - V prvních hodinách sčítání (14:00–16:30) sčítají malé venkovské obce. Agenti **nesmí** vyhlašovat celkového vítěze, pokud je sečteno méně než 80 % okrsků.
   - Velká města (Praha, Brno, Ostrava) sčítají nejpomaleji kvůli křížkování a panašování (17:00–21:00).
   - Dokud `is_completed == False`, hodnota `winner` je `None`. Agent musí stranu na 1. místě označovat výhradně jako **průběžného lídra** s uvedením % sečtených okrsků.
2. **Protokol pro Senát ČR (1. a 2. kolo):**
   - V 1. kole kandidát vítězí přímo pouze při zisku $> 50,00\ \%$ platných hlasů při 100 % okrsků (`elected_round_1 = True`).
   - Jinak postupují dva nejsilnější kandidáti do 2. kola (`advances_to_round_2 = True`).
   - Ve 2. kole vítězí kandidát s prostou většinou hlasů (`elected_round_2 = True`). V případě rovnosti rozhoduje dle § 76 odst. 3 zákona los.
   - Agent vždy kalkuluje a komentuje `lead_margin` (náskok vítěze) a `cutoff_margin` (odstup 2. místa před nepostupujícím 3.).
3. **Protokol pro zastupitelstva obcí (Koaliční kalkulátor MWC):**
   - Zákonná většina: $\text{majority\_seats} = \lfloor \text{total\_seats} / 2 \rfloor + 1$.
   - Propadlé hlasy (`wasted_votes_pct`): součet % stran pod 5% uzavírací klauzulí bez mandátu.
   - Minimální vítězné koalice (MWC): agent prezentuje kombinace stran, kde žádná strana není nadbytečná.

---

## 2. Přehled MCP nástrojů v repozitáři

Agent má k dispozici 8 nástrojů vystavených přes MCP i REST:

| Nástroj | Kdy použít |
|---|---|
| `get_election_overview` | Celostátní souhrn voleb, účast a tempo sčítání v ČR pro Senát (vč. 2. kola) i obce. |
| `get_senate_results` | Výsledky za všech 27 obvodů nebo konkrétní obvod (číslo 3..81 nebo název). Obsahuje strany, obě kola i marže. |
| `get_senate_district_breakdown` | Geografický rozpad senátního obvodu po jednotlivých obcích v obvodu (lokální lídři, strany, polarizace město vs. venkov). |
| `get_municipal_results` | Výsledky konkrétního města/obce (všech 6 396 obcí ČR): mandáty, většina `majority_seats`, propadlé hlasy `wasted_votes_pct`, kompletní kandidátní listiny včetně stranické příslušnosti (`political_affiliation`), navrhující strany, věku, povolání, přednostních hlasů (křížků) a zvolení zastupitelé (`elected_representatives`). |
| `get_coalition_scenarios` | Koaliční matematika pro zastupitelstvo: jednobarevné většiny a minimální vítězné koalice (MWC). |
| `search_municipality_or_district` | Vyhledání kódu obce nebo čísla senátního obvodu dle textového dotazu (odolné vůči diakritice). |
| `get_live_counting_progress` | Rychlost a dynamika sčítání v čase (okrsky za minutu, průběžný analytický komentář). |
| `get_precinct_counting_speed` | Časy zpracování a odevzdání spočtených hlasů z volebních okrsků (`DATUM_CAS_ZPRAC`). Umožňuje najít nejpomalejší i nejrychlejší volební komise v ČR, v obci nebo v senátním obvodu. |

---

## 3. Vývojové a verifikační standardy

Při jakýchkoliv úpravách tohoto repozitáře musí agenti dodržovat:

1. **Spuštění testů:**
   ```bash
   pytest tests/ -v
   ```
   Veškeré unit a integrační testy musí projít bez varování a chyb (37+ testů).
2. **Zachování integrity dat ČSÚ:**
   - ČSÚ nepoužívá vedoucí nuly pro senátní obvody v URL rozpadu: `vysledky_obce_obvod_{district_num}.xml`.
   - V číselnících otevřených dat (`kvcoco.json`) je klíč `"polozky"` bez diakritiky.
   - V roce 2026 se volí pouze senátní obvody s číslem dělitelným 3 ($\text{obvod} \pmod 3 = 0$).
3. **Nasazení na produkční server:**
   - Většina `main` je přímo napojena na GitHub Actions CI/CD ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)), které automaticky nasazuje na produkční Azure VM přes SSH a Docker Compose.
