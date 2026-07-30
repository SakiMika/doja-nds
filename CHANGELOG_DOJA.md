# Changelog

## v25

- Sửa save đúng ba slot ScratchPad của Corpse Party; slot 3 bắt đầu tại offset 3131 và dài 1563 byte.
- Dùng file save 8.3 theo mã ROM, ví dụ `CPN1.DJS`.
- Dùng file tạm 8.3 `CPN1.TMP`, không còn tên không tương thích `CPN1.DJS.tmp`.
- Thử mount lại DLDI ở lần ghi đầu tiên nếu FAT chưa sẵn sàng lúc boot.
- Không xóa overlay RAM khi mount muộn.
- Ghi write-through và chỉ báo thành công sau khi đọc lại, kiểm tra header và CRC file cuối.
- Có đường ghi trực tiếp dự phòng khi rename/copy file tạm không được DLDI hỗ trợ.
- Màn hình dưới chỉ giữ trạng thái save; bỏ log quét phím, class loader và audio thông thường.
- Giữ font Nhật CP932/SJIS, input, ScratchPad zero-copy, heap 2432 KiB và icon mặc định.
