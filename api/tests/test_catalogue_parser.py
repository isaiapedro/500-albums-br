from __future__ import annotations

import pytest

from app.catalogue_parser import (
    CatalogueValidationError,
    NormalizedAlbum,
    canonical_normalized_rows,
    normalized_sha256,
    parse_and_validate_html,
)


HEADERS = ("Posição", "Título", "Ano de lançamento", "Artista(s)")


def ranking_html(rows: list[tuple[str, str, str, str]]) -> str:
    header = "".join(f"<th>{value}</th>" for value in HEADERS)
    body = "".join(
        "<tr>" + "".join(f"<td>{value}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table class='wikitable sortable'><tr>{header}</tr>{body}</table>"


def complete_rows() -> list[tuple[str, str, str, str]]:
    return [(str(rank), f"Album {rank}", "1972", f"Artist {rank}") for rank in range(1, 501)]


def test_parses_normalizes_and_orders_a_complete_ranking() -> None:
    rows = complete_rows()
    rows[0] = ("1", "  Álbum   Um <sup>[1]</sup> ", "", " Artista\n Um ")
    albums = parse_and_validate_html(ranking_html(rows))

    assert len(albums) == 500
    assert albums[0] == NormalizedAlbum(1, "Álbum Um", None, "Artista Um")
    assert albums[-1].rank == 500


@pytest.mark.parametrize(
    ("rows", "error"),
    [
        (lambda: complete_rows()[:-1], "invalid_row_count"),
        (
            lambda: [("1" if rank == 500 else str(rank), f"Album {rank}", "1972", f"Artist {rank}") for rank in range(1, 501)],
            "duplicate_rank",
        ),
        (
            lambda: [("501" if rank == 500 else str(rank), f"Album {rank}", "1972", f"Artist {rank}") for rank in range(1, 501)],
            "rank_set_must_be_1_through_500",
        ),
    ],
)
def test_rejects_incomplete_duplicate_and_out_of_range_rankings(rows, error: str) -> None:
    with pytest.raises(CatalogueValidationError, match=f"^{error}$"):
        parse_and_validate_html(ranking_html(rows()))


@pytest.mark.parametrize("year", ["1879", "2101", "nineteen", "1972-73"])
def test_rejects_invalid_nonempty_release_year(year: str) -> None:
    rows = complete_rows()
    rows[0] = ("1", "Album 1", year, "Artist 1")
    with pytest.raises(CatalogueValidationError, match="^invalid_release_year$"):
        parse_and_validate_html(ranking_html(rows))


def test_parser_never_includes_raw_source_content_in_error() -> None:
    sentinel = "RAW_HTML_MUST_NOT_ESCAPE"
    html = ranking_html([("not-a-rank", sentinel, "1972", "Artist")])
    with pytest.raises(CatalogueValidationError) as error:
        parse_and_validate_html(html)
    assert sentinel not in str(error.value)


def test_hash_is_deterministic_and_independent_of_input_order() -> None:
    albums = parse_and_validate_html(ranking_html(complete_rows()))
    assert normalized_sha256(albums) == normalized_sha256(tuple(reversed(albums)))
    assert canonical_normalized_rows(albums).startswith(b'[{"artist_credit":"Artist 1"')
