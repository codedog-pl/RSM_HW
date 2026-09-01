# Remote Sensors Module (HARDWARE)

## Folder structure
- *Docs* - datasheets and various documentation
- *KiCad* - Schematics and PCB
  - *CustomFootprints*
  - *CustomSymbols*
  - *RS* - **main KiCad project**
  - *Scripts* - Python helper scripts
- *Simulations* - CircuitJS simulations of functional blocks.
  
## Using Python scripts

To use Python scripts open the `KiCad` directory in Terminal.

### Re-annotate schematics with exiting PCB

- Assign UUIDs to schematics symbols:
  ```powershell
  python .\Scripts\assign_uuids.py .\RS 
  ```
- Open existing PCB and `Update PCB from schematics` to copy assigned UUIDs to the PCB file. **SAVE CHANGES!**
- Re-annotate the schematics, then **SAVE CHANGES!**
- Close both schematics and PCB views.
- Synchronize PCB footprint designators with schematics designators via UUIDs:
  ```powershell
  python .\Scripts\sync_designators.py .\RS
  ```
- Re-open schematics editor. `Update PCB from schematics` and
  **SAVE CHANGES** to rename nets using new designators.
