#!/usr/bin/env python3
"""
Skrypt do nadawania UUID wszystkim elementom w schemacie KiCad.
Uruchomienie: python assign_uuids.py project.kicad_sch
"""

import sys
import re
from pathlib import Path
from uuid import uuid4
from datetime import datetime

def read_sexp_file(filepath):
    """Odczytaj plik KiCad jako tekst"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def write_sexp_file(filepath, content):
    """Zapisz plik KiCad"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def extract_symbols(content):
    """
    Wyodrębnij sekcje symboli ze schematu.
    Zwraca listę: [(start_pos, end_pos, symbol_text, reference)]
    """
    symbols = []
    
    # Regex do znalezienia bloków (symbol ...)
    # To jest uproszczone - szuka (symbol na początku i maczy odpowiadający )
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
        reference = ref_match.group(1) if ref_match else "UNKNOWN"
        
        symbols.append((start, end, symbol_text, reference))
        pos = end
    
    return symbols

def add_uuid_to_symbol(symbol_text, uuid_str):
    """
    Dodaj lub nadpisz pole UUID w symbolu.
    Wstawia go jako property zaraz po reference.
    """
    # Szukaj istniejącego UUID i usuń je
    symbol_text = re.sub(r'\s*\(property\s"UUID"\s"[^"]*"\)', '', symbol_text)
    
    # Znajdź koniec linii (reference "...")
    ref_pattern = r'(\(reference\s"[^"]+"\))'
    match = re.search(ref_pattern, symbol_text)
    
    if not match:
        print(f"  BŁĄD: Nie znaleziono reference w symbolu")
        return symbol_text
    
    insert_pos = match.end()
    
    # Wstaw property UUID
    uuid_prop = f'\n  (property "UUID" "{uuid_str}")'
    symbol_text = symbol_text[:insert_pos] + uuid_prop + symbol_text[insert_pos:]
    
    return symbol_text

def main():
    if len(sys.argv) < 2:
        print("Użycie: python assign_uuids.py <project.kicad_sch>")
        sys.exit(1)
    
    sch_path = Path(sys.argv[1])
    
    if not sch_path.exists():
        print(f"BŁĄD: Plik {sch_path} nie istnieje")
        sys.exit(1)
    
    print(f"Czytam schemat: {sch_path}")
    content = read_sexp_file(sch_path)
    
    # Backup
    backup_path = sch_path.with_suffix(sch_path.suffix + '.bak')
    write_sexp_file(backup_path, content)
    print(f"Backup utworzony: {backup_path}")
    
    # Wyodrębnij symbole
    symbols = extract_symbols(content)
    print(f"\nZnaleziono {len(symbols)} elementów")
    
    if len(symbols) == 0:
        print("Brak elementów do przetworzenia")
        return
    
    # Przetwórz każdy symbol
    offset = 0
    for start, end, symbol_text, reference in symbols:
        uuid_str = str(uuid4())
        new_symbol = add_uuid_to_symbol(symbol_text, uuid_str)
        
        # Zaktualizuj content z offset
        start_adj = start + offset
        end_adj = end + offset
        content = content[:start_adj] + new_symbol + content[end_adj:]
        
        # Zaktualizuj offset
        offset += len(new_symbol) - len(symbol_text)
        
        print(f"  {reference:15} → UUID: {uuid_str}")
    
    # Zapisz plik
    write_sexp_file(sch_path, content)
    print(f"\nSchematy zaktualizowany: {sch_path}")
    print("Teraz zsynchronizuj PCB ze schematem (Update PCB from Schematic)")

if __name__ == '__main__':
    main()
