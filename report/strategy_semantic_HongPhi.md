# Chiến lược chunking cá nhân — Semantic Chunking

**Thành viên — HongPhi**

- **Loại chiến lược:** Semantic (ngữ nghĩa) + Recursive fallback.
- **Cấu hình đã kiểm thử:** tách văn bản thành câu theo dấu câu (`.`, `!`, `?`), dùng embedder thật `text-embedding-3-small` (qua OpenRouter) để nhúng từng câu; tính cosine similarity giữa hai câu liền kề; đặt ranh giới chunk tại vị trí độ tương đồng rơi xuống dưới ngưỡng phân vị 25 của toàn bộ chuỗi similarity; nhóm câu vượt quá 500 ký tự được chia tiếp bằng `RecursiveChunker`; truy xuất `top_k=3`.
- **Mô tả & lý do chọn:** Corpus dịch vụ – quy định thư viện có nhiều phần từ vựng giống nhau nhưng nói về chủ đề khác (bảng hạn mượn, quy trình trả thiết bị, danh mục thiết bị). Cắt theo số ký tự hoặc theo câu không biết ranh giới nào là chuyển chủ đề thật. Tách tại điểm similarity giảm đột ngột cho phép chunk bám theo chuyển đổi ngữ nghĩa — mỗi chunk là một chủ đề trọn vẹn bất kể độ dài, nên embedding của chunk nguyên vẹn hơn khi truy xuất.
- **Metadata filter:** dùng `metadata_filter={"audience": "student"}` cho câu hỏi A/B về mượn/trả khi không thể đến thư viện do khuyết tật — đáp án nằm trong `utsc-borrowing-policy` (student) nhưng `utsc-accessibility-services` (all) cũng nói về proxy borrower với đáp án khác (Pickup Authorization Form), nên filter là bắt buộc để tránh lẫn hai tài liệu. Các câu còn lại chạy không lọc.
- **Code snippet (custom):**

```python
class SemanticChunker:
    """Embed every sentence, cut between two consecutive sentences whose
    similarity drops below the percentile threshold — chunk boundaries
    follow topic shifts instead of a fixed size."""

    def __init__(self, embed_fn, chunk_size: int = 500, percentile: float = 25.0) -> None:
        self.embed_fn = embed_fn
        self.chunk_size = chunk_size
        self.percentile = percentile
        self._fallback = RecursiveChunker(chunk_size=chunk_size)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
        if len(sentences) == 1:
            return [sentences[0]]

        vectors = [self.embed_fn(sentence) for sentence in sentences]
        similarities = [compute_similarity(vectors[i], vectors[i + 1])
                        for i in range(len(vectors) - 1)]
        threshold = sorted(similarities)[max(0, int(len(similarities) * self.percentile / 100) - 1)]

        # Split AFTER sentence i when its link to sentence i+1 is weak.
        groups: list[list[str]] = [[sentences[0]]]
        for i, similarity in enumerate(similarities):
            if similarity < threshold:
                groups.append([sentences[i + 1]])
            else:
                groups[-1].append(sentences[i + 1])

        chunks: list[str] = []
        for group in groups:
            section = " ".join(group)
            if len(section) <= self.chunk_size:
                chunks.append(section)
            else:
                chunks.extend(self._fallback.chunk(section))
        return chunks
```

**Chiến lược được ưu tiên theo bài giảng:** Semantic chunking — nhóm câu theo khoảng cách ngữ nghĩa đo bằng chính embedder dùng cho truy xuất, nên ranh giới chunk đồng nhất với không gian vector mà search sẽ so khớp (heading chunker bám cấu trúc soạn sẵn của tài liệu, semantic bám trực tiếp nội dung). Kết quả kiểm thử trên 5 benchmark query đạt retrieval top-3 **5/5** (10/10 điểm theo thang SCORING.md, tính cả lượt có filter của câu A/B) và agent answer **5/5**, với tổng cộng **131 chunks**. A/B test cho thấy giá trị của metadata filter: có `audience=student` đạt 2/2, bỏ filter rơi xuống 0/2 vì top-3 bị tài liệu `utsc-accessibility-services` chiếm chỗ và agent trả lời sai quy trình (dịch vụ lấy sách tại chỗ thay vì proxy borrower).
