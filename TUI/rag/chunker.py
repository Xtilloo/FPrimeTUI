import hashlib
import re

TARGET_TOKENS = 300
CHARS_PER_TOKEN = 4  # rough estimate

_CODE_EXTENSIONS = {".fpp", ".hpp", ".h", ".cpp", ".py"}

_FPP_SPEC_PREFIXES = ("docs/reference/fpp-", "docs/user-manual/fpp-")
FPP_SPEC_MAX_CHARS = 2000  # ~500 tokens — dense DSL docs need larger chunks


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
    max_chars = FPP_SPEC_MAX_CHARS if source.startswith(_FPP_SPEC_PREFIXES) else TARGET_TOKENS * CHARS_PER_TOKEN
    sections = re.split(r'(?=^#{1,2} )', text, flags=re.MULTILINE)
    chunks = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        truncated = _truncate(section, max_chars=max_chars)
        chunks.append({
            "text": truncated,
            "source_file": source,
            "chunk_type": "markdown",
            "component_name": "",
            "content_type": detect_content_type(truncated, source),
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
            "content_type": "code",
        })
    if not chunks:
        # Fallback: treat whole file as one chunk
        chunks.append({
            "text": _truncate(text),
            "source_file": source,
            "chunk_type": "fpp_block",
            "component_name": "",
            "content_type": "code",
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
            "content_type": "code",
        })
    return chunks


# Patterns for C++ chunking
_CPP_PREPROCESSOR = re.compile(r"^\s*#\s*(?:ifndef|define|endif|include|pragma)\b.*$", re.MULTILINE)
_CPP_NAMESPACE = re.compile(r"namespace\s+([\w:]+)\s*\{")
_CPP_CLASS_OR_STRUCT = re.compile(r"(?:class|struct)\s+(\w+)(?:\s*:\s*(?:public|protected|private)\s+[\w:]+)?\s*\{")
_CPP_ENUM = re.compile(r"enum\s+(?:class\s+)?(\w+)\s*\{")
_CPP_SPLIT = re.compile(r"(?=(?:class|struct|enum)\s+\w+)")


def chunk_cpp(text: str, source: str) -> list[dict]:
    """Split C++ header/source files on class, struct, and enum boundaries."""
    # Strip preprocessor lines
    cleaned = _CPP_PREPROCESSOR.sub("", text)

    # Detect enclosing namespace for context prefix
    ns_match = _CPP_NAMESPACE.search(cleaned)
    ns_prefix = f"namespace {ns_match.group(1)} :: " if ns_match else ""

    # Split on class/struct/enum declarations
    sections = _CPP_SPLIT.split(cleaned)
    chunks: list[dict] = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Determine component name from class/struct/enum
        comp_name = ""
        class_match = _CPP_CLASS_OR_STRUCT.search(section)
        enum_match = _CPP_ENUM.search(section)
        if class_match:
            comp_name = class_match.group(1)
        elif enum_match:
            comp_name = enum_match.group(1)

        # Only keep sections that contain a declaration (skip preamble noise)
        if not comp_name:
            continue

        # Prepend namespace context
        chunk_text = f"{ns_prefix}{section}" if ns_prefix else section

        chunks.append({
            "text": _truncate(chunk_text),
            "source_file": source,
            "chunk_type": "cpp",
            "component_name": comp_name,
            "content_type": "code",
        })

    if not chunks:
        # Fallback: whole file as one chunk
        chunks.append({
            "text": _truncate(cleaned),
            "source_file": source,
            "chunk_type": "cpp",
            "component_name": "",
            "content_type": "code",
        })

    return chunks


_AC_METHOD_PATTERN = re.compile(
    r"^\s+(?:virtual\s+)?(?:[\w:]+\s+)+(\w+)\s*\([^)]*\)(?:\s*(?:const|override|=\s*0))?\s*;",
    re.MULTILINE,
)
# Skip patterns: constructors, destructors, serialization, dispatch, private helpers
_AC_SKIP_PATTERNS = re.compile(
    r"(?:~?\w+ComponentBase|serialize|deserialize|dispatchMsg|__\w+|m_p_\w+)"
)


def chunk_autocoded_cpp(text: str, source: str) -> list[dict]:
    """Extract public/protected API signatures from autocoded *Ac.hpp/*Ac.cpp files."""
    # Find class name
    class_match = _CPP_CLASS_OR_STRUCT.search(text)
    comp_name = class_match.group(1) if class_match else ""

    # Extract sections by visibility
    # Split into public/protected/private sections
    signatures: list[str] = []
    in_api_section = False

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("public:") or stripped.startswith("protected:"):
            in_api_section = True
            continue
        elif stripped.startswith("private:"):
            in_api_section = False
            continue

        if not in_api_section:
            continue

        # Check if line looks like a method signature
        method_match = _AC_METHOD_PATTERN.match(line)
        if method_match:
            method_name = method_match.group(1)
            # Skip constructors, destructors, serialization boilerplate
            if _AC_SKIP_PATTERNS.search(method_name):
                continue
            signatures.append(stripped.rstrip(";").strip())

    if signatures:
        header = f"Component {comp_name} API:" if comp_name else "API:"
        sig_text = header + "\n" + "\n".join(f"  {sig}" for sig in signatures)
    else:
        sig_text = f"Component {comp_name}: no public/protected API extracted" if comp_name else text[:200]

    return [{
        "text": _truncate(sig_text),
        "source_file": source,
        "chunk_type": "cpp_api",
        "component_name": comp_name.replace("ComponentBase", "").replace("Base", ""),
        "content_type": "reference",
    }]


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
