# DoJa v59 Empty

DoJa v59 Empty is a generic DoJa/KVM-to-Nintendo-DS runtime and build environment.

It prepares a DoJa game from its original **JAR**, **JAM**, and **ScratchPad (`.sp`)** files and builds a standalone Nintendo DS ROM.

The runtime is not permanently locked to one title. To change games, run `build-doja.bat` again with another JAR/JAM/SP set.

> **Current status:** v59 is also a diagnostic build for the DoJa `Graphics3D` path.  
> 2D rendering, indexed-image transparency, virtual RAM save, top-level JAR optimization, and FF4A compatibility work are substantially functional, while the Final Fantasy IV: The After Years world-map 3D renderer is still under investigation.

---

## Warning

**Warning: The internal ScratchPad resource layout is no longer blindly repacked to STORED. Some games may therefore still have slow loading or lag while compressed resources are being loaded.**

The original game-visible ScratchPad layout is deliberately preserved for compatibility with games that depend on exact offsets, embedded resources, bundled save data, or pre-installed Continue data.

The complete prepared ScratchPad may still be wrapped in Nintendo LZ77 for ROM embedding. This is different from repacking the archives *inside* the ScratchPad.

---

## User-facing build files

Use only:

```text
build-doja.bat
build.bat
```

### `build-doja.bat`

Use this when preparing a new game.

The script asks for:

```text
1. JAR file
2. JAM file
3. ScratchPad SP file
4. 4-character ROM/save code
5. Optional ROM name
6. Optional Japanese TTF/TTC font
```

It then prepares the game, verifies the generated files, and starts the NDS build.

### `build.bat`

Use this when the source tree has already been prepared for a game.

---

## ROM filename

The generated ROM uses only the sanitized game name.

Example:

```text
Final Fantasy IV The After
```

becomes:

```text
final_fantasy_iv_the_after.nds
```

No `_doja_v59` suffix is added to the final ROM filename.

---

## Requirements

### Windows

The included batch workflow is intended for Windows.

### Python 3

Install Python 3 and make sure either `py.exe` or `python.exe` is available in `PATH`.

Pillow is required for image/font preparation:

```bat
py -3 -m pip install pillow
```

### Nintendo DS toolchain

Install a working devkitPro Nintendo DS environment containing the tools used by the project, including:

- devkitARM
- libnds
- Calico / ARM7 support used by the project
- `make`
- `ndstool`

Large DoJa games should preferably be tested in **DSi mode**.

---

# Build pipeline

A normal `build-doja.bat` run performs the following work:

1. Reads the JAM file.
2. Detects `AppClass`, `AppParam`, ScratchPad size, and supported display metadata.
3. Strips a supported host/emulator ScratchPad wrapper when necessary.
4. Preserves the game-visible ScratchPad layout.
5. Rebuilds the **top-level `game.jar` with STORED entries**.
6. Applies only exact-signature game-specific bytecode patches.
7. Builds the CP932/SJIS font and encoding tables.
8. Packages the ScratchPad for ROM embedding.
9. Generates runtime metadata and the prepared JAM.
10. Verifies the prepared data.
11. Builds the standalone `.nds` ROM.

---

# JAR and ScratchPad policy

## Top-level JAR

The top-level `game.jar` is rebuilt using **STORED** ZIP/JAR entries.

Original path:

```text
compressed class/resource
        -> DEFLATE
        -> KVM loading
```

Prepared path:

```text
STORED class/resource
        -> direct read/copy
        -> KVM loading
```

This reduces class-loader and resource-loader CPU overhead.

---

## ScratchPad

The `.sp` is treated differently.

DoJa games may use the ScratchPad for much more than normal save data. It may contain:

- bundled Continue state
- save data
- maps
- sprites
- field data
- battle data
- audio
- nested ZIP/JAR packs
- private offset tables
- private length tables

Rebuilding an internal archive as STORED changes its size. If the game uses private offsets, moving that data can break the game.

For that reason, v59 does **not** blindly repack unknown internal ScratchPad archives.

### FF4A example

For the tested Final Fantasy IV: The After Years build:

```text
Host/emulator SP file : 778304 bytes
Host wrapper          : 64 bytes
Game-visible SP       : 778240 bytes
Bundled Continue area : 0..25599
```

The 778240-byte game-visible ScratchPad is preserved byte-for-byte.

The original internal resource packs remain DEFLATE-compressed. FF4A uses the ARM-native inflater path to reduce the cost of reading them without changing their binary layout.

---

# Save architecture

v59 uses **Virtual RAM Save**.

At boot, the application sees a valid save backend even if FAT/SD storage is not attached.

Typical lower-screen status:

```text
MODE: VIRTUAL RAM SAVE
SAVE: READY
MEDIA: RAM-VIRTUAL
PERSIST: START+SELECT
```

ScratchPad/RMS writes succeed in RAM.

`START+SELECT` is reserved for optional persistent-storage attachment. Missing physical media is not treated as an application-level `ENODEV` error.

Without successful persistent storage, RAM saves are volatile and do not survive power-off.

---

# Display handling

The runtime separates the game's logical canvas from the physical Nintendo DS display.

The tested FF4A configuration uses:

```text
Logical canvas : 240x240
Physical output: 256x192
Mode           : affine-stretch
```

The final screen transform is performed by Nintendo DS video hardware rather than by scaling every pixel in Java.

This keeps the original game coordinate system intact while avoiding expensive Java framebuffer scaling.

---

# Font and encoding

v59 supports CP932/SJIS-oriented Japanese game text.

The preparation pipeline can generate a full printable CP932 font set from a compatible TTF/TTC font.

The tested FF4A preparation currently uses:

```text
Encoding: SJIS / CP932
Glyphs  : 7485
```

The current font backend is still a compatibility implementation and may not perfectly match the original DoJa handset system font.

---

# Image compatibility

The runtime contains compatibility work for DoJa image formats and palette behavior, including:

- indexed GIF
- indexed BMP
- mutable `Palette`
- `PalettedImage`
- transparent palette indexes
- fuchsia/magenta compatibility color-key behavior
- image alpha
- clipped `drawRegion` behavior

A major FF4A transparency issue was fixed by preserving the original Pstros-style magenta color-key behavior.

---

# FF4A compatibility patches

For the exact supported FF4A build, the preparation tool applies signature-checked bytecode patches.

Current examples include:

- removal of periodic forced full GC
- removal of redundant phone attribute calls
- removal of an unused frame clock read
- removal of a redundant frame yield
- logical canvas decoupling
- removal of remaining explicit full-GC calls
- exception rethrow traces for field/load diagnostics

Unknown games are not blindly patched.

---

# Graphics3D status

DoJa `Graphics3D` is the main incomplete area in v59.

FF4A uses the 3D API for its world-map layer.

The expected composition is roughly:

```text
2D sky/cloud background
        +
Graphics3D world map
        +
2D player/overlay sprites
```

Earlier builds displayed only the sky and player because the 3D path was effectively a stub.

Later builds added a software renderer, but the FF4A world-map workload exposed serious performance/stall problems.

v59 therefore includes a compact diagnostic system rather than verbose per-object logging.

---

# v59 compact 3D diagnostics

v59 summarizes completed 3D frames with one line.

Example:

```text
3D F#12 r=57 q=228 t=0 fb=57 time=842ms OK
```

Fields:

```text
F#   frame number
r=   render calls/primitives processed
q=   quad count
t=   triangle count
fb=  framebuffer reads
time= elapsed 3D frame time
```

A slow completed frame is reported as:

```text
3D F#12 r=57 q=228 t=0 fb=57 time=6124ms SLOW
```

---

## Stall watchdog

If the same internal 3D stage makes no progress for at least about three seconds, v59 prints one warning:

```text
3D WATCH: HANG? R57 FB_READ age=3012ms
```

If the stage later resumes:

```text
3D WATCH: RESUME R57 FB_READ age=4270ms
```

Interpretation:

```text
HANG? -> RESUME
```

means the renderer was extremely slow, but it did make progress.

If `HANG?` remains on screen for a long time with no `RESUME` and no new frame summary, the stage is a likely real stall.

Large primitive batches update watchdog progress internally every 16 primitives without spamming the console.

---

# Why some games can load slowly but run smoothly

Slow loading does not necessarily mean the normal game loop is slow.

A typical resource-loading path is:

```text
read compressed pack from ScratchPad
        |
        v
inflate resource
        |
        v
allocate Java objects
        |
        v
decode image/map/audio
        |
        v
enter gameplay
```

Once those resources are in RAM, gameplay can be smooth.

This is why a game may take a long time between:

```text
logo -> title
title -> New Game
Continue -> field
map -> battle
```

while movement and combat are otherwise responsive.

---

# Diagnosing performance

## Slow before the first screen

Likely targets:

- class loading
- JAR decompression
- VM startup
- font initialization

The top-level STORED JAR optimization already helps this case.

## Slow only during scene/map transitions

Likely targets:

- compressed resource packs inside `.sp`
- Java/JAR inflater
- image decoding
- repeated resource-cache replacement
- explicit GC

Do not blindly repack the `.sp`; first understand its internal format.

## Slow during normal movement/gameplay

Investigate:

- rendering
- Graphics3D
- alpha blending
- per-frame allocations
- audio mixing
- VM interpreter hot paths
- frame timing

Archive conversion alone will not fix a true per-frame CPU bottleneck.

---

# Troubleshooting

## `Source version tag does not match prepare_doja.py`

The source tree contains files from different port versions.

Use a clean source package and do not mix generated/version files between releases.

---

## `Wrong generated version`

The prepared runtime metadata and Makefile version check do not match.

Run `build-doja.bat` from a clean matching source.

---

## `NoClassDefFoundError`

A DoJa API/class used by the game is not implemented or not included in `game.jar`.

The missing class is the next compatibility target.

---

## `IllegalArgumentException` from an image API

Check the lower-screen stack trace.

Several image compatibility issues have already been fixed, including indexed BMP, palette transparency, and clipped `drawRegion`.

---

## `JVM RETURNED: 127`

This normally indicates a fatal VM-level failure.

Capture the last lower-screen lines.

---

## `JVM RETURNED: 0` immediately after a game error

The game may have caught an exception and called `terminate()` normally.

Diagnostic bytecode patches may be needed to expose the hidden exception.

---

## World map is blank or renderer appears frozen

For v59, capture the latest:

```text
3D F#...
3D WATCH: HANG? ...
3D WATCH: RESUME ...
```

Do not rely on older verbose `G3D OBJ`, `Q`, `P0-P3`, or framebuffer spam; those logs were intentionally removed in v59.

---

# Current tested FF4A preparation

The current v59 preparation report for the supplied FF4A build confirms:

```text
App class       : FF4A
App param       : 131 0
Canvas          : logical 240x240
Output          : 256x192 affine-stretch
SP source       : 778304 bytes
SP payload      : 778240 bytes
SP layout       : preserved
Continue data   : preserved
Resource packs  : original DEFLATE
Inflater        : ARM-native fast path
game.jar        : all entries STORED
Encoding        : SJIS/CP932
Port            : DoJa v59 Empty
Output ROM      : final_fantasy_iv_the_after.nds
Verification    : PASS
```

The outer Nintendo LZ77 pack for this particular ScratchPad is larger than the original payload:

```text
778240 -> 827360 bytes
```

This is expected when the source data is already compressed internally. It does not mean the internal ScratchPad layout was changed.

---

# Known limitations

- Graphics3D world-map rendering is still under active diagnosis in v59.
- The current Japanese font is compatible but not identical to the original DoJa handset system font.
- Internal `.sp` compression cannot be safely optimized generically without understanding each game's offset tables.
- Virtual RAM save is volatile unless persistent storage is successfully attached.
- Not every DoJa API is implemented.
- Game-specific fixes may still be required for uncommon image, audio, network, or 3D behavior.

---

# Recommended workflow for another game

```text
Original JAR + JAM + SP
        |
        v
build-doja.bat
        |
        v
Top-level JAR -> STORED
        |
        v
Preserve game-visible ScratchPad
        |
        v
Generate encoding/font/runtime metadata
        |
        v
Verify
        |
        v
Build NDS ROM
        |
        v
Test in melonDS and hardware
```

If the game works but loads slowly, investigate the ScratchPad resource layout before creating a game-specific optimization.

If normal gameplay is slow or rendering is missing, profile the rendering/API path instead.

---

## Version

```text
DoJa v59 Empty
```

v59 is currently best treated as a **compatibility + Graphics3D diagnostic build**.
