# Plugin Guide — Custom Extractors & Chunkers

OpenNotebook provides an extensible architecture for adding custom document extractors, content scrapers, and chunking algorithms.

---

## 1. Extractor Architecture

Extractors take raw byte streams or remote references (e.g., URLs, storage URIs) and transform them into standardized text content enriched with page and section metadata.

All extractors live under `backend/app/domain/sources/` or can be registered dynamically.

### Extractor Interface
An extractor must return clean text accompanied by metadata dictionaries:

```python
from dataclasses import dataclass
from typing import BinaryIO

@dataclass
class ExtractedDocument:
    content: str
    metadata: dict
    sections: list[dict]

class BaseExtractor:
    def extract(self, stream: BinaryIO, filename: str) -> ExtractedDocument:
        raise NotImplementedError
```

### Supported Built-in Extractors
* **PDF Extractor:** Uses `PyMuPDF` (`fitz`) to extract page-by-page text, preserving reading order and table structure.
* **Word Document Extractor:** Uses `python-docx` for `.docx` formatting, headings, and lists.
* **Web Scraper:** Uses `trafilatura` to extract boilerplate-free article text from public URLs.
* **YouTube Transcript Extractor:** Uses `youtube-transcript-api` to extract timestamped subtitles from video URLs.

---

## 2. Implementing a Custom Extractor

Here is an example of creating a custom **CSV/Tabular Extractor**:

```python
import csv
import io
from typing import BinaryIO

class CsvExtractor(BaseExtractor):
    def extract(self, stream: BinaryIO, filename: str) -> ExtractedDocument:
        content_lines = []
        reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8"))
        for row_idx, row in enumerate(reader):
            formatted_row = " | ".join(f"{k}: {v}" for k, v in row.items())
            content_lines.append(f"Row {row_idx + 1}: {formatted_row}")
            
        full_text = "\n".join(content_lines)
        return ExtractedDocument(
            content=full_text,
            metadata={"filename": filename, "type": "tabular/csv"},
            sections=[{"index": 0, "title": "Table Data"}]
        )
```

---

## 3. Chunker Architecture

Once text is extracted, it passes to the chunker to create appropriately sized semantic fragments for vectorization.

* **Default Chunker:** Recursive token-aware semantic chunker targeting ~800 tokens with a 100-token overlap.
* **Custom Chunkers:** Can be implemented to respect domain-specific boundaries (e.g. Markdown headers, legal clauses, code functions).

---

## 4. Testing Your Plugin

Add unit tests in `backend/tests/unit/test_extractors.py`:

```python
def test_custom_csv_extractor():
    sample_csv = b"name,role\nAlice,Admin\nBob,Viewer\n"
    extractor = CsvExtractor()
    result = extractor.extract(io.BytesIO(sample_csv), "users.csv")
    
    assert "Alice" in result.content
    assert result.metadata["type"] == "tabular/csv"
```
