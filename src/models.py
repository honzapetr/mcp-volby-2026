"""Pydantic models for election data representations and API/MCP responses."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class TurnoutInfo(BaseModel):
    """Voter turnout statistics for a district, municipality, or whole country."""
    precincts_total: int = Field(description="Celkový počet volebních okrsků")
    precincts_processed: int = Field(description="Počet zpracovaných volebních okrsků")
    precincts_processed_pct: float = Field(description="Procento zpracovaných okrsků")
    registered_voters: int = Field(description="Počet zapsaných voličů")
    issued_envelopes: int = Field(description="Počet vydaných úředních obálek")
    turnout_pct: float = Field(description="Volební účast v procentech")
    valid_votes: int = Field(description="Počet platných hlasů")


class SenateCandidateResult(BaseModel):
    """Result for an individual Senate candidate."""
    candidate_number: int = Field(description="Pořadové číslo kandidáta")
    first_name: str = Field(description="Jméno kandidáta")
    last_name: str = Field(description="Příjmení kandidáta")
    title_pre: str = Field(default="", description="Titul před jménem")
    title_post: str = Field(default="", description="Titul za jménem")
    party_name: Optional[str] = Field(default=None, description="Název volební strany / koalice")
    nominating_party: Optional[str] = Field(default=None, description="Navrhující strana")
    political_affiliation: Optional[str] = Field(default=None, description="Politická příslušnost")
    votes_round_1: int = Field(description="Počet hlasů v 1. kole")
    votes_pct_round_1: float = Field(description="Procento hlasů v 1. kole")
    elected_round_1: bool = Field(default=False, description="Zda byl zvolen již v 1. kole (>50 %)")
    advances_to_round_2: bool = Field(default=False, description="Zda postupuje do 2. kola")
    votes_round_2: Optional[int] = Field(default=None, description="Počet hlasů ve 2. kole")
    votes_pct_round_2: Optional[float] = Field(default=None, description="Procento hlasů ve 2. kole")
    elected_round_2: Optional[bool] = Field(default=None, description="Zda byl zvolen ve 2. kole")


class SenateDistrictResult(BaseModel):
    """Result for a specific Senate electoral district (senátní obvod)."""
    district_number: int = Field(description="Číslo senátního obvodu (1–81)")
    district_name: str = Field(description="Sídlo senátního obvodu")
    turnout: TurnoutInfo = Field(description="Volební účast v obvodu (1. kolo)")
    turnout_round_2: Optional[TurnoutInfo] = Field(default=None, description="Volební účast v obvodu (2. kolo)")
    candidates: List[SenateCandidateResult] = Field(description="Seznam kandidátů s výsledky")
    is_completed: bool = Field(description="Zda jsou již sečteny všechny okrsky v obvodu")
    status_summary: str = Field(description="Stručné textové shrnutí stavu obvodu")
    lead_margin: Optional[dict] = Field(default=None, description="Rozdíl mezi 1. a 2. kandidátem {'votes': int, 'pct': float}")
    cutoff_margin: Optional[dict] = Field(default=None, description="Rozdíl mezi 2. a 3. kandidátem {'votes': int, 'pct': float}")
    lead_margin_votes: Optional[int] = Field(default=None, description="Náskok 1. před 2. kandidátem v hlasech")
    lead_margin_pct: Optional[float] = Field(default=None, description="Náskok 1. před 2. kandidátem v procentních bodech")
    cutoff_margin_votes: Optional[int] = Field(default=None, description="Náskok 2. před 3. kandidátem v hlasech")
    cutoff_margin_pct: Optional[float] = Field(default=None, description="Náskok 2. před 3. kandidátem v procentních bodech")


class SenateOverviewResponse(BaseModel):
    """Overview of Senate elections (27 contested districts in 2026)."""
    election_title: str = Field(default="Volby do Senátu Parlamentu ČR 2026")
    generated_at: str = Field(description="Čas generování dat ČSÚ")
    districts_total: int = Field(default=27, description="Počet volených obvodů v roce 2026")
    districts_completed: int = Field(description="Počet kompletně sečtených obvodů")
    districts: List[SenateDistrictResult] = Field(description="Výsledky za jednotlivé obvody")


class MunicipalCandidateResult(BaseModel):
    """Result for an individual candidate in a municipal election."""
    candidate_number: int = Field(description="Pořadové číslo kandidáta na kandidátní listině")
    first_name: str = Field(description="Jméno kandidáta")
    last_name: str = Field(description="Příjmení kandidáta")
    title_pre: str = Field(default="", description="Titul před jménem")
    title_post: str = Field(default="", description="Titul za jménem")
    party_name: Optional[str] = Field(default=None, description="Volební strana")
    party_id: Optional[int] = Field(default=None, description="Číslo / kód volební strany ČSÚ")
    votes: int = Field(default=0, description="Počet získaných přednostních hlasů (křížků)")
    votes_pct: float = Field(default=0.0, description="Procentuální podíl hlasů v rámci strany")
    is_elected: bool = Field(default=False, description="Zda získal mandát zastupitele")
    order_elected: Optional[int] = Field(default=None, description="Pořadí zvolení / mandátu")
    mandate_status: Optional[str] = Field(default=None, description="Status mandátu: 'Zvolen', 'Náhradník', 'Bez mandátu'")


class MunicipalPartyResult(BaseModel):
    """Result for a candidate list / political party in a municipality."""
    list_number: int = Field(description="Číslo volební strany na hlasovacím lístku")
    party_id: int = Field(description="Kód volební strany ČSÚ")
    party_name: str = Field(description="Název volební strany / sdružení")
    votes: int = Field(description="Počet získaných hlasů")
    votes_pct: float = Field(description="Procento získaných hlasů")
    seats_won: int = Field(description="Počet získaných mandátů v zastupitelstvu")
    seats_pct: float = Field(description="Procentuální podíl mandátů")
    candidates_count: int = Field(description="Počet kandidátů na listině")
    candidates: List[MunicipalCandidateResult] = Field(default_factory=list, description="Seznam kandidátů s výsledky a hlasy")
    elected_candidates: List[MunicipalCandidateResult] = Field(default_factory=list, description="Seznam přímo zvolených zastupitelů strany")


class MunicipalResultResponse(BaseModel):
    """Results for municipal elections in a specific town, city, or Prague."""
    municipality_code: str = Field(description="Kód obce / zastupitelstva (KODZASTUP)")
    municipality_name: str = Field(description="Název obce / města")
    council_type: str = Field(description="Typ zastupitelstva (OBEC, MCMO apod.)")
    total_seats: int = Field(description="Celkový počet volených zastupitelů")
    is_completed: bool = Field(description="Zda je sčítání v obci ukončeno")
    generated_at: str = Field(description="Čas vygenerování dat ČSÚ")
    turnout: TurnoutInfo = Field(description="Volební účast v obci")
    parties: List[MunicipalPartyResult] = Field(description="Výsledky kandidujících stran")
    winner: Optional[str] = Field(default=None, description="Vítězná strana dle počtu hlasů (pouze po 100% sečtení)")
    leading_party: Optional[str] = Field(default=None, description="Průběžně vedoucí strana během sčítání")
    majority_seats: int = Field(default=0, description="Minimální počet mandátů pro většinu (total_seats // 2 + 1)")
    wasted_votes_pct: float = Field(default=0.0, description="Součet % hlasů propadlých stranám s 0 mandáty")
    counting_status: Optional[str] = Field(default=None, description="Indikace stavu sčítání")
    elected_representatives: List[MunicipalCandidateResult] = Field(default_factory=list, description="Všichni zvolení zastupitelé obce napříč stranami")


class MunicipalitySenateResult(BaseModel):
    """Senate election results within a specific municipality."""
    municipality_code: str = Field(description="Kód obce ČSÚ")
    municipality_name: str = Field(description="Název obce")
    turnout: TurnoutInfo = Field(description="Volební účast v obci")
    candidates: List[SenateCandidateResult] = Field(description="Výsledky kandidátů v obci")
    leader_name: Optional[str] = Field(default=None, description="Vítězný / vedoucí kandidát v této obci")


class SenateDistrictBreakdownResponse(BaseModel):
    """Detailed breakdown of Senate district votes across all municipalities."""
    district_number: int = Field(description="Číslo senátního obvodu")
    district_name: str = Field(description="Sídlo senátního obvodu")
    generated_at: str = Field(description="Čas vygenerování dat ČSÚ")
    municipalities_total: int = Field(description="Celkový počet obcí v obvodu")
    municipalities_processed: int = Field(description="Počet sečtených obcí v obvodu")
    municipalities: List[MunicipalitySenateResult] = Field(description="Výsledky za jednotlivé obce v obvodu")


class CoalitionScenario(BaseModel):
    """Potential governing coalition scenario in a municipal council."""
    parties: List[str] = Field(description="Seznam stran tvořících koalici")
    total_seats: int = Field(description="Celkový počet mandátů koalice")
    seats_pct: float = Field(description="Procentuální podíl křesel v zastupitelstvu")
    majority_margin: int = Field(description="Počet mandátů nad potřebnou většinu")
    parties_count: int = Field(description="Počet stran v koalici")
    is_minimal_winning: bool = Field(description="Zda jde o minimální vítěznou koalici (žádná strana není přebytečná)")


class CoalitionAnalysisResponse(BaseModel):
    """Analysis of municipal council coalition potential and minimal winning coalitions."""
    municipality_code: str = Field(description="Kód obce")
    municipality_name: str = Field(description="Název obce")
    total_seats: int = Field(description="Celkový počet mandátů v zastupitelstvu")
    majority_seats: int = Field(description="Potřebná většina mandátů (total_seats // 2 + 1)")
    is_completed: bool = Field(description="Zda je sčítání v obci ukončeno")
    single_party_majority: Optional[str] = Field(default=None, description="Strana s jednobarevnou většinou, pokud existuje")
    scenarios: List[CoalitionScenario] = Field(description="Možné většinové koaliční scénáře seřazené dle stability")
    status_message: Optional[str] = Field(default=None, description="Informativní stavová zpráva k analýze koalic")


class SearchResultItem(BaseModel):
    """Item found in municipality or district search."""
    item_type: str = Field(description="'senat' pro senátní obvod nebo 'obec' pro obec")
    code: str = Field(description="Kód obce (např. 554782) nebo číslo obvodu (např. 3)")
    name: str = Field(description="Název obce nebo senátního obvodu")
    district_nuts: Optional[str] = Field(default=None, description="Kód okresu NUTS (např. CZ0100)")
    description: str = Field(description="Doplňující popis (okres, kraj apod.)")


class SearchResultResponse(BaseModel):
    """Response containing matched municipalities and Senate districts."""
    query: str = Field(description="Hledaný výraz")
    total_found: int = Field(description="Celkový počet nalezených záznamů")
    results: List[SearchResultItem] = Field(description="Seznam nalezených položek")


class ElectionOverviewResponse(BaseModel):
    """High-level summary of all Czech 2026 elections."""
    current_time: str = Field(description="Aktuální čas")
    counting_started: bool = Field(description="Zda již začalo sčítání (sobota po 14:00)")
    senate_summary: dict = Field(description="Souhrn sčítání do Senátu")
    municipal_summary: dict = Field(description="Souhrn sčítání do zastupitelstev obcí")
    last_updated: str = Field(description="Čas poslední aktualizace dat z ČSÚ")


class CountingProgressResponse(BaseModel):
    """Real-time counting telemetry and speed metrics."""
    timestamp: str = Field(description="Čas odečtu metriky")
    counting_active: bool = Field(description="Zda probíhá sčítání")
    senate_pct: float = Field(description="% sečtených okrsků Senát")
    municipal_pct: float = Field(description="% sečtených okrsků Obce")
    status_message: str = Field(description="Informativní zpráva o stavu sčítání")
