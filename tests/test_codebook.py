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

    # Non-existent or not contested in 2026 (only 27 districts divisible by 3 are contested)
    assert index.resolve_senate_district(1) is None
    assert index.resolve_senate_district("2") is None
    assert index.resolve_senate_district(81) == 81
    assert index.resolve_senate_district(82) is None
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


def test_major_cities_corrected_codes():
    index = CodebookIndex()
    index.initialize_defaults()

    # Verify corrected codes from task
    assert index.resolve_municipality_code("Ostrava") == "554821"
    assert index.resolve_municipality_code("Pardubice") == "555134"
    assert index.resolve_municipality_code("Kolín") == "533165"
    assert index.resolve_municipality_code("Kolin") == "533165"
    assert index.resolve_municipality_code("Kutná Hora") == "533955"
    assert index.resolve_municipality_code("Kutna Hora") == "533955"
    assert index.resolve_municipality_code("Jeseník") == "536385"
    assert index.resolve_municipality_code("Jesenik") == "536385"
    assert index.resolve_municipality_code("Šumperk") == "523704"
    assert index.resolve_municipality_code("Sumperk") == "523704"
    assert index.resolve_municipality_code("Vyškov") == "592889"
    assert index.resolve_municipality_code("Vyskov") == "592889"
    assert index.resolve_municipality_code("Znojmo") == "593711"

    # Verify no duplicate codes exist in bundled MAJOR_CITIES
    from src.parsers.codebook_loader import MAJOR_CITIES
    codes = [c[0] for c in MAJOR_CITIES]
    assert len(codes) == len(set(codes)), "MAJOR_CITIES must not have duplicate municipality codes"


def test_candidate_affiliation():
    index = CodebookIndex()
    index.senate_candidates[(3, 1)] = {
        "party_name": "STAROSTOVÉ A NEZÁVISLÍ",
        "nominating_party": "STAN",
        "political_affiliation": "BEZPP",
    }
    aff = index.get_candidate_affiliation(3, 1)
    assert aff["party_name"] == "STAROSTOVÉ A NEZÁVISLÍ"
    assert aff["nominating_party"] == "STAN"
    assert aff["political_affiliation"] == "BEZPP"

    empty_aff = index.get_candidate_affiliation(99, 99)
    assert empty_aff["party_name"] == ""


def test_municipal_candidate_info_and_party_candidates():
    index = CodebookIndex()
    c1 = {
        "candidate_number": 1,
        "first_name": "Petr",
        "last_name": "Myslivec",
        "title_pre": "Ing.",
        "title_post": "",
        "party_name": "BOR NÁS SPOJUJE",
        "nominating_party": "STAN",
        "political_affiliation": "BezPP",
        "age": 57,
        "occupation": "obchodní ředitel",
    }
    c2 = {
        "candidate_number": 2,
        "first_name": "František",
        "last_name": "Vokroj",
        "title_pre": "Mgr.",
        "title_post": "",
        "party_name": "BOR NÁS SPOJUJE",
        "nominating_party": "NK",
        "political_affiliation": "BezPP",
        "age": 50,
        "occupation": "vedoucí oddělení",
    }

    index.municipal_candidates[("560758", 5, 1)] = c1
    index.municipal_candidates[("560758", 5, 2)] = c2
    index.municipal_candidates_by_party[("560758", 5)] = [c1, c2]

    # Test single candidate lookup
    cand = index.get_municipal_candidate_info("560758", 5, 1)
    assert cand["first_name"] == "Petr"
    assert cand["political_affiliation"] == "BezPP"
    assert cand["nominating_party"] == "STAN"

    # Test party candidates lookup
    party_cands = index.get_municipal_party_candidates("560758", 5)
    assert len(party_cands) == 2
    assert party_cands[0]["candidate_number"] == 1
    assert party_cands[1]["candidate_number"] == 2

    # Non-existent party
    empty_list = index.get_municipal_party_candidates("560758", 99)
    assert empty_list == []

