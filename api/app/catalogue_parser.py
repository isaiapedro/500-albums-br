"""Pure parsing and validation for the approved Wikipedia catalogue response.

This module deliberately has no HTTP, database, filesystem, or logging
dependencies.  Callers must discard the supplied HTML once this function
returns (or raises) and persist only the returned normalized rows and hash.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html.parser import HTMLParser
import json
import re
from typing import Final
import unicodedata


MIN_RANK: Final = 1
MAX_RANK: Final = 500
MIN_RELEASE_YEAR: Final = 1880
MAX_RELEASE_YEAR: Final = 2100
EXPECTED_HEADERS: Final = (
    "posição",
    "título",
    "ano de lançamento",
    "artista(s)",
)


class CatalogueValidationError(ValueError):
    """A bounded, safe-to-record catalogue validation failure.

    Messages intentionally identify only a validation category: callers must
    never append untrusted source cells or raw HTML to an error or log.
    """


@dataclass(frozen=True, slots=True)
class NormalizedAlbum:
    """One normalized, provenance-backed ranking row."""

    rank: int
    title: str
    release_year: int | None
    artist_credit: str


@dataclass(slots=True)
class _Table:
    classes: frozenset[str]
    rows: list[list[str]]
    row: list[str] | None = None
    cell_parts: list[str] | None = None
    ignored_depth: int = 0


class _WikiTableParser(HTMLParser):
    """Collect tables without retaining the input document after parsing."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self._table_stack: list[_Table] = []

    @property
    def _current(self) -> _Table | None:
        return self._table_stack[-1] if self._table_stack else None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            table = _Table(
                classes=frozenset((dict(attrs).get("class") or "").split()),
                rows=[],
            )
            self.tables.append(table)
            self._table_stack.append(table)
            return

        table = self._current
        if table is None:
            return
        if tag == "tr" and table.ignored_depth == 0:
            table.row = []
        elif tag in {"td", "th"} and table.row is not None and table.ignored_depth == 0:
            table.cell_parts = []
        elif tag == "sup" and table.cell_parts is not None:
            # Citation markers are not part of an album title or artist credit.
            table.ignored_depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" and self._current and self._current.cell_parts is not None:
            self._current.cell_parts.append(" ")

    def handle_data(self, data: str) -> None:
        table = self._current
        if table is not None and table.cell_parts is not None and table.ignored_depth == 0:
            table.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._table_stack:
                self._table_stack.pop()
            return

        table = self._current
        if table is None:
            return
        if tag == "sup" and table.ignored_depth:
            table.ignored_depth -= 1
        elif tag in {"td", "th"} and table.cell_parts is not None:
            table.row = (table.row or []) + [_normalize_text("".join(table.cell_parts))]
            table.cell_parts = None
        elif tag == "tr" and table.row is not None:
            if table.row:
                table.rows.append(table.row)
            table.row = None


def _normalize_text(value: str) -> str:
    """Apply the documented Unicode and whitespace normalization."""

    return " ".join(unicodedata.normalize("NFC", value).split())


def _header_key(value: str) -> str:
    return _normalize_text(value).casefold()


def _ranking_table(html: str) -> list[list[str]]:
    parser = _WikiTableParser()
    parser.feed(html)
    parser.close()

    for table in parser.tables:
        if {"wikitable", "sortable"}.issubset(table.classes) and table.rows:
            if tuple(_header_key(cell) for cell in table.rows[0]) == EXPECTED_HEADERS:
                return table.rows
    raise CatalogueValidationError("ranking_table_not_found")


def _parse_rank(value: str) -> int:
    if not re.fullmatch(r"[0-9]+", value):
        raise CatalogueValidationError("invalid_rank")
    return int(value)


def _parse_release_year(value: str) -> int | None:
    if not value:
        return None
    if not re.fullmatch(r"[0-9]{4}", value):
        raise CatalogueValidationError("invalid_release_year")
    year = int(value)
    if not MIN_RELEASE_YEAR <= year <= MAX_RELEASE_YEAR:
        raise CatalogueValidationError("invalid_release_year")
    return year


def parse_and_validate_html(html: str) -> tuple[NormalizedAlbum, ...]:
    """Return exactly the normalized rows ranked 1 through 500.

    The input is processed in memory only.  Validation errors are deliberately
    sanitized, so they can be safely recorded as an error code by the import
    service without leaking raw third-party content.
    """

    if not isinstance(html, str):
        raise TypeError("html must be text")

    table = _ranking_table(html)
    rows: list[NormalizedAlbum] = []
    for row in table[1:]:
        if len(row) != 4:
            raise CatalogueValidationError("invalid_row_shape")
        rank, title, year, artist_credit = row
        if not title or not artist_credit:
            raise CatalogueValidationError("missing_required_text")
        rows.append(
            NormalizedAlbum(
                rank=_parse_rank(rank),
                title=_normalize_text(title),
                release_year=_parse_release_year(year),
                artist_credit=_normalize_text(artist_credit),
            )
        )

    ranks = [row.rank for row in rows]
    if len(rows) != MAX_RANK:
        raise CatalogueValidationError("invalid_row_count")
    if len(set(ranks)) != len(ranks):
        raise CatalogueValidationError("duplicate_rank")
    if set(ranks) != set(range(MIN_RANK, MAX_RANK + 1)):
        raise CatalogueValidationError("rank_set_must_be_1_through_500")
    return tuple(sorted(rows, key=lambda row: row.rank))


def canonical_normalized_rows(rows: tuple[NormalizedAlbum, ...] | list[NormalizedAlbum]) -> bytes:
    """Serialize validated rows deterministically for content idempotency."""

    ordered = sorted(rows, key=lambda row: row.rank)
    if len(ordered) != MAX_RANK or [row.rank for row in ordered] != list(range(1, 501)):
        raise CatalogueValidationError("cannot_hash_unvalidated_rows")
    payload = [
        {
            "artist_credit": row.artist_credit,
            "rank": row.rank,
            "release_year": row.release_year,
            "title": row.title,
        }
        for row in ordered
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def normalized_sha256(rows: tuple[NormalizedAlbum, ...] | list[NormalizedAlbum]) -> str:
    """Return the SHA-256 of deterministic normalized ranking content."""

    return hashlib.sha256(canonical_normalized_rows(rows)).hexdigest()
