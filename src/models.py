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
    votes_round_1: int = Field(description="Počet hlasů v 1. kole")
    votes_pct_round_1: float = Field(description="Procento hlasů v 1. kole")
    elected_round_1: bool = Field(default=False, description="Zda byl zvolen již v 1. kole (>50 %)")
    advances_to_round_2: bool = Field(default=False, description="Zda postupuje do 2. kola")


class SenateDistrictResult(BaseModel):
    """Result for a specific Senate electoral district (senátní obvod)."""
    district_number: int = Field(description="Číslo senátního obvodu (1–81)")
    district_name: str = Field(description="Sídlo senátního obvodu")
    turnout: TurnoutInfo = Field(description="Volební účast v obvodu")
    candidates: List[SenateCandidateResult] = Field(description="Seznam kandidátů s výsledky")
    is_completed: bool = Field(description="Zda jsou již sečteny všechny okrsky v obvodu")
    status_summary: str = Field(description="Stručné textové shrnutí stavu obvodu")


class SenateOverviewResponse(BaseModel):
    """Overview of Senate elections (27 contested districts in 2026)."""
    election_title: str = Field(default="Volby do Senátu Parlamentu ČR 2026")
    generated_at: str = Field(description="Čas generování dat ČSÚ")
    districts_total: int = Field(default=27, description="Počet volených obvodů v roce 2026")
    districts_completed: int = Field(description="Počet kompletně sečtených obvodů")
    districts: List[SenateDistrictResult] = Field(description="Výsledky za jednotlivé obvody")


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
    winner: Optional[str] = Field(default=None, description="Vítězná strana dle počtu hlasů")


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
