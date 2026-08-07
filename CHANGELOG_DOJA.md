# DoJa v48 Empty

- Tách toàn bộ FF4A khỏi source phát hành.
- Thêm `build-doja.bat` để chọn JAR/JAM/SP và build trong một lần.
- Tự chuyển mọi entry của `game.jar` sang STORED.
- Tự nén ScratchPad bằng Nintendo LZ77 type 0x10 (`D7SP` wrapper + CRC32).
- Giữ patch FF4A/Corpse Party theo chữ ký chính xác, không khóa game.
- Không ép DSi mode đối với game nhỏ; DSi vẫn dùng heap 8 MiB.
