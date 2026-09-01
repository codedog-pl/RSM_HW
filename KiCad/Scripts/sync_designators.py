#!/usr/bin/env python3
"""
Etap 2: przepisz desygnatory (Reference) z elementów schematu na footprinty
PCB, dopasowując je po właściwości "UUID" (nadanej wcześniej przez
assign_uuids.py), a nie po ich bieżącym desygnatorze.

Dzięki temu zmiana numeracji elementów na schemacie (np. R5 -> R12) nie
rozbija mapowania schemat<->PCB, dopóki footprint ma tę samą właściwość
UUID co odpowiadający mu element schematu (czyli został wcześniej
zsynchronizowany przez "Update PCB from Schematic").

Algorytm dla każdego footprintu na płytce:
  1. odczytaj jego właściwość "UUID",
  2. znajdź element schematu o tej samej właściwości "UUID" (przeszukując
     WSZYSTKIE arkusze *.kicad_sch w katalogu projektu),
  3. przepisz jego bieżący desygnator (Reference) do footprintu.

Użycie: python sync_designators.py <katalog_projektu>

Skrypt sam znajduje plik płytki: <katalog_projektu>/<nazwa_katalogu>.kicad_pcb
(w tym projekcie: RS/RS.kicad_pcb) oraz wszystkie arkusze *.kicad_sch w tym
samym katalogu.
"""

import sys
from pathlib import Path

from kicad_sexp import (
    find_blocks,
    find_placed_schematic_symbols,
    get_property,
    replace_blocks,
    set_property_value,
)


def build_uuid_to_reference_map(sch_files):
    """Zeskanuj wszystkie arkusze schematu i zbuduj mapę {uuid: reference}."""
    uuid_map = {}
    duplicates = []
    total_symbols = 0
    total_with_uuid = 0

    for sch_path in sch_files:
        content = sch_path.read_text(encoding='utf-8')
        symbols = find_placed_schematic_symbols(content)
        total_symbols += len(symbols)

        for start, end in symbols:
            block = content[start:end]
            reference = get_property(block, "Reference")
            uuid_str = get_property(block, "UUID")

            if not uuid_str:
                continue
            total_with_uuid += 1

            if uuid_str in uuid_map and uuid_map[uuid_str] != reference:
                duplicates.append((uuid_str, uuid_map[uuid_str], reference, sch_path.name))
            uuid_map[uuid_str] = reference

    return uuid_map, total_symbols, total_with_uuid, duplicates


def main():
    if len(sys.argv) != 2:
        print("Użycie: python sync_designators.py <katalog_projektu>")
        sys.exit(1)

    directory = Path(sys.argv[1])
    if not directory.is_dir():
        print(f"BŁĄD: {directory} nie jest katalogiem")
        sys.exit(1)

    pcb_path = directory / f"{directory.name}.kicad_pcb"
    if not pcb_path.exists():
        print(f"BŁĄD: nie znaleziono {pcb_path}")
        print("Oczekiwano pliku o nazwie takiej jak katalog projektu, "
              f"np. dla katalogu '{directory.name}' -> '{directory.name}.kicad_pcb'.")
        sys.exit(1)

    sch_files = sorted(directory.glob('*.kicad_sch'))
    if not sch_files:
        print(f"BŁĄD: brak plików *.kicad_sch w katalogu {directory}")
        sys.exit(1)

    print(f"Płytka: {pcb_path.name}")
    print(f"Arkusze schematu ({len(sch_files)}):")
    for f in sch_files:
        print(f"  - {f.name}")

    print("\nSkanowanie schematów...")
    uuid_map, total_symbols, total_with_uuid, duplicates = build_uuid_to_reference_map(sch_files)
    print(f"Elementów na schemacie: {total_symbols}, z właściwością UUID: {total_with_uuid}")

    if total_with_uuid == 0:
        print("\nBŁĄD: żaden element schematu nie ma właściwości UUID!")
        print(f"Uruchom najpierw: python assign_uuids.py {directory}")
        print("a następnie w KiCad: Update PCB from Schematic.")
        sys.exit(1)

    if duplicates:
        print(f"\nUWAGA: {len(duplicates)} UUID występuje z różnymi desygnatorami "
              "w różnych miejscach schematu (nie powinno się zdarzyć):")
        for uuid_str, ref1, ref2, fname in duplicates:
            print(f"  {uuid_str}: '{ref1}' vs '{ref2}' (w {fname})")

    print("\nSkanowanie PCB...")
    pcb_content = pcb_path.read_text(encoding='utf-8')
    footprint_spans = find_blocks(pcb_content, 'footprint')
    print(f"Znaleziono {len(footprint_spans)} footprintów")

    backup_path = pcb_path.with_suffix(pcb_path.suffix + '.bak')
    backup_path.write_text(pcb_content, encoding='utf-8')
    print(f"Backup utworzony: {backup_path}")

    replacements = []
    changed = []
    unchanged = 0
    no_uuid = 0
    not_found = []

    for start, end in footprint_spans:
        block = pcb_content[start:end]
        old_reference = get_property(block, "Reference") or "UNKNOWN"
        uuid_str = get_property(block, "UUID")

        if not uuid_str:
            no_uuid += 1
            continue

        if uuid_str not in uuid_map:
            not_found.append((old_reference, uuid_str))
            continue

        new_reference = uuid_map[uuid_str]
        if new_reference == old_reference:
            unchanged += 1
            continue

        new_block, ok = set_property_value(block, "Reference", new_reference)
        if not ok:
            print(f"  BŁĄD: nie udało się podmienić Reference w footprincie {old_reference}")
            continue

        replacements.append((start, end, new_block))
        changed.append((old_reference, new_reference, uuid_str))
        print(f"  {old_reference:15} -> {new_reference:15} (UUID: {uuid_str[:8]}...)")

    if not_found:
        print(f"\nUWAGA: {len(not_found)} footprintów ma UUID nieznane schematowi:")
        for ref, uid in not_found:
            print(f"  {ref:15} UUID: {uid}")

    print(f"\n{'=' * 60}")
    print(f"Zmienione desygnatory: {len(changed)}")
    print(f"Bez zmian (już poprawne): {unchanged}")
    print(f"Bez właściwości UUID: {no_uuid}")
    print(f"UUID nieznane schematowi: {len(not_found)}")

    if no_uuid > 0:
        print(f"\n{no_uuid} footprintów nie ma właściwości UUID. Możliwe przyczyny:")
        print("  - assign_uuids.py nie był uruchamiany / był uruchomiony po ostatnim sync")
        print("  - w KiCad nie wykonano jeszcze 'Update PCB from Schematic'")
        print("Rozwiązanie: uruchom assign_uuids.py, potem Update PCB from Schematic w KiCad.")

    if replacements:
        new_content = replace_blocks(pcb_content, replacements)
        pcb_path.write_text(new_content, encoding='utf-8')
        print(f"\nPCB zaktualizowany: {pcb_path}")
    else:
        print("\nBrak zmian do zapisania.")


if __name__ == '__main__':
    main()
