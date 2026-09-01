#!/usr/bin/env python3
"""
Wspólne funkcje do bezpiecznej pracy z fragmentami plików KiCad (S-expression),
używane przez assign_uuids.py i sync_designators.py.

To NIE jest pełny parser S-expression - to proste zliczanie nawiasów
(z poszanowaniem cudzysłowów i znaków ucieczki), które pozwala:
  - znaleźć granice pojedynczego bloku, np. (symbol ...) albo (footprint ...),
  - odróżnić UMIESZCZONE na schemacie symbole od definicji w (lib_symbols ...),
  - odczytać/podmienić wartość konkretnego (property "Nazwa" "wartość" ...).

Działa to, bo pliki .kicad_sch / .kicad_pcb generowane przez KiCad mają stały,
przewidywalny format (jedno pole na linię, spójne wcięcia), a nie dlatego,
że obsługujemy pełną gramatykę S-expression.
"""

import re

UUID_RE = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'


def find_matching_paren(content, start):
    """
    `start` musi wskazywać na znak '(' otwierający blok.
    Zwraca indeks TUŻ ZA odpowiadającym mu ')' (czyli content[start:end] to cały blok).
    """
    if content[start] != '(':
        raise ValueError(f"Pozycja {start} nie wskazuje na '(' tylko na {content[start]!r}")

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start, len(content)):
        ch = content[i]

        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue

        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return i + 1

    raise ValueError("Niezbalansowane nawiasy - nie znaleziono końca bloku")


def find_blocks(content, keyword):
    """
    Znajdź wszystkie bloki `(keyword ...)` zaczynające się na początku linii
    (z dowolnym wcięciem spacjami/tabami). NIE schodzi rekurencyjnie w głąb
    znalezionych bloków (przeszukiwanie kontynuowane jest od pozycji za blokiem).

    Zwraca listę (start, end), gdzie start wskazuje na '(', a end na pozycję
    tuż za odpowiadającym ')'.
    """
    results = []
    pos = 0
    pattern = re.compile(r'(?m)^[ \t]*\(' + re.escape(keyword) + r'\b')
    while True:
        m = pattern.search(content, pos)
        if not m:
            break
        start = content.index('(', m.start())
        end = find_matching_paren(content, start)
        results.append((start, end))
        pos = end
    return results


def find_placed_schematic_symbols(content):
    """
    Jak find_blocks(content, 'symbol'), ale tylko elementy UMIESZCZONE na
    schemacie (blok zaczyna się od (symbol (lib_id ...) ...)) -  z pominięciem
    definicji bibliotecznych wewnątrz (lib_symbols ...), które mają postać
    (symbol "Biblioteka:Nazwa" ...) i nie mają pola lib_id.
    """
    results = []
    for start, end in find_blocks(content, 'symbol'):
        block = content[start:end]
        after_keyword = block[len('(symbol'):].lstrip()
        if after_keyword.startswith('(lib_id'):
            results.append((start, end))
    return results


def get_property(block, name):
    """Zwróć wartość (property "name" "wartość" ...) z bloku, albo None."""
    m = re.search(r'\(property\s+"' + re.escape(name) + r'"\s+"([^"]*)"', block)
    return m.group(1) if m else None


def set_property_value(block, name, new_value):
    """
    Podmień wartość istniejącej (property "name" "...") w bloku (pierwsze
    wystąpienie), nie ruszając pozostałych pól tej właściwości (at/layer/uuid/
    effects itd.). Zwraca (nowy_block, czy_znaleziono_i_podmieniono).
    """
    pattern = re.compile(r'(\(property\s+"' + re.escape(name) + r'"\s+")([^"]*)(")')
    new_block, n = pattern.subn(lambda m: m.group(1) + new_value + m.group(3), block, count=1)
    return new_block, n > 0


def get_symbol_uuid(block):
    """Zwróć wartość top-level pola (uuid "...") symbolu/footprintu (jego własny,
    natywny identyfikator KiCad - NIE naszą właściwość "UUID")."""
    m = re.search(r'\(uuid\s+"(' + UUID_RE + r')"\)', block)
    return m.group(1) if m else None


def replace_blocks(content, replacements):
    """
    `replacements`: lista (start, end, new_text) posortowana wg start rosnąco,
    o nienachodzących na siebie przedziałach [start, end) w oryginalnym `content`.
    Zwraca nowy tekst z podmienionymi fragmentami.
    """
    parts = []
    last = 0
    for start, end, new_text in replacements:
        parts.append(content[last:start])
        parts.append(new_text)
        last = end
    parts.append(content[last:])
    return ''.join(parts)
