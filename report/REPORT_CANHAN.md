# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** [Tên sinh viên]
**Nhóm:** [Tên nhóm]
**Ngày:** [Ngày nộp]

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> Cosine similarity đo góc giữa hai vector: giá trị gần 1 nghĩa là hai vector chỉ hướng gần như trùng nhau — hai đoạn text có ý nghĩa/đề tài rất giống nhau dù dùng từ có thể khác; gần 0 nghĩa là gần như không liên quan; âm nghĩa là hướng ngược nhau.

**Ví dụ có độ tương tự CAO:**
- Câu A: "Hạn mượn sách cho sinh viên là bao nhiêu ngày?"
- Câu B: "Sinh viên được mượn tài liệu của thư viện trong bao lâu?"
- Tại sao tương đồng: hai câu khác hoàn toàn về từ vựng (hạn mượn ↔ mượn tài liệu... bao lâu) nhưng cùng một ý — hỏi thời hạn mượn của sinh viên; embedding hiểu nghĩa nên vector gần nhau.

**Ví dụ có độ tương tự THẤP:**
- Câu A: "Hạn mượn sách cho sinh viên là bao nhiêu ngày?"
- Câu B: "Cách đặt lịch phỏng vấn công ty trong mùa tuyển dụng."
- Tại sao khác: không chia sẻ đề tài nào (thư viện vs tuyển dụng), vector chỉ hướng gần trực giao → cosine gần 0.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> Text embedding thường được chuẩn hóa hoặc quan trọng là *hướng* (đề tài) chứ không phải độ lớn vector (độ dài văn bản, tần suất từ). Cosine chỉ so hướng nên bất biến với độ lớn; Euclid bị ảnh hưởng bởi độ lớn — văn bản dài có vector "kéo dài" gây sai lệch khoảng cách dù cùng đề tài.

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> *Trình bày phép tính:* công thức `ceil((độ_dài − overlap) / (chunk_size − overlap))` = `ceil((10000 − 50) / (500 − 50))` = `ceil(9950 / 450)` = `ceil(22.11)`.
> *Đáp án:* **23 chunks** — đã kiểm lại bằng `FixedSizeChunker(chunk_size=500, overlap=50).chunk('a'*10000)` chạy thật, ra đúng 23.

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> Overlap 100 → `ceil((10000 − 100) / (500 − 100))` = `ceil(9900/400)` = 25 chunks, tức tăng từ 23 lên 25 vì mỗi bước trượt tiến ngắn lại (400 thay vì 450 ký tự). Muốn overlap lớn hơn vì ranh giới câu/điều khoản vắt qua hai chunk: với overlap, câu nằm sát mép chunk trước vẫn xuất hiện nguyên vẹn trong chunk sau, nên retrieval ít bỏ lỡ thông tin nằm đúng sát ranh giới — cái giá là nhiều chunk hơn (tốn embedding, lưu trữ) và dữ liệu lặp giữa các chunk.

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi lập trình (implement) các phần chính trong gói `src`.

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
> Dùng `re.split(r"(?<=[.!?])\s+", text)` — lookbehind `(?<=...)` cắt ở vị trí *sau* dấu câu nên dấu câu được giữ nguyên ở cuối câu trước, tránh bẫy "nuốt dấu câu" khi split bằng `[.!?]\s+` (với zero-width lookbehind, `\s+` chỉ là mốc kết thúc, không thuộc về phía nào). Gom từng nhóm `max_sentences_per_chunk` câu rồi join bằng dấu cách; text rỗng/chỉ khoảng trắng trả `[]` không crash. Edge case biết là chưa xử lý: chữ viết tắt (`TS.`, `v.v.`, `e.g.`) và số thập phân (`3.5`) bị cắt nhầm thành ranh giới câu vì không phân biệt được dấu chấm giữa câu với dấu chấm kết thúc câu.

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> `_split` cắt bằng separator "to" nhất còn lại (`"\n\n"` → `"\n"` → `". "` → `" "` → `""`), rồi gom các mảnh nhỏ liền kề nối lại (kèm đúng separator) tới sát `chunk_size` — thiếu bước gom này, file nhiều dòng ngắn sẽ sinh hàng trăm chunk vụn. Mảnh nào vẫn quá dài thì đệ quy xuống với danh sách separator mịn hơn (`finer = remaining_separators[1:]`). Ba base case: (1) text rỗng/chỉ whitespace trả `[]`; (2) text ≤ `chunk_size` trả nguyên văn; (3) hết separator (nhất là khi `separators=[]` — test `test_empty_separators_falls_back_gracefully` truyền thẳng vào) thì cắt cứng theo `chunk_size` để không trả chunk quá khổ.

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
> `add_documents` chuyển mỗi `Document` thành một record `{id, content, embedding, metadata}` — 1 `Document` = 1 record, chunking làm ở tầng ngoài nên mỗi chunk là một `Document` riêng. `search` embed query đúng một lần, tính dot product với mọi embedding đã lưu (vector chuẩn hoá sẵn nên dot = cosine), sort giảm dần theo score rồi cắt `top_k`.

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> `search_with_filter` lọc **trước** khi search: chọn trước các record có metadata khớp hết các cặp key/value rồi mới search trong tập ứng viên — nếu lọc sau khi search, các chunk ngoài phạm vi sẽ chiếm hết chỗ trong top_k. `delete_document` xoá mọi record có `metadata['doc_id']` trùng (hoặc id record trùng cho record thêm không có metadata), trả `True` nếu có ít nhất một record bị xoá bằng cách so độ dài store trước/sau.

### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
> `answer` lấy top-k chunk từ store, dựng prompt kiểu RAG: context đánh số `[1]`, `[2]`... chèn vào giữa, kèm chỉ dẫn "trả lời chỉ dựa trên context, nếu không đủ thì nói vậy" để hạn chế LLM bịa; rồi gọi `llm_fn(prompt)` và trả chuỗi kết quả. Trường hợp không có chunk nào thì chèn "(no matching documents found)" thay vì để context rỗng.

---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

Vượt qua bộ kiểm thử là điều kiện tính điểm phần này.

### Kết Quả Kiểm Thử (Test Results)

```
============================= test session starts =============================
collected 42 items

tests/test_solution.py::TestProjectStructure::test_root_main_entrypoint_exists PASSED
tests/test_solution.py::TestProjectStructure::test_src_package_exists PASSED
tests/test_solution.py::TestClassBasedInterfaces::test_chunker_classes_exist PASSED
tests/test_solution.py::TestClassBasedInterfaces::test_mock_embedder_exists PASSED
tests/test_solution.py::TestFixedSizeChunker::test_returns_list PASSED
tests/test_solution.py::TestFixedSizeChunker::test_single_chunk_if_text_shorter PASSED
tests/test_solution.py::TestFixedSizeChunker::test_chunks_respect_size PASSED
tests/test_solution.py::TestFixedSizeChunker::test_correct_number_of_chunks_no_overlap PASSED
tests/test_solution.py::TestFixedSizeChunker::test_overlap_creates_shared_content PASSED
tests/test_solution.py::TestFixedSizeChunker::test_no_overlap_no_shared_content PASSED
tests/test_solution.py::TestFixedSizeChunker::test_empty_text_returns_empty_list PASSED
tests/test_solution.py::TestSentenceChunker::test_returns_list PASSED
tests/test_solution.py::TestSentenceChunker::test_respects_max_sentences PASSED
tests/test_solution.py::TestSentenceChunker::test_single_sentence_max_gives_many_chunks PASSED
tests/test_solution.py::TestSentenceChunker::test_chunks_are_strings PASSED
tests/test_solution.py::TestRecursiveChunker::test_returns_list PASSED
tests/test_solution.py::TestRecursiveChunker::test_chunks_within_size_when_possible PASSED
tests/test_solution.py::TestRecursiveChunker::test_empty_separators_falls_back_gracefully PASSED
tests/test_solution.py::TestRecursiveChunker::test_handles_double_newline_separator PASSED
tests/test_solution.py::TestEmbeddingStore::test_initial_size_is_zero PASSED
tests/test_solution.py::TestEmbeddingStore::test_add_documents_increases_size PASSED
tests/test_solution.py::TestEmbeddingStore::test_add_more_increases_further PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_returns_list PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_returns_at_most_top_k PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_content_key PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_results_have_score_key PASSED
tests/test_solution.py::TestEmbeddingStore::test_search_results_sorted_by_score_descending PASSED
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_returns_string PASSED
tests/test_solution.py::TestKnowledgeBaseAgent::test_answer_non_empty PASSED
tests/test_solution.py::TestComputeSimilarity::test_identical_vectors_return_1 PASSED
tests/test_solution.py::TestComputeSimilarity::test_orthogonal_vectors_return_0 PASSED
tests/test_solution.py::TestComputeSimilarity::test_opposite_vectors_return_minus_1 PASSED
tests/test_solution.py::TestComputeSimilarity::test_zero_vector_returns_0 PASSED
tests/test_solution.py::TestCompareChunkingStrategies::test_returns_three_strategies PASSED
tests/test_solution.py::TestCompareChunkingStrategies::test_each_strategy_has_count_and_avg_length PASSED
tests/test_solution.py::TestCompareChunkingStrategies::test_counts_are_positive PASSED
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_filter_by_department PASSED
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_no_filter_returns_all_candidates PASSED
tests/test_solution.py::TestEmbeddingStoreSearchWithFilter::test_returns_at_most_top_k PASSED
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_true_for_existing_doc PASSED
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_returns_false_for_nonexistent_doc PASSED
tests/test_solution.py::TestEmbeddingStoreDeleteDocument::test_delete_reduces_collection_size PASSED

============================== 42 passed in 0.32s =============================
```

**Số lượng bài test vượt qua (pass):** 42 / 42

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Hạn mượn sách cho sinh viên là bao nhiêu ngày? | Sinh viên được mượn tài liệu của thư viện trong bao lâu? | cao | 0.6206 | ✅ |
| 2 | Hạn mượn sách cho sinh viên là bao nhiêu ngày? | Cách đặt lịch phỏng vấn công ty trong mùa tuyển dụng. | thấp | 0.2325 | ✅ |
| 3 | What are the library opening hours? | How long is the loan period for books? | thấp (cùng lĩnh vực nhưng khác ý định hỏi) | 0.3364 | ✅ |
| 4 | Trả laptop mượn ở đâu? | Borrowed laptops should be returned directly to the Info Desk. | cao (cùng nghĩa, khác ngôn ngữ) | 0.4057 | ❌ |
| 5 | Tiền phạt trả sách trễ là bao nhiêu? | Phí thay thế khi làm mất tài liệu thư viện. | thấp (cùng chủ đề phí, khác ý nghĩa) | 0.4036 | ✅ |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Bất ngờ nhất là cặp 4: hai câu **cùng nghĩa hoàn toàn** nhưng chỉ đạt 0.4057 — thấp hơn cả nửa của cặp 1 (0.6206) dù cũng cùng nghĩa. Nguyên nhân: `text-embedding-3-small` không phải mô hình đa ngữ mạnh, không gian vector của tiếng Việt và tiếng Anh chưa thẳng hàng tốt, nên "cùng nghĩa" chỉ đo được chính xác khi hai câu cùng ngôn ngữ. Điều này nói lên hai điều: embedding mã hoá *ngữ nghĩa theo ngôn ngữ của văn bản* chứ không phải một không gian ý nghĩa phổ quát hoàn hảo; và với corpus đa ngữ, nên chọn embedder multilingual chuyên dụng (repo có sẵn `paraphrase-multilingual-MiniLM-L12-v2` cho mục đích này). Cặp 3 cũng thú vị: hai câu cùng lĩnh vực thư viện chỉ được 0.34 — embedding phân biệt *ý định hỏi* chứ không gộp chung theo chủ đề rộng, đúng thứ retrieval cần.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chạy **5 câu hỏi đánh giá của nhóm** trên mã nguồn cá nhân của bạn trong gói `src`. **5 câu hỏi này phải trùng với các thành viên cùng nhóm** (xem `REPORT_NHOM.md`).

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | What are the UTSC Library's regular opening hours from Monday to Friday between September 8 and December 22, 2026? | `utsc-library-hours#…` — "Library Hours, September 8 - December 22, 2026, Monday - Friday 8:00 AM - 10:00 PM" (score 0.746) | 2/2 | Có | Giờ mở cửa T2–T6 là 8:00 AM – 10:00 PM trong giai đoạn 8/9–22/12/2026 |
| 2 | As an undergraduate student, how long can I borrow regular library items, and what is my item limit? | `utsc-borrowing-policy#…` — bảng "Patron type / Loan period / Item limit" (score 0.671) | 2/2 | Có | Sinh viên đại học mượn 14 ngày, hạn mức 50 tài liệu |
| 3 | Where should a user return a borrowed laptop from the Technology Loans collection? | `utsc-technology-loans#…` — đoạn mở đầu "Technology loans are divided into items…" (score 0.615) | 2/2 | Có | Trả laptop trực tiếp tại Info Desk |
| 4 | How do I borrow and pick up library items when I cannot visit the library myself due to a disability? *(chạy có `metadata_filter={"audience": "student"}`)* | `utsc-borrowing-policy#…` — "Sign in to LibrarySearch… REQUEST: Library Pick Up" (score 0.676) | 2/2 (không filter: 0/2) | Có | Chỉ định proxy borrower hoàn tất application form (UTORid required) |
| 5 | Which service provides a free and secure University of Toronto repository for disseminating and preserving faculty and graduate-student research? | `utsc-research-publishing#…` — "TSpace is a free and secure research repository…" (score 0.698) | 2/2 | Có | TSpace – University of Toronto Research Repository |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 5 / 5

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
> Học được rằng cùng một corpus nhưng FixedSizeChunker cắt vỡ bảng Markdown khiến chunk chứa nửa trên/hạ của bảng mà không chunk nào trọn câu trả lời — trong khi heading/semantic giữ nguyên khối. Còn một bài học từ chính A/B của nhóm: cùng câu hỏi, chỉ vì bỏ `metadata_filter` mà agent chuyển sang trả lời theo tài liệu `utsc-accessibility-services` (sai quy trình) — chứng minh filter phải đặt trước search, và một chunk "đúng chủ đề" không đảm bảo chứa đáp án.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | / 5 |
| Hướng tiếp cận của tôi (My Approach) | / 10 |
| Hoàn thiện code (Core Implementation — tests) | / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | / 5 |
| Kết quả truy xuất của tôi (Competition Results) | / 10 |
| **Tổng phần cá nhân** | **/ 60** |
