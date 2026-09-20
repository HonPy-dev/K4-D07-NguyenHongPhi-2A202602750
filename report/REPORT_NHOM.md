# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** [Tên nhóm]
**Thành viên:** [Họ tên từng thành viên]
**Ngày:** [Ngày nộp]

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Dịch vụ và quy định thư viện đại học — UTSC Library (University of Toronto Scarborough)

**Tại sao nhóm chọn chủ đề này?**
> Dịch vụ và quy định thư viện nằm đúng chủ đề bắt buộc của L3A (dịch vụ/quy định đại học), và UTSC Library công khai đầy đủ chính sách trên một site chính thức duy nhất, cấu trúc trang ổn định, robots.txt cho phép truy cập. Bộ tài liệu có cả quy định dạng số (hạn mượn, phí trễ, tiền phạt) lẫn dịch vụ mô tả, và chứa thông tin phân biệt theo đối tượng (student / faculty / all) — thuận lợi để chứng minh `metadata_filter`. Corpus là 8 tài liệu, nằm gọn trong khung 5–10 của lab.

### Danh sách tài liệu (Data Inventory)

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | UTSC Library borrowing policy | https://utsc.library.utoronto.ca/borrowing | 2026-09-19 / 2025-12-17 | 8 748 | audience=student, department=library, category=library-services, language=en |
| 2 | Technology loans | https://utsc.library.utoronto.ca/technology-loans | 2026-09-19 / not-stated | 18 157 | audience=student, department=library, category=library-services, language=en |
| 3 | Course reserves and short-term loans | https://utsc.library.utoronto.ca/course-reserves-short-term-loan | 2026-09-19 / not-stated | 1 670 | audience=student, department=library, category=library-services, language=en |
| 4 | Services for persons with disabilities | https://utsc.library.utoronto.ca/services-persons-disabilities | 2026-09-19 / not-stated | 3 844 | audience=all, department=library, category=library-services, language=en |
| 5 | Ask a Librarian chat service | https://utsc.library.utoronto.ca/ask-librarian-chat | 2026-09-19 / not-stated | 701 | audience=all, department=library, category=library-services, language=en |
| 6 | Library spaces and services | https://utsc.library.utoronto.ca/library-spaces | 2026-09-19 / not-stated | 2 311 | audience=all, department=library, category=library-services, language=en |
| 7 | UTSC Library hours | https://utsc.library.utoronto.ca/hours | 2026-09-19 / 2026-09-08 | 722 | audience=all, department=library, category=library-services, language=en |
| 8 | Research and publishing services for faculty | https://utsc.library.utoronto.ca/research-publishing | 2026-09-19 / not-stated | 6 056 | audience=faculty, department=library, category=library-services, language=en |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc ngày hiệu lực) trong metadata.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| `audience` | enum | `student` / `faculty` / `all` | Trường bắt buộc của L3A để `metadata_filter={"audience": "student"}` loại tài liệu cho đối tượng khác (ví dụ câu hỏi dành cho sinh viên không được trả bằng trang InfoExpress dành cho faculty) |
| `department` | enum | `library` | Cho phép mở rộng sang corpus phòng ban khác (academic-affairs…) mà vẫn lọc được theo đơn vị chịu trách nhiệm |
| `category` | enum | `library-services` | Phân biệt nhóm chủ đề con khi corpus phình ra nhiều mảng dịch vụ |
| `language` | enum | `en` | Corpus dùng nguồn tiếng Anh nhưng bộ câu hỏi có thể trộn tiếng Việt — lọc ngôn ngữ tránh nhầm tài liệu tiếng Việt khác trong repo |
| `document_version` | date / `not-stated` | `2025-12-17` | Chính sách mượn/trả thay đổi theo thời gian; cho phép ưu tiên/thay thế phiên bản mới và ghi rõ nguồn "cập nhật ngày nào" khi trích dẫn |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> Mỗi thành viên thử **một chiến lược khác nhau** trên cùng bộ tài liệu; nhóm tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| | FixedSizeChunker (`fixed_size`) | | | |
| | SentenceChunker (`by_sentences`) | | | |
| | RecursiveChunker (`recursive`) | | | |

### Chiến lược của từng thành viên

> Mỗi thành viên điền một khối dưới đây (copy thêm nếu nhóm có nhiều hơn 3 người).

**Thành viên 1 — [Tên]**
- **Loại chiến lược:** [FixedSize / Sentence / Recursive / custom]
- **Mô tả & lý do chọn cho chủ đề này:** *(2-3 câu)*
- **Code snippet (nếu custom):**
```python
# Dán mã nguồn (implementation) vào đây
```

**Thành viên 2 — [Tên]**
- **Loại chiến lược:**
- **Mô tả & lý do chọn:**
- **Code snippet (nếu custom):**

**Thành viên 3 — [Tên]**
- **Loại chiến lược:**
- **Mô tả & lý do chọn:**
- **Code snippet (nếu custom):**

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| | | | | |
| | | | | |
| | | | | |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> *Viết 2-3 câu — đây là phần được đánh giá cao nhất (khả năng suy nghĩ & giải thích):*

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> **Đúng 5 câu hỏi**, đa dạng, có thể kiểm chứng; **ít nhất 1 câu** cần lọc metadata mới trả lời tốt. Đây là bộ câu hỏi chung cho mọi thành viên chạy.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | What are the UTSC Library's regular opening hours from Monday to Friday between September 8 and December 22, 2026? | The library's regular weekday hours are 8:00 AM to 10:00 PM. It is closed on October 12, 2026. | `utsc-library-hours` — "Library Hours" (đã kiểm chứng: "8:00 AM - 10:00 PM" và "closed on October 12" có nguyên văn trong tài liệu) |
| 2 | As an undergraduate student, how long can I borrow regular library items, and what is my item limit? | Undergraduate students have a regular loan period of 14 days and an item limit of 50. | `utsc-borrowing-policy` — bảng "Loan privileges by patron type at most University of Toronto Libraries", hàng Undergraduate students (14 days / Unlimited / 50) |
| 3 | Where should a user return a borrowed laptop from the Technology Loans collection? | A borrowed laptop should be returned directly to the Info Desk. | `utsc-technology-loans` — đoạn mở đầu "Technology Loans", câu "Large electronic devices (laptops, monitors, cameras, etc.) should be returned directly to the Info Desk." |
| 4 | A student needs to find a physical course reading placed on reserve. Where is it located? | Physical course reserves are located 20 steps to the left of the InfoDesk at the UTSC Library. | `utsc-course-reserves` — mục "Where are physical course reserves located?" |
| 5 | Which service provides a free and secure University of Toronto repository for disseminating and preserving faculty and graduate-student research? | TSpace – University of Toronto Research Repository. | `utsc-research-publishing` — mục "TSpace - University of Toronto Research Repository" ("free and secure research repository… including faculty and graduate student research") |

**Ghi chú đánh giá từng câu (nhóm thống nhất):**

| # | Ghi chú đánh giá |
|---|------------------|
| 1 | Tra cứu thời gian và nhận biết ngoại lệ (ngày đóng cửa 12/10) — câu hỏi hai phần, tách được chunk có giờ và câu ngoại lệ cùng một chunk giờ tốt. |
| 2 | Phân biệt quy định dành cho sinh viên đại học với các nhóm khác (graduate/faculty đều là 90 ngày) — chunk chứa bảng loan privileges phải trích đúng hàng Undergraduate. |
| 3 | Tra cứu địa điểm và quy trình trả thiết bị — đáp án nằm ở đoạn văn mở đầu, không phải trong danh mục thiết bị; chunk mở đầu phải thắng các chunk catalogue dài phía sau. |
| 4 | **A/B test:** chạy không lọc so với `metadata_filter={"audience": "student"}` — đo xem lọc trước có cải thiện top-3 không (đây là câu thỏa ràng buộc "ít nhất 1 câu cần metadata_filter"). |
| 5 | Định danh dịch vụ theo chức năng — đáp án nằm trong tài liệu `audience: faculty`, kiểm tra xem query "sinh ngữ nghĩa" (không nhắc tên TSpace) có kéo được chunk đúng lên top-3. |

### Tổng hợp chất lượng truy xuất của nhóm

> Cách chấm (theo `docs/SCORING.md`): **2 điểm/câu** — top-3 chứa chunk liên quan + agent trả lời đúng (2), có liên quan nhưng thiếu/không ở top-1 (1), không có trong top-3 (0).

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> *Viết 2-3 câu:*

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
> *Liệt kê 2-3 ý:*

**Bài học rút ra khi so sánh trong nhóm:**
> *Viết 2-3 câu — cùng tài liệu nhưng chiến lược khác nhau dẫn tới khác biệt gì?*

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> *Viết 2-3 câu:*

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | / 10 |
| Thiết kế chiến lược (Strategy Design) | / 15 |
| Chất lượng truy xuất (Retrieval Quality) | / 10 |
| Thuyết trình (Demo) | / 5 |
| **Tổng phần nhóm** | **/ 40** |
