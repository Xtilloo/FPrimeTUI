import hashlib
import re

TARGET_TOKENS = 300
CHARS_PER_TOKEN = 4  # rough estimate

_CODE_EXTENSIONS = {".fpp", ".hpp", ".h", ".cpp", ".py"}


def detect_content_type(text: str, source_file: str) -> str:
    """Classify chunk content as code, concept, reference, or tutorial."""
    # 1. Code files by extension
    for ext in _CODE_EXTENSIONS:
        if source_file.endswith(ext):
            return "code"

    # 2. Tutorial by path
    if "how-to/" in source_file or "getting-started/" in source_file:
        return "tutorial"

    lines = text.strip().split("\n")
    non_empty = [line for line in lines if line.strip()]
    if not non_empty:
        return "concept"

    # 3. Code by fenced block ratio (>50% of non-fence lines inside ```)
    in_fence = False
    code_lines = 0
    fence_lines = 0
    for line in non_empty:
        if line.strip().startswith("```"):
            fence_lines += 1
            in_fence = not in_fence
            continue
        if in_fence:
            code_lines += 1
    total_content = len(non_empty) - fence_lines
    if total_content > 0 and code_lines > total_content / 2:
        return "code"

    # 4. Reference: tables or enum-like listings
    table_lines = sum(1 for line in non_empty if "|" in line and line.strip().startswith("|"))
    if table_lines > 2:
        return "reference"

    # 5. Tutorial: numbered steps
    numbered = sum(1 for line in non_empty if re.match(r"^\s*\d+[\.\)]\s", line))
    if numbered >= 3:
        return "tutorial"

    return "concept"


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
