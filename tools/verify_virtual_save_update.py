#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
checks = {
    "RAM backend": ("kvm/VmSkel/src/Java_nds_File.c", '"RAM-VIRTUAL"'),
    "RAM RMS path": ("kvm/VmSkel/src/Java_nds_File.c", 'PSTROS_RAM_RMS_PATH'),
    "RAM RMS store": ("kvm/VmSkel/src/Java_nds_File.c", 'pstrosRamRmsStore'),
    "no boot ENODEV": ("kvm/VmSkel/src/Java_nds_File.c", 'pstrosSaveErrno = 0;'),
    "ScratchPad RAM success": ("kvm/VmExtra/src/resource.c", 'return 1;'),
    "UI virtual mode": ("kvm/VmSkel/src/nds_main.c", 'MODE: VIRTUAL RAM SAVE'),
    "boot RAM ready": ("kvm/VmSkel/src/nds_main.c", 'SAVE RAM READY'),
}
failed = []
for name, (rel, token) in checks.items():
    text = (root / rel).read_text(encoding="utf-8", errors="replace")
    if token not in text:
        failed.append(name)

bad_boot = 'pstrosSaveErrno = ENODEV;\\n    pstrosSaveStage = 40'
text = (root / "kvm/VmSkel/src/Java_nds_File.c").read_text(encoding="utf-8")
if bad_boot in text:
    failed.append("legacy boot ENODEV policy still present")

if failed:
    print("[FAIL] " + ", ".join(failed))
    sys.exit(1)
print("[OK] v59 Empty virtual RAM save update markers verified.")
