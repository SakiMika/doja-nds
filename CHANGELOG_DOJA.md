# DoJa NDS Port – Changelog

## v36 — Sửa lỗi biên dịch bộ scale 256×192

- Sửa lỗi `KNI_EndHandles()` bị gọi trong nhánh scale, làm đóng scope macro giữa hàm và khiến `alpha`, `clipX`, `dstX`, `srcW` cùng nhiều biến khác bị báo chưa khai báo.
- Nhánh scale giờ nhảy tới một epilogue chung duy nhất bằng `goto blit_done`, sau đó mới đóng KNI handles và trả về.
- Thêm kiểm tra tự động để không tái xuất hiện lỗi đóng handle scope trong nhánh.
- Giữ nguyên font CP932 12×12, sửa nét Latin, scale 240×240 → 256×192 và save `.sav` đang hoạt động.

## v35 — Original CP932 Font + Latin Stroke Fix + Forced 256×192

- Loại bỏ hoàn toàn font lai NFTR của v34.
- Khôi phục font CP932 12×12 đầy đủ như v33.
- Raster chữ Latin vào ô 6×12 riêng, không còn lấy cách một cột gây mất nét.
- Giữ hệ tọa độ game 240×240, scale khung hình cuối sang toàn màn hình NDS 256×192.
- Đặt khung hình tại X=0, Y=0; không còn crop bằng offset Y=-24.
- Giữ nguyên save `.sav` đang hoạt động, ba slot, write-through, CRC, icon mặc định, input, ScratchPad zero-copy và heap 2432 KiB.
