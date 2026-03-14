import hashlib
import re

TARGET_TOKENS = 300
CHARS_PER_TOKEN = 4  # rough estimate


def _truncate(text: str, max_chars: int = TARGET_TOKENS * CHARS_PER_TOKEN) -> str:
    return text[:max_chars]


def chunk_markdown(text: str, source: str) -> list[dict]:
    """Split markdown on ## headers. Each section becomes one chunk."""
    sections = re.split(r'(?=^#{1,2} )', text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        chunks.append({
            "text": _truncate(section),
            "source_file": source,
            "chunk_type": "markdown",
            "component_name": "",
        })
    return chunks


def chunk_fpp(text: str, source: str) -> list[dict]:
    """Split .fpp files on component/port/command block boundaries."""
    pattern = re.compile(
        r'((?:active\s+|passive\s+|queued\s+)?(?:component|port|command)\s+(\w+)\s*\{[^}]*\})',
        re.DOTALL
    )
    chunks = []
    for match in pattern.finditer(text):
        block = match.group(1).strip()
        name = match.group(2)
        chunks.append({
            "text": _truncate(block),
            "source_file": source,
            "chunk_type": "fpp_block",
            "component_name": name,
        })
    if not chunks:
        # Fallback: treat whole file as one chunk
        chunks.append({
            "text": _truncate(text),
            "source_file": source,
            "chunk_type": "fpp_block",
            "component_name": "",
        })
    return chunks


def chunk_python(text: str, source: str) -> list[dict]:
    """Split Python files at class and top-level function boundaries."""
    pattern = re.compile(r'(?=^(?:class |def )\w)', re.MULTILINE)
    sections = pattern.split(text)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        chunks.append({
            "text": _truncate(section),
            "source_file": source,
            "chunk_type": "python",
            "component_name": "",
        })
    return chunks


def deduplicate(chunks: list[dict]) -> list[dict]:
    """Remove chunks with identical text content using SHA-256 hashing."""
    seen = set()
    result = []
    for chunk in chunks:
        h = hashlib.sha256(chunk["text"].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            result.append(chunk)
    return result
