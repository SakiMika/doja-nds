# DoJa NDS Port v36 — font CP932 cũ, sửa chữ Latin và ép toàn màn hình

Bản v36 giữ font bitmap CP932 12×12 trước v34. `dsr_fnt.NFTR` không còn được đọc hoặc trộn vào ROM.

## Font

- Giữ trọn bộ ký tự CP932/SJIS: khoảng 7.485 glyph.
- Ký tự Nhật vẫn dùng font Windows được chọn khi chuẩn bị ROM.
- Chữ Latin/ASCII được raster trực tiếp vào ô nửa chiều rộng 6×12.
- Runtime không còn lấy cách một cột ảnh, tránh mất nét dọc ở các chữ như `M`, `N`, `H`, `E`, `F`, `R`.
- Giữ sửa lỗi bỏ qua byte NUL ở cuối chuỗi.

## Hiển thị

Game vẫn chạy với hệ tọa độ gốc 240×240 để không làm lệch map, va chạm và giao diện. Khung hình hoàn chỉnh được scale nearest-neighbor sang toàn bộ màn hình NDS 256×192:

```text
240×240 logic -> 256×192 output
X: 15/16 source pixel cho mỗi pixel màn hình
Y: 5/4 source pixel cho mỗi pixel màn hình
```

Không còn cắt 24 pixel phía trên và 24 pixel phía dưới. Hình sẽ bị kéo ngang nhẹ vì đây là chế độ force full-screen theo đúng 256×192.

## Save

Giữ nguyên phương thức `.sav` của v33 đang hoạt động:

```text
corpse_party_newchapter_1_doja_v36.nds
corpse_party_newchapter_1_doja_v36.sav
```

Khi launcher không truyền đường dẫn ROM, dùng `fat:/CPN1.SAV`. Ba slot, write-through, CRC và trạng thái save màn hình dưới được giữ nguyên.

## Sửa lỗi build v35

V35 gọi macro `KNI_EndHandles()` ngay trong nhánh scale. Macro này đóng scope ở thời điểm biên dịch, nên phần blit phía sau mất toàn bộ biến cục bộ. V36 chỉ đóng handles tại nhãn `blit_done` ở cuối hàm.

## Build

Giải nén vào thư mục mới, chạy `build_doja.bat`, chọn JAR/JAM/SP và font Nhật TTF/TTC. Không cần đặt file NFTR cạnh source.
