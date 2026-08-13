# DoJa v48 Empty — Virtual RAM Save Update

This update changes the save architecture without changing the public v48 Empty name.

## Problem fixed

Previous v48 Empty builds intentionally refused to attach physical media during boot.
That avoided FAT/DLDI hangs, but the runtime exposed the state as:

- `MEDIA: NOT ATTACHED`
- `ERRNO: 19` (`ENODEV`)
- `LAST: RAM BUFFERED`

Some DoJa games perform a save/RMS capability check during startup. They interpreted
the missing device as a real storage error and displayed an error screen even though
the ScratchPad RAM overlay itself was functioning.

## New architecture

The runtime now exposes `RAM-VIRTUAL` as a real save device from power-on.

- ScratchPad writes succeed in RAM.
- ScratchPad flush returns success in RAM.
- RMS `File.exists/size/load/save` works against an in-memory virtual file.
- No FAT, DLDI, SD, or filesystem probe occurs before the JVM starts.
- `START+SELECT` is optional and only tries to attach persistent FAT/SD storage.
- A failed physical attach leaves the RAM save device valid.
- `ENODEV` is no longer exposed merely because physical media is absent.

When physical storage is attached successfully, subsequent persistent writes use it.
A complete dirty RAM RMS snapshot is also mirrored to the attached storage when safe.

## Expected lower-screen status

```text
DoJa v48 Empty
MODE: VIRTUAL RAM SAVE
SAVE: READY
MEDIA: RAM-VIRTUAL
PERSIST: START+SELECT
```

After a ScratchPad write without physical media:

```text
LAST: RAM SAVED (N)
```

This is a successful volatile save. It survives for the current run. Use
`START+SELECT` after the game is running if the loader/device supports persistent
FAT/SD saves.
