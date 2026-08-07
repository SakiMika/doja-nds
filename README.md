# DoJa v48 Empty

Đây là source trống, không khóa sẵn một game.

## Cách dùng

Chạy `build-doja.bat`, sau đó nhập lần lượt đường dẫn **JAR**, **JAM** và **SP**. Script tự động:

1. Đọc `AppClass`, `AppParam`, `SPsize` và cấu hình canvas từ JAM.
2. Chỉ áp dụng patch bytecode khi đúng chữ ký game được hỗ trợ; game khác không bị vá nhầm.
3. Tạo `game.jar` mới với toàn bộ entry ở chế độ **STORED** để nạp class nhanh.
4. Với FF4A đúng phiên bản, chuyển 14 resource pack bên trong ScratchPad sang **STORED** và cập nhật lại 65 record offset/length.
5. Nén toàn bộ ScratchPad bằng **Nintendo LZ77 type 0x10** thành `embedded/doja_scratchpad.lz7b`.
6. Tạo `build_doja/prepared_game.jam`, metadata ROM, tên save và font CP932.
7. Xác minh CRC rồi tự gọi `build.bat`.

Màn hình boot ghi `DoJa v48 Empty`. DSi mode dùng heap lớn; DS mode vẫn được phép với game nhỏ.

Không trộn `game.jar`, `.lz7b`, `standalone_game.h` hoặc marker từ những lần chuẩn bị khác nhau.
