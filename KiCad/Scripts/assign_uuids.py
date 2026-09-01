#!/usr/bin/env python3
"""
Etap 1: nadaj każdemu UMIESZCZONEMU na schemacie elementowi (symbolowi)
nową, trwałą właściwość "UUID" - we WSZYSTKICH plikach *.kicad_sch
znalezionych w podanym katalogu (projekt składa się z wielu arkuszy).

Ta właściwość, w odróżnieniu od desygnatora (Reference), nie zmienia się
przy renumeracji elementów na schemacie i po "Update PCB from Schematic"
zostanie skopiowana także do odpowiadającego footprintu na płytce - dzięki
czemu sync_designators.py będzie mógł później dopasować footprint do
elementu schematu niezależnie od jego bieżącego desygnatora.

Skrypt jest bezpieczny do wielokrotnego uruchamiania: elementy, które już
mają właściwość "UUID", zachowują swoją dotychczasową wartość.

Użycie: python assign_uuids.py <katalog_projektu>
Przykład: python assign_uuids.py .\\RS
"""

import re
import sys
from pathlib import Path
from uuid import uuid4

from kicad_sexp import find_placed_schematic_symbols, get_property, replace_blocks

PROPERTY_INDENT_UNIT = '\t'


def build_uuid_property_block(block, indent, new_uuid):
    """
    Zbuduj tekst nowej (property "UUID" "...") w stylu identycznym jak inne
    ukryte, niestandardowe właściwości w tym pliku (np. "Mfg Part #", "URL"):
    pozycja = pozycja własna symbolu, ukryta, bez etykiety nazwy.
    `indent` to wcięcie sąsiednich pól symbolu (np. "\t\t"), pobrane z pola (uuid ...).
    """
    at_match = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\s+[-\d.]+\)', block)
    x, y = (at_match.group(1), at_match.group(2)) if at_match else ('0', '0')

    i1 = indent + PROPERTY_INDENT_UNIT
    i2 = i1 + PROPERTY_INDENT_UNIT
    i3 = i2 + PROPERTY_INDENT_UNIT
    lines = [
        f'{indent}(property "UUID" "{new_uuid}"',
        f'{i1}(at {x} {y} 0)',
        f'{i1}(hide yes)',
        f'{i1}(show_name no)',
        f'{i1}(do_not_autoplace no)',
        f'{i1}(effects',
        f'{i2}(font',
        f'{i3}(size 1.27 1.27)',
        f'{i2})',
        f'{i1})',
        f'{indent})',
    ]
    return '\n'.join(lines)


def process_symbol_block(block):
    """
    Zwraca (new_block_or_None, uuid_str, is_new).
    new_block_or_None: None, jeśli blok nie wymaga zmiany w treści.
    """
    existing = get_property(block, "UUID")
    if existing:
        return None, existing, False

    # Miejsce wstawienia: zaraz za polem (uuid "...") - to jest WŁASNE, natywne
    # pole symbolu (jego "instance uuid"), obecne w KAŻDYM umieszczonym
    # elemencie, zawsze PRZED sekcją (instances ...). NIE mylić z (reference ...),
    # które w nowym formacie KiCada występuje tylko wewnątrz (instances (project
    # (path ... (reference "...") (unit ...)))) - wstawienie tam property łamie
    # składnię pliku (to właśnie był błąd w poprzedniej wersji tego skryptu).
    anchor = re.search(r'\n([ \t]*)\(uuid\s+"[0-9a-fA-F-]{36}"\)', block)
    if not anchor:
        return None, None, False

    indent = anchor.group(1)
    new_uuid = str(uuid4())
    prop_text = build_uuid_property_block(block, indent, new_uuid)

    insert_pos = anchor.end()
    new_block = block[:insert_pos] + '\n' + prop_text + block[insert_pos:]
    return new_block, new_uuid, True


def process_file(path):
    content = path.read_text(encoding='utf-8')

    backup_path = path.with_suffix(path.suffix + '.bak')
    backup_path.write_text(content, encoding='utf-8')

    symbols = find_placed_schematic_symbols(content)
    print(f"\n{path.name}: znaleziono {len(symbols)} umieszczonych elementów")

    replacements = []
    added = kept = skipped = 0
    for start, end in symbols:
        block = content[start:end]
        new_block, uid, is_new = process_symbol_block(block)
        if uid is None:
            skipped += 1
            print(f"  UWAGA: element bez pola (uuid ...) - pominięty ({block[:60].splitlines()[0]}...)")
            continue
        if is_new:
            added += 1
            replacements.append((start, end, new_block))
        else:
            kept += 1

    new_content = replace_blocks(content, replacements) if replacements else content

    changed = new_content != content
    if changed:
        path.write_text(new_content, encoding='utf-8')

    print(f"  nowe UUID: {added}, już posiadały UUID: {kept}, pominięte: {skipped}")
    return added, kept, skipped, changed


def main():
    if len(sys.argv) != 2:
        print("Użycie: python assign_uuids.py <katalog_projektu>")
        sys.exit(1)

    directory = Path(sys.argv[1])
    if not directory.is_dir():
        print(f"BŁĄD: {directory} nie jest katalogiem")
        sys.exit(1)

    sch_files = sorted(directory.glob('*.kicad_sch'))
    if not sch_files:
        print(f"BŁĄD: brak plików *.kicad_sch w katalogu {directory}")
        sys.exit(1)

    print(f"Znaleziono {len(sch_files)} plików schematu w {directory}:")
    for f in sch_files:
        print(f"  - {f.name}")

    total_added = total_kept = total_skipped = 0
    changed_files = []
    for f in sch_files:
        added, kept, skipped, changed = process_file(f)
        total_added += added
        total_kept += kept
        total_skipped += skipped
        if changed:
            changed_files.append(f.name)

    print(f"\n{'=' * 60}")
    print(f"RAZEM: nowe UUID: {total_added}, już istniały: {total_kept}, pominięte: {total_skipped}")
    if changed_files:
        print(f"Zmodyfikowane pliki: {', '.join(changed_files)}")
        print("\nTeraz otwórz projekt w KiCad i zsynchronizuj PCB ze schematem")
        print("(Tools -> Update PCB from Schematic), aby właściwość UUID trafiła")
        print("do footprintów. Następnie uruchom sync_designators.py.")
    else:
        print("Brak zmian - wszystkie elementy miały już właściwość UUID.")


if __name__ == '__main__':
    main()
