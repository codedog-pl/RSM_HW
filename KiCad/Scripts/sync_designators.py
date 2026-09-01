#!/usr/bin/env python3
"""
Skrypt do synchronizacji desygnatorów w PCB na podstawie UUID ze schematu.
Uruchomienie: python sync_designators.py project.kicad_sch project.kicad_pcb
"""

import sys
import re
from pathlib import Path
from collections import defaultdict

def read_file(filepath):
    """Odczytaj plik KiCad jako tekst"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def write_file(filepath, content):
    """Zapisz plik KiCad"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def extract_symbols(content):
    """
    Wyodrębnij symbole ze schematu z ich UUID i desygnatorami.
    Zwraca dict: {uuid: reference}
    """
    uuid_map = {}
    
    pos = 0
    while True:
        match = re.search(r'\(symbol\s', content[pos:])
        if not match:
            break
        
        start = pos + match.start()
        
        # Znalezienie odpowiadającego zamykającego nawiasu
        paren_count = 0
        in_string = False
        escape_next = False
        end = start
        
        for i in range(start, len(content)):
            char = content[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and (i == 0 or content[i-1] != '\\'):
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        end = i + 1
                        break
        
        symbol_text = content[start:end]
        
        # Wyodrębnij reference
        ref_match = re.search(r'\(reference\s"([^"]+)"', symbol_text)
        reference = ref_match.group(1) if ref_match else None
        
        # Wyodrębnij UUID
        uuid_match = re.search(r'\(property\s"UUID"\s"([^"]+)"', symbol_text)
        uuid_str = uuid_match.group(1) if uuid_match else None
        
        if uuid_str and reference:
            uuid_map[uuid_str] = reference
        
        pos = end
    
    return uuid_map

def extract_footprints(content):
    """
    Wyodrębnij footprinty z PCB.
    Zwraca listę: [(start_pos, end_pos, footprint_text, reference, uuid)]
    """
    footprints = []
    
    pos = 0
    while True:
        match = re.search(r'\(footprint\s', content[pos:])
        if not match:
            break
        
        start = pos + match.start()
        
        # Znalezienie odpowiadającego zamykającego nawiasu
        paren_count = 0
        in_string = False
        escape_next = False
        end = start
        
        for i in range(start, len(content)):
            char = content[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and (i == 0 or content[i-1] != '\\'):
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        end = i + 1
                        break
        
        footprint_text = content[start:end]
        
        # Wyodrębnij reference
        ref_match = re.search(r'\(reference\s"([^"]+)"', footprint_text)
        reference = ref_match.group(1) if ref_match else "UNKNOWN"
        
        # Wyodrębnij UUID
        uuid_match = re.search(r'\(property\s"UUID"\s"([^"]+)"', footprint_text)
        uuid_str = uuid_match.group(1) if uuid_match else None
        
        footprints.append((start, end, footprint_text, reference, uuid_str))
        pos = end
    
    return footprints

def update_footprint_reference(footprint_text, new_reference):
    """Zmień reference w footpricie"""
    new_text = re.sub(
        r'\(reference\s"[^"]+"\)',
        f'(reference "{new_reference}")',
        footprint_text
    )
    return new_text

def main():
    if len(sys.argv) < 3:
        print("Użycie: python sync_designators.py <project.kicad_sch> <project.kicad_pcb>")
        sys.exit(1)
    
    sch_path = Path(sys.argv[1])
    pcb_path = Path(sys.argv[2])
    
    if not sch_path.exists():
        print(f"BŁĄD: Plik {sch_path} nie istnieje")
        sys.exit(1)
    
    if not pcb_path.exists():
        print(f"BŁĄD: Plik {pcb_path} nie istnieje")
        sys.exit(1)
    
    print(f"Czytam schemat: {sch_path}")
    sch_content = read_file(sch_path)
    
    print(f"Czytam PCB: {pcb_path}")
    pcb_content = read_file(pcb_path)
    
    # Wyodrębnij mapowanie UUID → reference ze schematu
    print("\nSkanowanie schematu...")
    uuid_map = extract_symbols(sch_content)
    print(f"Znaleziono {len(uuid_map)} elementów ze UUID")
    
    if len(uuid_map) == 0:
        print("BŁĄD: Brak elementów z UUID w schemacie!")
        print("Uruchom najpierw: python assign_uuids.py project.kicad_sch")
        sys.exit(1)
    
    # Wyodrębnij footprinty z PCB
    print("Skanowanie PCB...")
    footprints = extract_footprints(pcb_content)
    print(f"Znaleziono {len(footprints)} footprintów")
    
    # Backup
    backup_path = pcb_path.with_suffix(pcb_path.suffix + '.bak')
    write_file(backup_path, pcb_content)
    print(f"Backup utworzony: {backup_path}")
    
    # Przetwórz każdą footprinkę
    changes = []
    offset = 0
    no_uuid_count = 0
    
    for start, end, footprint_text, old_reference, uuid_str in footprints:
        if not uuid_str:
            no_uuid_count += 1
            continue
        
        if uuid_str not in uuid_map:
            print(f"  UWAGA: {old_reference} ma UUID {uuid_str}, ale nie ma go w schemacie!")
            continue
        
        new_reference = uuid_map[uuid_str]
        
        if old_reference != new_reference:
            new_footprint = update_footprint_reference(footprint_text, new_reference)
            
            # Zaktualizuj content z offset
            start_adj = start + offset
            end_adj = end + offset
            pcb_content = pcb_content[:start_adj] + new_footprint + pcb_content[end_adj:]
            
            # Zaktualizuj offset
            offset += len(new_footprint) - len(footprint_text)
            
            changes.append((old_reference, new_reference, uuid_str))
            print(f"  {old_reference:15} → {new_reference:15} (UUID: {uuid_str[:8]}...)")
        else:
            print(f"  {old_reference:15} ✓ (już poprawny)")
    
    # Podsumowanie
    print(f"\n{'='*60}")
    print(f"Zmienione desygnatory: {len(changes)}")
    print(f"Bez zmian: {len(footprints) - len(changes) - no_uuid_count}")
    print(f"Brak UUID: {no_uuid_count}")
    
    if no_uuid_count > 0:
        print(f"\nUWAGA: {no_uuid_count} footprintów nie ma UUID!")
        print("Możliwe przyczyny:")
        print("  - Footprinty zostały dodane po ostatniej synchronizacji")
        print("  - Synchronizacja ze schematem nie skopiowała UUID")
        print("Rozwiązanie: Update PCB from Schematic jeszcze raz")
    
    # Zapisz plik
    if changes:
        write_file(pcb_path, pcb_content)
        print(f"\nPCB zaktualizowany: {pcb_path}")
    else:
        print(f"\nBrak zmian do dokonania")

if __name__ == '__main__':
    main()
