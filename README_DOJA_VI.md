# DoJa NDS Port v25

Nhánh DoJa độc lập với PSTros. Bản này giữ font Nhật CP932/SJIS tích hợp sẵn, ScratchPad đọc trực tiếp từ ROM và icon mặc định trong `assets/default_standalone_icon.bmp`.

## Save v25

Corpse Party lưu ba slot trực tiếp trong ScratchPad. Bản v25 nhận diện đúng vùng ghi:

- Slot 1: offset 5, dài 1563 byte.
- Slot 2: offset 1568, dài 1563 byte.
- Slot 3: offset 3131, dài 1563 byte.

Save được lưu ở thư mục gốc của thiết bị FAT bằng tên 8.3 lấy từ mã ROM. Ví dụ mã ROM `CPN1` tạo:

```text
fat:/CPN1.DJS
```

File tạm cũng dùng tên 8.3 `CPN1.TMP`, tránh lỗi của flashcart/DLDI cũ với tên `CPN1.DJS.tmp`. Bản v25 thử lại mount DLDI ngay lúc game ghi save, ghi file tạm rồi đọc kiểm tra CRC; nếu rename/copy không hoạt động, nó chuyển sang ghi trực tiếp và kiểm tra lại file cuối.

## Trạng thái màn hình dưới

```text
SAVE: READY
LAST: SAVED SLOT 3
FILE: CPN1.DJS
```

`SAVED SLOT n` chỉ xuất hiện sau khi file cuối đã được đọc lại và xác minh. Các trạng thái khác:

- `SAVE: RAM ONLY`: FAT/DLDI chưa dùng được; thay đổi chưa tồn tại sau khi tắt máy.
- `LAST: SAVE LOADED`: đã nạp file `.DJS` lúc khởi động.
- `LAST: SAVING SLOT n`: đang ghi.
- `LAST: SAVE FAILED (-n)`: lỗi ở một bước ghi hoặc xác minh; mã lỗi được giữ trên màn hình.

## Build

Giải nén source vào thư mục mới rồi chạy:

```bat
build_doja.bat
```

Build tự tạo `last_prepare.log`, `last_build.log` và ROM có hậu tố `_doja_v25.nds`.
