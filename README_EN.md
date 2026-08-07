# DoJa v48 Empty — Nintendo DS Build System

DoJa v48 Empty is a generic DoJa/KVM-to-Nintendo-DS build tree.

It is intentionally shipped without a pre-installed game. The build pipeline reads a game's JAR, JAM, and ScratchPad (`.sp`), prepares them for the Nintendo DS runtime, verifies the generated data, and then builds a standalone `.nds` ROM.

The boot screen identifies this runtime as:

```text
DoJa v48 Empty
```

---

## 1. What this build does

Run `build-doja.bat` and provide:

- the game `.jar`
- the game `.jam`
- the game ScratchPad `.sp`
- an optional 4-character ROM/save code
- an optional ROM name
- an optional Japanese TTF/TTC font

The preparation pipeline then performs the following steps:

1. Reads the JAM file and extracts the game configuration, including `AppClass`, `AppParam`, `SPsize`, and supported canvas metadata.
2. Rebuilds the top-level `game.jar` so every ZIP/JAR entry uses **STORED** mode instead of DEFLATE.
3. Applies a bytecode patch only when the input game matches a known, supported signature. Unknown games are not blindly patched.
4. For supported Final Fantasy IV: The After Years builds, converts the known resource archives inside the ScratchPad to **STORED** and rewrites their resource offset/length table.
5. Compresses the complete prepared ScratchPad with **Nintendo LZ77 type 0x10** for embedding in the NDS ROM.
6. Generates the prepared JAM, ROM metadata, save name, font data, and runtime headers.
7. Verifies JAR structure, ScratchPad size, LZ77 decompression, and CRC consistency.
8. Calls the NDS compiler and creates the standalone `.nds` file.

Important: **STORED** and **LZ77** serve different purposes.

- `STORED` means entries inside a ZIP/JAR are not DEFLATE-compressed. This reduces CPU time while the KVM/game is loading them.
- LZ77 is the outer compression used to fit the prepared ScratchPad efficiently inside the NDS ROM. It is decompressed once at boot into RAM.

---

## 2. Requirements

### Windows

The included batch files expect Windows.

### Python 3

Install Python 3 and make sure either `py.exe` or `python.exe` is available in `PATH`.

Pillow is required for some image/font preparation steps:

```bat
py -3 -m pip install pillow
```

### devkitPro / devkitARM

Install a Nintendo DS development environment containing at least:

- devkitARM
- libnds
- Calico / DS ARM7 support used by this project
- `make`
- `ndstool`

The scripts automatically check common devkitPro locations such as:

```text
D:\devkitPro
C:\devkitPro
```

The `DEVKITPRO` environment variable is also supported.

### DSi mode recommended

Large DoJa games should be tested in DSi mode when possible.

The v48 runtime uses a larger Java heap on DSi. Small games may still work in standard DS/NTR mode, but large games can run out of memory.

---

## 3. Quick start

Do not run `build.bat` first on a clean v48 Empty source tree.

Run:

```bat
build-doja.bat
```

Then enter the requested files.

Example:

```text
1. JAR file: D:\games\MyGame.jar
2. JAM file: D:\games\MyGame.jam
3. SP file:  D:\games\MyGame.sp
4. 4-character save/ROM code [D0JA]: FF4A
5. Optional ROM name [use JAR name]:
6. Optional Japanese TTF/TTC font [auto-detect]:
```

Paths can also be pasted or dragged into the Command Prompt window.

The script removes generated data from the previous prepared game before preparing the new one. This prevents metadata, JARs, ScratchPads, or save identifiers from being accidentally reused across different games.

After preparation succeeds, it automatically calls the NDS build step.

---

## 4. Generated files

During preparation, the important generated files include:

```text
embedded\game.jar
embedded\doja_scratchpad.lz7b
build_doja\prepared_game.jam
standalone_game.mk
include\standalone_game.h
```

The final ROM name is generated from the selected game metadata and normally ends in:

```text
_doja_v48.nds
```

Do not manually mix generated files from different games.

For example, do not combine:

- `game.jar` from game A
- `doja_scratchpad.lz7b` from game B
- `standalone_game.h` from game C

Always run `build-doja.bat` again when changing games.

---

# 5. Why some DoJa games load very slowly

A game can have very slow loading screens while still running smoothly after the scene has loaded.

This is especially important because **slow loading does not automatically mean the NDS renderer is too slow**.

For Final Fantasy IV: The After Years, the major slowdown was found in resource loading rather than normal gameplay.

## 5.1 Top-level JAR class loading

The normal game JAR contains Java bytecode and DoJa classes.

If its entries are DEFLATE-compressed, the KVM must repeatedly:

1. find a ZIP entry,
2. read compressed data,
3. inflate it,
4. allocate the class data,
5. parse the class,
6. resolve methods and fields.

On an interpreted KVM running on ARM9, this is much more expensive than on a modern JVM.

For this reason v48 Empty automatically rebuilds the top-level `game.jar` using **STORED** entries.

This improves class loading for every game.

However, the top-level JAR is not always the main bottleneck.

---

## 5.2 ScratchPad resource archives can be much more expensive

Many DoJa games use the ScratchPad as more than a save area.

A ScratchPad can contain large runtime resources such as:

- maps
- sprites
- field data
- battle data
- images
- sound data
- additional JAR/ZIP-like resource packs

A game may read a resource pack from the `.sp`, construct a `JarInflater`, inflate it, create many Java arrays/objects, and then cache the result.

If those inner packs use DEFLATE, resource loading may become extremely slow because decompression is being performed through Java/KVM code.

This explains the typical pattern:

```text
logo
  -> very long wait
title screen
  -> New Game
  -> another very long wait
actual gameplay
  -> smooth
```

Once the required assets are already in RAM, the expensive decompression path is no longer running every frame, so gameplay can remain smooth.

---

## 5.3 Why Final Fantasy IV: The After Years was especially slow

In the tested FF4A build, the ScratchPad contains multiple compressed resource packs.

The original runtime repeatedly had to do work similar to:

```text
read resource pack from ScratchPad
        |
        v
create Java JarInflater
        |
        v
DEFLATE/Huffman decompression
        |
        v
allocate unpacked resources
        |
        v
create/cache game objects
```

This was much more expensive than the normal rendering path.

The game also contained forced garbage-collection calls and the development runtime previously printed a very large amount of class-loader/debug text. Both increased loading time further.

The result was approximately minute-long waits around major resource transitions even though the game itself was smooth after loading.

---

# 6. How v48 optimizes loading

## 6.1 Convert `game.jar` to STORED

This is the generic optimization applied to all prepared games.

Before:

```text
game.jar entry
    -> DEFLATE
    -> KVM decompression
    -> class parser
```

After:

```text
game.jar entry
    -> STORED
    -> direct read/copy
    -> class parser
```

This reduces class-loader CPU cost.

---

## 6.2 Convert known ScratchPad resource packs to STORED

This is the most important optimization for games whose loading bottleneck is inside the `.sp`.

For the supported FF4A build, v48 can:

1. identify the known resource archives,
2. extract each archive,
3. rebuild it using STORED entries,
4. rewrite the ScratchPad resource offsets and lengths,
5. verify that every resource still matches the original unpacked data.

The important part is the offset rewrite.

A generic tool **cannot safely change an arbitrary compressed block inside an unknown `.sp`** because changing archive size moves all following data. If the game stores offsets in a private table, those offsets must also be updated.

Therefore:

- top-level `game.jar` -> STORED is generic,
- entire prepared `.sp` -> LZ77 is generic,
- converting unknown nested resource packs inside `.sp` -> STORED is **game-format dependent**.

v48 only performs such internal rewriting when the format/signature is known.

---

## 6.3 Outer ScratchPad LZ77

After the runtime resource layout has been prepared, the whole ScratchPad is compressed with Nintendo LZ77 type `0x10`.

This does **not** bring back the original in-game DEFLATE bottleneck.

The sequence is:

```text
NDS boot
    -> decompress one LZ77 ScratchPad image into RAM
    -> verify it
    -> start JVM
    -> game reads the already-prepared RAM ScratchPad
```

The LZ77 cost happens once during boot.

The game does not need to repeatedly run Java DEFLATE on the outer container during every scene transition.

---

## 6.4 Remove unnecessary debug output

Development logging can be surprisingly expensive on the Nintendo DS.

A loader that prints information for every:

- class
- method
- field
- exception handler
- resource entry

can generate thousands of console writes.

The optimized runtime removes hot-path debug output from release operation while still retaining serious boot/error reporting.

---

## 6.5 Avoid unnecessary forced garbage collection

Explicit `System.gc()` calls can cause noticeable pauses in a small interpreted VM.

For supported game-specific patches, unnecessary forced GC calls can be removed when they are known not to be required for correctness.

This is not applied blindly to unknown games.

---

# 7. How to diagnose another slow DoJa game

Use the loading pattern to identify the likely bottleneck.

## Case A — Slow before the first screen appears

Likely causes:

- class loading
- top-level JAR DEFLATE
- VM initialization
- font initialization
- large startup allocations

First optimization:

```text
rebuild game.jar as STORED
```

v48 Empty already does this automatically.

## Case B — Title appears, but New Game or map changes take a very long time

Likely causes:

- resources stored in `.sp`
- nested ZIP/JAR packs
- Java `JarInflater`
- repeated DEFLATE
- repeated GC
- resource-pack cache replacement

This usually needs inspection of the ScratchPad format.

## Case C — Loading is fast, but movement/gameplay is slow

Then the problem is probably not resource compression.

Investigate:

- rendering
- alpha blending
- Java game logic
- per-frame allocations
- audio mixing
- frame limiter/timing
- VM interpreter hot paths

Converting archives to STORED will not fix a true per-frame CPU bottleneck.

---

# 8. Optimizing a new game

For a new game, use this order.

### Stage 1 — Build normally with v48 Empty

Run:

```bat
build-doja.bat
```

The top-level JAR is already converted to STORED.

Test the ROM.

### Stage 2 — Observe where the delay occurs

Measure separately:

- boot -> publisher/logo
- logo -> title
- title -> New Game
- map -> map
- battle entry
- battle exit

If only scene transitions are extremely slow while gameplay is smooth, inspect the ScratchPad.

### Stage 3 — Inspect the `.sp`

Look for:

- ZIP signatures
- JAR signatures
- repeated DEFLATE streams
- resource tables
- offset/length tables
- pack IDs

Do not simply replace a compressed archive with a larger STORED archive without updating its metadata.

### Stage 4 — Create a game-specific ScratchPad converter

The safe process is:

```text
parse original table
    -> extract pack
    -> rebuild pack STORED
    -> rebuild ScratchPad
    -> calculate new offsets
    -> write new lengths
    -> verify every resource
```

### Stage 5 — Only then consider deeper VM patches

Examples:

- native inflater
- class-entry index
- resource caching
- GC reduction
- native CRC
- native copy/blit functions

These are secondary if the main delay is repeated Java DEFLATE.

---

# 9. Screen handling

v48 Empty is designed so the runtime does not need to permanently lock itself to one game.

Game-specific display information is generated from the preparation pipeline.

For the FF4A work that led to v48:

- the logical source canvas remains compatible with the game's original coordinate system,
- the NDS hardware performs the final display transform,
- expensive Java per-pixel resizing is avoided.

Do not assume every DoJa game uses the same logical canvas size. A new game's JAM and bytecode may need separate analysis.

---

# 10. Troubleshooting

## `Python 3 was not found`

Install Python 3 and ensure either:

```text
py.exe
```

or:

```text
python.exe
```

is available in `PATH`.

---

## Pillow is missing

Run:

```bat
py -3 -m pip install pillow
```

---

## `devkitPro MSYS2 make.exe was not found`

Set:

```text
DEVKITPRO
```

or install devkitPro to one of the common locations checked by the script.

---

## Preparation fails

Send/check:

```text
last_prepare.log
```

Do not continue to `build.bat` with partially generated files.

---

## NDS build fails

Check:

```text
last_build.log
```

Compiler warnings are not necessarily fatal. The final error near the bottom of the log is the important part.

---

## ROM boots but freezes before JVM start

This usually indicates a runtime initialization problem rather than game bytecode.

Check the last boot-stage text shown on the lower screen.

---

## ROM reaches JVM but reports `NoClassDefFoundError`

The game is calling a DoJa class/API that is not yet implemented by the runtime.

The missing class shown in the exception is the next compatibility target.

---

## The game is smooth but loading still takes a very long time

The most likely next target is the ScratchPad resource path.

The top-level JAR may already be optimized while inner resource archives remain DEFLATE-compressed.

---

# 11. Important limitations

v48 Empty is a generic build base, not a promise that every DoJa game will automatically become fully optimized.

Generic preparation can safely do:

```text
top-level game.jar -> STORED
ScratchPad -> LZ77 outer ROM container
JAM parsing
metadata generation
verification
build
```

Game-specific knowledge may still be required for:

```text
nested archives inside ScratchPad -> STORED
private offset/length tables
bytecode patches
custom canvas behavior
unsupported DoJa APIs
game-specific save layouts
```

The build system intentionally avoids blindly modifying unknown binary structures.

---

# 12. Recommended workflow

For each new game:

```text
original JAR + JAM + SP
          |
          v
build-doja.bat
          |
          v
generic STORED game.jar
          |
          v
LZ77 ScratchPad container
          |
          v
verification
          |
          v
NDS build
          |
          v
test in melonDS / hardware
          |
          +--> fast enough -> done
          |
          +--> slow loading only
                 |
                 v
              analyze .sp
                 |
                 v
        add game-specific STORED pack conversion
```

This keeps the runtime multi-game while allowing aggressive optimization only where the binary format is understood.

---

## v48 Empty summary

- No game is permanently embedded in the clean source.
- Changing games does not require hard-locking the runtime to one title.
- Top-level JAR entries are automatically rebuilt as STORED.
- The prepared ScratchPad is automatically packaged with Nintendo LZ77.
- Supported game-specific resource packs can also be converted to STORED.
- Large games should use DSi mode.
- If gameplay is smooth but scene loading is extremely slow, investigate the `.sp` before blaming rendering performance.
