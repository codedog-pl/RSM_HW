import shutil
from skip import Schematic

########################################
FILEPATH = r"..\RS\RS.kicad_sch"
########################################

backup_path = FILEPATH + ".bak"
shutil.copy2(FILEPATH, backup_path)

sch = Schematic(FILEPATH)

########################################
master = sch.symbol.R4
targets = ["R3", "R5"]
########################################

def relative_offset(symbol, field):
    sx, sy = symbol.at.value[0], symbol.at.value[1]
    fx, fy, frot = field.at.value[0], field.at.value[1], field.at.value[2]
    return (fx - sx, fy - sy, frot)

def apply_field(symbol, field, offset):
    ox, oy, rot = offset
    new_x = symbol.at.value[0] + ox
    new_y = symbol.at.value[1] + oy
    field.at.value = [new_x, new_y, rot]
#    print(f"  -> ustawiono at = [{new_x}, {new_y}, {rot}]")

def copy_justify(src_field, dst_field):
    try:
        dst_field.effects.justify.value = src_field.effects.justify.value
        print("  OK  justify")
    except Exception as e:
        pass
#        print(f"  POMINIETO justify -> {e}")

ref_offset = relative_offset(master, master.Reference)
val_offset = relative_offset(master, master.Value)

for ref in targets:
    sym = getattr(sch.symbol, ref)
    print(f"--- {ref} ---")
    apply_field(sym, sym.Reference, ref_offset)
    copy_justify(master.Reference, sym.Reference)
    apply_field(sym, sym.Value, val_offset)
    copy_justify(master.Value, sym.Value)

sch.overwrite()
print("OK.")
