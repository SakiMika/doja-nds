# Changelog

All versions below refer to the DoJa/KVM Nintendo DS port development line.

---

## v59 — Compact Graphics3D Diagnostic

### Added

- Compact one-line 3D frame summaries.
- 3D stage watchdog with a one-shot possible-stall warning:
  ```text
  3D WATCH: HANG? ...
  ```
- Resume reporting when a suspected stall later makes progress:
  ```text
  3D WATCH: RESUME ...
  ```
- Internal watchdog progress updates every 16 primitives for large batches without console spam.

### Changed

- Removed the very verbose v58 Graphics3D trace output.
- Successful texture decode, camera-step, object, primitive, projection, quad, and framebuffer chatter is no longer printed repeatedly.
- A completed slow 3D frame is marked `SLOW`.
- A normal completed 3D frame is marked `OK`.

### Current diagnostic target

FF4A world-map `Graphics3D` rendering still appears to stall or become extremely slow. v59 is intended to distinguish true stalls from very slow progress and to identify the last active internal stage.

### Verified

- FF4A preparation: PASS.
- Original game-visible ScratchPad layout preserved.
- Top-level `game.jar` STORED.
- Output ROM name remains game-name only.

---

## v58 — Detailed Graphics3D Trace

### Added

- Detailed instrumentation around:
  - texture loading
  - camera setup
  - `renderObject3D`
  - primitive entry
  - framebuffer read
  - projection
  - quad batches
  - raster entry/exit
  - 3D flush

### Purpose

v58 was created to determine whether the FF4A world-map failure happened during class loading, texture decoding, projection, framebuffer access, or rasterization.

### Result

The trace produced too much repeated output during the world-map workload, motivating the compact v59 logger.

---

## v57 — Fast World-Map Quad Path

### Added

- Fast tiled-quad path for large `QUADS` batches.
- Fixed-point/integer raster work for large world-map batches.
- Screen clipping before rasterization.
- Primitive/bounding-area guards to prevent malformed projection from causing unbounded loops.

### Changed

- Large quad batches no longer use full per-pixel floating-point barycentric work where the fast path applies.
- Smaller 3D primitives retain the more general renderer.

### Reason

The FF4A world map creates a large tiled-quad workload. The previous Java/KVM software rasterizer could appear frozen because of excessive floating-point raster work.

---

## v56 — Initial FF4A Graphics3D World-Map Renderer

### Added

- Software rendering support for DoJa `Graphics3D` textured primitives.
- Textured quads.
- Textured triangles.
- Texture tiling.
- Perspective-oriented texture mapping.
- Normal, alpha, and additive blend paths.
- Fog support.
- 3D composition with the existing 2D framebuffer.

### Fixed

- `FastMath` trigonometric behavior adjusted for DoJa-compatible angle usage.
- `Transform.rotate()` and `Transform.lookAt()` compatibility work.
- Initial camera/projection handling for FF4A world-map rendering.

### Known issue

The initial software renderer was too expensive for the full FF4A world-map workload and could appear to hang.

---

## v55 — Pstros Transparency Compatibility Backport

### Fixed

- Magenta/fuchsia (`RGB 255,0,255`) compatibility color-key behavior.
- Transparent native blits skip magenta pixels.
- Alpha/fade paths preserve the compatibility color key.
- Palette/PNG compatibility paths correctly treat the Pstros-style magenta key as transparent.

### Result

FF4A scenes that previously displayed a bright magenta background correctly exposed the intended underlying background layer.

---

## v54 — Indexed BMP / PalettedImage Transparency

### Added

- Indexed BMP support for `PalettedImage`.
- 1-bit, 4-bit, and 8-bit indexed BMP decoding.
- Windows and OS/2 palette BMP handling.
- Bottom-up/top-down BMP support.
- Palette-index preservation.

### Fixed

- BMP transparency metadata is applied to `PalettedImage`.
- Conservative magenta corner-based transparent-index detection for compatible indexed BMP assets.

### Build fix

- Synchronized v54 version tags across:
  - `VERSION`
  - `prepare_doja.py`
  - verifier
  - source version headers
  - Makefile checks
- Fixed `build-doja.bat` optional-font input handling.

---

## v53 — Runtime Stability Fixes

### Fixed

- DoJa-style `drawRegion` source clipping.
  - Source rectangles that slightly cross bitmap boundaries no longer automatically cause a MIDP `IllegalArgumentException`.
- KVM unresolved-field handling during GC/stack-map work.
  - Prevented the fatal:
    ```text
    FATAL VM: Expected a resolved field
    ```
  - Added safer type inference for unresolved field references.
- Soft-key/menu carry-over.
  - SELECT/SOFT-style polling behavior changed to avoid a Back key being carried into the title menu and immediately triggering another action.

### Retained

- Original ScratchPad layout policy.
- Virtual RAM Save.
- Existing FF4A bytecode/performance patches.

---

## v52 — Paletted BMP Compatibility

### Fixed

- FF4A Continue/world-map loading failed with:
  ```text
  java.lang.IllegalArgumentException:
  Unsupported Paletted Image
  ```
- Added indexed BMP decoding to the DoJa `PalettedImage` path.

### Result

FF4A could proceed past the previous unsupported-BMP failure and expose the next rendering compatibility issues.

---

## v51 — FF4A Outer Exception Trace

### Changed

For the exact supported FF4A build, the outer `FF4A.start()` exception handler was changed from:

```text
catch(Exception)
    -> discard exception
    -> terminate()
    -> return normally
```

to a diagnostic rethrow.

### Reason

v50 could expose an inner exception, but the outer application handler still swallowed it and caused:

```text
JVM RETURNED: 0
```

v51 allowed the real exception to reach the runtime stack-trace path.

---

## v50 — Original ScratchPad Compatibility / Continue Diagnostics

### Major change

Stopped aggressively rebuilding FF4A's internal ScratchPad resource layout.

For the tested FF4A build:

```text
Host SP       : 778304 bytes
Wrapper       : 64 bytes
Game SP       : 778240 bytes
Continue data : first 25600 bytes preserved
```

The game-visible ScratchPad is preserved byte-for-byte.

### Changed

- Internal FF4A resource archives remain in their original DEFLATE layout.
- ARM-native inflater path used for performance without moving resource offsets.
- Top-level `game.jar` still rebuilt as STORED.
- Continued use of Virtual RAM Save.

### Added

- Exception-rethrow diagnostics for FF4A load/Continue error handlers.
- Build-version consistency fixes.
- Clean game-name-only ROM output naming.

### Reason

Earlier aggressive ScratchPad repacking could alter private resource offsets and interfere with bundled Continue state and game loading behavior.

---

# Current architecture summary

As of v59:

```text
Top-level game.jar
    -> STORED

Game-visible ScratchPad
    -> original internal layout preserved
    -> optional outer Nintendo LZ77 ROM package

Save
    -> RAM-VIRTUAL from boot
    -> optional persistent media attachment

2D rendering
    -> substantially functional

Indexed GIF/BMP
    -> supported

Magenta transparency compatibility
    -> supported

FF4A world-map Graphics3D
    -> implemented experimentally
    -> currently under v59 stall/performance diagnosis
```

---

# Important compatibility policy

The project currently favors **preserving game binary layout** over blindly applying maximum compression/loading optimization.

In particular:

- Do not assume every `.sp` is only save data.
- Do not blindly convert nested ScratchPad archives to STORED.
- Do not permanently lock the runtime to one game.
- Apply game-specific bytecode changes only when exact signatures match.
- Use diagnostics to identify API/runtime failures before patching game state.

---

## Current version

```text
DoJa v59 Empty
```
