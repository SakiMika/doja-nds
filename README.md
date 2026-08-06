# DoJa NDS Port v41 — giảm chớp hình và tăng tốc tải

v41 tiếp tục giữ hai nguyên tắc:

1. **Không ép fit** khung DoJa 240×240 sang 256×192.
2. **Không khóa theo một game**; khi đổi JAR/JAM/SP, lớp chính, ScratchPad và tên save đều được sinh lại.

## Lỗi đã quan sát ở v40

FF4A đã vào được màn hình tiêu đề, nhưng:

- tải tài nguyên lâu;
- màn hình dưới liên tục cuộn log `DOJA SENT`, `Thread.start...`, tìm class/JAR;
- khung hình có thể chớp vì `flushBuffer()` đưa từng trạng thái trung gian lên màn hình dù game vẫn đang ở trong `Graphics.lock()`.

## Thay đổi v41

- `Graphics.flushBuffer()` chỉ đánh dấu frame đang chờ khi còn nằm trong `lock()`.
- Chỉ trình bày **một frame hoàn chỉnh** khi `unlock()` ngoài cùng kết thúc.
- Loại bỏ log nóng khỏi đường input, tạo thread, tìm class và đọc JAR.
- Tắt các log thành công khi boot, nạp font và CP932; lỗi nghiêm trọng vẫn được in.
- Tái sử dụng cây Huffman cố định của DEFLATE thay vì dựng lại ở mỗi block.
- Sao chép chuỗi LZ bằng `System.arraycopy()` theo khối thay vì từng byte.
- Tăng bộ đệm đọc JAR từ 2 KiB lên 8 KiB.
- Giữ API `Palette`, `PalettedImage`, `graphics3d`, SJIS/CP932 và RAM-first save của v40.

## Hiển thị nguyên tỉ lệ

Game vẫn chạy trong hệ tọa độ 240×240, mặc định:

```text
X = 8
Y = -24
```

NDS hiển thị vùng giữa 240×192 bằng pixel nguyên bản; không kéo ngang và không nén dọc.

## Chuẩn bị game khác

Chạy `build_doja.bat`, chọn JAR, JAM và SP, sau đó nhập mã lưu bốn ký tự. Công cụ xóa metadata game cũ trước khi tạo bộ mới.

## FF4A prepared

```text
AppClass: FF4A
AppParam: 131 0
ScratchPad: 778240 bytes
Viewport: 240x240 at X=8, Y=-24
Expected ROM: final_fantasy_iv_the_after_doja_v41.nds
```

Nên thử bằng melonDS ở DSi mode. v41 chưa được boot trực tiếp trong môi trường đóng gói này vì không có devkitARM, ndstool và melonDS.
