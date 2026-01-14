"""File processor for extracting text content from uploaded files."""

import csv
import json
from io import BytesIO, StringIO
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class FileProcessor:
    """Service for extracting text from various file types."""

    async def extract_text(
        self,
        file_data: BytesIO,
        content_type: str,
        filename: str,
    ) -> Optional[str]:
        """Extract text content from a file for LLM context."""

        extractors = {
            "text/plain": self._extract_text_plain,
            "text/markdown": self._extract_text_plain,
            "text/csv": self._extract_csv,
            "application/json": self._extract_json,
            "text/x-python": self._extract_code,
            "text/javascript": self._extract_code,
            "application/typescript": self._extract_code,
            "text/html": self._extract_code,
            "text/css": self._extract_code,
            "application/pdf": self._extract_pdf,
        }

        extractor = extractors.get(content_type)
        if extractor:
            try:
                return await extractor(file_data, filename)
            except Exception as e:
                logger.error(
                    "text_extraction_failed",
                    content_type=content_type,
                    filename=filename,
                    error=str(e),
                )
                return None

        # For unsupported types (images, binary docs), return None
        return None

    async def _extract_text_plain(self, data: BytesIO, filename: str) -> str:
        """Extract text from plain text files."""
        return data.read().decode("utf-8", errors="ignore")

    async def _extract_csv(self, data: BytesIO, filename: str) -> str:
        """Extract text from CSV files as formatted table."""
        content = data.read().decode("utf-8", errors="ignore")
        reader = csv.reader(StringIO(content))
        rows = list(reader)

        if not rows:
            return ""

        # Format as markdown table
        result = []
        headers = rows[0]
        result.append("| " + " | ".join(headers) + " |")
        result.append("| " + " | ".join(["---"] * len(headers)) + " |")

        for row in rows[1:50]:  # Limit to 50 rows for context
            if len(row) == len(headers):  # Only include rows with matching columns
                result.append("| " + " | ".join(row) + " |")

        if len(rows) > 51:
            result.append(f"\n... ({len(rows) - 51} more rows)")

        return "\n".join(result)

    async def _extract_json(self, data: BytesIO, filename: str) -> str:
        """Extract JSON content as formatted string."""
        content = data.read().decode("utf-8", errors="ignore")
        parsed = json.loads(content)
        # Pretty print with indentation
        return json.dumps(parsed, indent=2)[:10000]  # Limit to 10k chars

    async def _extract_code(self, data: BytesIO, filename: str) -> str:
        """Extract code files with syntax context."""
        content = data.read().decode("utf-8", errors="ignore")
        ext = filename.split(".")[-1] if "." in filename else "txt"
        return f"```{ext}\n{content[:10000]}\n```"

    async def _extract_pdf(self, data: BytesIO, filename: str) -> Optional[str]:
        """Extract text from PDF files."""
        try:
            # Using pypdf for simple extraction
            from pypdf import PdfReader

            reader = PdfReader(data)
            text_parts = []
            for page in reader.pages[:20]:  # Limit to 20 pages
                text_parts.append(page.extract_text())

            return "\n\n".join(text_parts)[:20000]  # Limit total chars
        except ImportError:
            logger.warning("pypdf not installed, PDF extraction unavailable")
            return None
        except Exception as e:
            logger.error("pdf_extraction_failed", error=str(e))
            return None


file_processor = FileProcessor()
