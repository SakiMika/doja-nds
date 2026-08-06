# DoJa NDS Port v42 — FF4A performance build

v42 keeps native 240×240 rendering (X=8, Y=-24) and multi-game preparation,
but adds an exact-signature optimization path for Final Fantasy IV The After.

## FF4A optimizations

- Directly presents the completed DoJa framebuffer; removes the extra repaint/copy.
- Global image alpha is blended in native ARM code; fades no longer rebuild ARGB images.
- Caches complete Japanese labels, reducing per-glyph Java scaling and drawRGB calls.
- Removes FF4A's forced full GC every 75 frames and redundant phone attribute call.
- Compiles the KVM interpreter/cache/video hot objects as ARM `-O3`.
- Opaque image rows use `memcpy`.

The bytecode patch only runs when `AppClass=FF4A` and both exact `m.class`
signatures match. Other games remain unchanged.

Run `build_doja.bat`, select JAR/JAM/SP, then run `build.bat`.
Use melonDS DSi mode for FF4A. The build still does not stretch 240×240 to 256×192.
