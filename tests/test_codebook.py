"""Unit tests for codebook index, search and accent-insensitive normalization."""

import pytest
from src.parsers.codebook_loader import CodebookIndex, normalize_text


def test_normalize_text():
    assert normalize_text("Příbram") == "pribram"
    assert normalize_text("České Budějovice") == "ceske budejovice"
    assert normalize_text("Plzeň-město") == "plzen-mesto"
    assert normalize_text("Žďár nad Sázavou") == "zdar nad sazavou"
    assert normalize_text("") == ""


def test_codebook_defaults():
    index = CodebookIndex()
    index.initialize_defaults()

    assert len(index.senate_districts) == 27
    assert 3 in index.senate_districts
    assert index.senate_districts[3].name == "Obvod č. 3 - Cheb"

    assert "554782" in index.municipalities
    assert index.municipalities["554782"].name == "Praha"


def test_resolve_senate_district():
    index = CodebookIndex()
    index.initialize_defaults()

    # By number
    assert index.resolve_senate_district(3) == 3
    assert index.resolve_senate_district("3") == 3
    assert index.resolve_senate_district("03") == 3

    # By name without accents
    assert index.resolve_senate_district("cheb") == 3
    assert index.resolve_senate_district("Cheb") == 3
    assert index.resolve_senate_district("louny") == 6
    assert index.resolve_senate_district("praha 9") == 24
    assert index.resolve_senate_district("zdar nad sazavou") == 51

    # Non-existent
    assert index.resolve_senate_district("NonExistent") is None


def test_resolve_municipality_code():
    index = CodebookIndex()
    index.initialize_defaults()

    # By code
    assert index.resolve_municipality_code("554782") == "554782"

    # By name
    assert index.resolve_municipality_code("Praha") == "554782"
    assert index.resolve_municipality_code("praha") == "554782"
    assert index.resolve_municipality_code("Brno") == "582786"
    assert index.resolve_municipality_code("Ceske Budejovice") == "544256"
    assert index.resolve_municipality_code("Plzen") == "554791"


def test_search():
    index = CodebookIndex()
    index.initialize_defaults()

    # Search for "cheb" should find both Senate district 3 and town Cheb
    res = index.search("cheb")
    assert res.total_found >= 2
    types = {r.item_type for r in res.results}
    assert "senat" in types
    assert "obec" in types

    # Search for "ostrava"
    res_ostrava = index.search("ostrava")
    assert any("Ostrava" in r.name for r in res_ostrava.results)
