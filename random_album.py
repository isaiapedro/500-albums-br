#!/usr/bin/env python3
"""Print one random album from the approved Discoteca Básica ranking source.

This is a manual, read-only selector.  It fetches the current REST HTML only
for this invocation and never writes the response to disk.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE_URL = (
    "https://pt.wikipedia.org/api/rest_v1/page/html/"
    "Lista_dos_500_maiores_discos_da_m%C3%BAsica_brasileira_pelo_Discoteca_B%C3%A1sica"
)
ATTRIBUTION = (
    "Source: Portuguese Wikipedia, Lista dos 500 maiores discos da música "
    "brasileira pelo Discoteca Básica (CC BY-SA)."
)


@dataclass(frozen=True)
class Album:
    rank: int
    title: str
    release_year: str
    artist: str


class RankingTableParser(HTMLParser):
    """Extract cells from the source page's sortable ranking table."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_ranking_table = False
        self._table_depth = 0
        self._in_row = False
        self._row: list[str] = []
        self._cell_parts: list[str] | None = None
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and not self._in_ranking_table:
            classes = attributes.get("class", "") or ""
            if "wikitable" in classes.split() and "sortable" in classes.split():
                self._in_ranking_table = True
                self._table_depth = 1
                return
        elif tag == "table" and self._in_ranking_table:
            self._table_depth += 1

        if not self._in_ranking_table:
            return
        if tag == "tr":
            self._in_row = True
            self._row = []
        elif tag in {"td", "th"} and self._in_row:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_ranking_table:
            return
        if tag in {"td", "th"} and self._cell_parts is not None:
            text = " ".join("".join(self._cell_parts).split())
            self._row.append(text)
            self._cell_parts = None
        elif tag == "tr" and self._in_row:
            if self._row:
                self.rows.append(self._row)
            self._in_row = False
        elif tag == "table":
            self._table_depth -= 1
            if self._table_depth == 0:
                self._in_ranking_table = False


def parse_albums(html: str) -> list[Album]:
    parser = RankingTableParser()
    parser.feed(html)
    parser.close()

    if not parser.rows:
        raise ValueError("Could not find the ranking table in the source response.")

    headers = [cell.casefold() for cell in parser.rows[0]]
    expected = ["posição", "título", "ano de lançamento", "artista(s)"]
    if headers != expected:
        raise ValueError(f"Unexpected ranking-table headers: {parser.rows[0]!r}")

    albums: list[Album] = []
    for row in parser.rows[1:]:
        if len(row) != 4:
            raise ValueError(f"Unexpected ranking-table row: {row!r}")
        try:
            rank = int(row[0])
        except ValueError as error:
            raise ValueError(f"Invalid album rank: {row[0]!r}") from error
        albums.append(Album(rank, row[1], row[2], row[3]))

    ranks = {album.rank for album in albums}
    if len(albums) != 500 or ranks != set(range(1, 501)):
        raise ValueError("Source must contain each unique rank from 1 through 500.")
    return albums


def fetch_albums(timeout: float) -> list[Album]:
    request = Request(SOURCE_URL, headers={"User-Agent": "album-journey-mvp/0.1"})
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8")
    return parse_albums(html)


def main() -> int:
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("--seed", type=int, help="Optional seed for a repeatable selection.")
    argument_parser.add_argument("--timeout", type=float, default=20, help="HTTP timeout in seconds (default: 20).")
    args = argument_parser.parse_args()

    try:
        albums = fetch_albums(args.timeout)
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, ValueError) as error:
        print(f"Could not select an album: {error}", file=sys.stderr)
        return 1

    chooser = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    album = chooser.choice(albums)
    print(f"#{album.rank}: {album.title} — {album.artist} ({album.release_year})")
    print(ATTRIBUTION)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
