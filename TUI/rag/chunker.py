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


# ---------------------------------------------------------------------------
# FPP chunker helpers
# ---------------------------------------------------------------------------

def _fpp_extract_block(text: str, start: int) -> int:
    """
    Given text and the index of the opening '{', return the index one past
    the matching closing '}' using a brace-depth counter.
    Returns -1 if no matching brace is found.
    """
    depth = 0
    i = start
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def _fpp_collect_annotation(lines: list[str], idx: int) -> str:
    """
    Walk backward from line idx-1 to collect consecutive `@` annotation lines.
    Returns them joined with newlines (empty string if none).
    """
    ann_lines: list[str] = []
    j = idx - 1
    while j >= 0 and lines[j].strip().startswith("@"):
        ann_lines.insert(0, lines[j])
        j -= 1
    return "\n".join(ann_lines)


def _fpp_make_chunk(text: str, name: str, source: str, module_prefix: str) -> dict:
    full_text = (module_prefix + text) if module_prefix else text
    return {
        "text": _truncate(full_text),
        "source_file": source,
        "chunk_type": "fpp_block",
        "component_name": name,
        "content_type": "code",
    }


def _in_extracted(pos: int, ranges: list[tuple[int, int]]) -> bool:
    """Return True if pos falls within any already-extracted character range."""
    return any(start <= pos < end for start, end in ranges)


# Regex patterns for FPP construct detection.
# _FPP_BLOCK_OPEN uses a named 'brace' group so the '{' position is robust
# to future additions of capturing groups before it.
_FPP_BLOCK_OPEN = re.compile(
    r"^[ \t]*(?P<keyword>"
    r"(?:active\s+|passive\s+|queued\s+)?component"
    r"|enum"
    r"|struct"
    r"|interface"
    r"|state\s+machine(?!\s+instance\b)"
    r"|topology"
    r")\s+(?P<name>\w+)(?:[^{\n]*)(?P<brace>\{)",
    re.MULTILINE,
)
_FPP_LINE_CONSTRUCTS = re.compile(
    r"^[ \t]*(?P<keyword>type|constant|array|instance|state\s+machine)\s+(?P<name>\w+)",
    re.MULTILINE,
)
_FPP_PORT_LINE = re.compile(r"^[ \t]*port\s+(?P<name>\w+)", re.MULTILINE)


def chunk_fpp(text: str, source: str) -> list[dict]:
    """
    Extract all FPP language constructs from a .fpp file.

    Strategies:
    - Block constructs (component, enum, struct, interface, state machine,
      topology): brace-counting extractor.
    - Port: paren-depth counter for multi-line argument lists.
    - Line constructs (type, constant, array, instance): line collector with
      backslash-continuation and optional phase-block for instances.
    - Module blocks: tracked as namespace prefix, not emitted as chunks.
    - Annotations (@): included in chunk text.
    - Nested constructs inside components: second pass over component text.
    - _in_extracted() prevents Pass 2/3 from double-emitting items from Pass 1.
    """
    chunks: list[dict] = []
    lines = text.split("\n")

    # ------------------------------------------------------------------
    # Build per-line module prefix by scanning module open/close braces.
    # ------------------------------------------------------------------
    module_stack: list[str] = []
    line_module_prefix: list[str] = [""] * len(lines)
    module_open_depths: list[tuple[int, str]] = []  # (depth_when_opened, name)
    depth = 0

    for i, line in enumerate(lines):
        m = re.match(r"^[ \t]*module\s+(\w+)\s*\{", line)
        if m:
            depth += line.count("{") - line.count("}")
            module_stack.append(m.group(1))
            module_open_depths.append((depth, m.group(1)))
        else:
            depth += line.count("{") - line.count("}")
            # Pop modules whose enclosing brace depth has been exited
            while module_open_depths and depth < module_open_depths[-1][0]:
                module_open_depths.pop()
                if module_stack:
                    module_stack.pop()

        prefix = " :: ".join(module_stack)
        line_module_prefix[i] = (f"module {prefix} :: ") if prefix else ""

    # ------------------------------------------------------------------
    # Pass 1: extract block constructs using brace-counter.
    # ------------------------------------------------------------------
    extracted_ranges: list[tuple[int, int]] = []  # (start_char, end_char)

    for m in _FPP_BLOCK_OPEN.finditer(text):
        brace_start = m.start("brace")
        end = _fpp_extract_block(text, brace_start)
        if end == -1:
            continue

        # For structs: extend extraction to include optional "default { ... }" clause.
        keyword = m.group("keyword").strip()
        if keyword == "struct":
            # Look ahead up to 30 chars for a 'default {' clause immediately after the
            # closing '}' of a struct. FPP style always puts 'default' on the same or
            # next line with no intervening content — 30 chars is a safe window.
            default_m = re.match(r"\s*default\s*\{", text[end:end + 30])
            if default_m:
                default_brace = end + default_m.end() - 1
                default_end = _fpp_extract_block(text, default_brace)
                if default_end != -1:
                    end = default_end

        block_text = text[m.start():end]
        name = m.group("name")
        line_idx = text[:m.start()].count("\n")
        ann = _fpp_collect_annotation(lines, line_idx)
        if ann:
            block_text = ann + "\n" + block_text

        module_prefix = line_module_prefix[line_idx] if line_idx < len(line_module_prefix) else ""
        chunks.append(_fpp_make_chunk(block_text, name, source, module_prefix))
        extracted_ranges.append((m.start(), end))

        # Second pass for nested constructs inside component blocks.
        keyword = m.group("keyword").strip()
        if "component" in keyword:
            inner_text = text[brace_start + 1:end - 1]
            inner_chunks = _fpp_extract_inner_constructs(inner_text, source, module_prefix)
            chunks.extend(inner_chunks)

    # ------------------------------------------------------------------
    # Pass 2: extract port signatures (paren-depth counter).
    # Skips ports inside already-extracted blocks via _in_extracted.
    # ------------------------------------------------------------------
    for m in _FPP_PORT_LINE.finditer(text):
        if _in_extracted(m.start(), extracted_ranges):
            continue
        name = m.group("name")
        line_idx = text[:m.start()].count("\n")
        ann = _fpp_collect_annotation(lines, line_idx)
        module_prefix = line_module_prefix[line_idx] if line_idx < len(line_module_prefix) else ""

        # Walk forward using a paren-depth counter.
        i = m.start()
        paren_depth = 0
        found_open = False
        while i < len(text):
            ch = text[i]
            if ch == "(":
                paren_depth += 1
                found_open = True
            elif ch == ")":
                paren_depth -= 1
                if paren_depth == 0:
                    i += 1
                    break
            elif ch == "\n" and not found_open:
                # No opening paren on this line — single-line port, done.
                i += 1
                break
            i += 1

        # Capture optional "-> ReturnType" after closing paren.
        remainder = text[i:i + 40]
        ret_m = re.match(r"[ \t]*->[ \t]*\w+", remainder)
        if ret_m:
            i += ret_m.end()

        port_text = text[m.start():i].rstrip()
        if ann:
            port_text = ann + "\n" + port_text

        chunks.append(_fpp_make_chunk(port_text, name, source, module_prefix))

    # ------------------------------------------------------------------
    # Pass 3: extract line/continuation constructs.
    # Skips items already captured as blocks via _in_extracted.
    # ------------------------------------------------------------------
    for m in _FPP_LINE_CONSTRUCTS.finditer(text):
        if _in_extracted(m.start(), extracted_ranges):
            continue
        keyword = m.group("keyword").strip()
        name = m.group("name")
        line_idx = text[:m.start()].count("\n")
        ann = _fpp_collect_annotation(lines, line_idx)
        module_prefix = line_module_prefix[line_idx] if line_idx < len(line_module_prefix) else ""

        # Collect from this line, following \ continuations.
        construct_lines: list[str] = []
        j = line_idx
        while j < len(lines):
            construct_lines.append(lines[j])
            if lines[j].rstrip().endswith("\\"):
                j += 1
                continue
            # For instances: handle phase block.
            if keyword == "instance":
                # Case 1: current stopping line IS the '{' (e.g. continuation ended with \
                # on the previous line, next line is '{')
                if lines[j].strip().startswith("{"):
                    # Note: assumes Unix line endings (\n only). FPP source files are always
                    # Unix-terminated (the fpp toolchain enforces this).
                    char_pos = sum(len(lines[n]) + 1 for n in range(j)) + lines[j].index("{")
                    end = _fpp_extract_block(text, char_pos)
                    if end != -1:
                        end_line = text[:end].count("\n")
                        # Replace last appended line with the full block content
                        construct_lines.pop()
                        construct_lines.extend(lines[j:end_line + 1])
                else:
                    # Case 2: check if the next non-empty line opens a phase block.
                    k = j + 1
                    while k < len(lines) and not lines[k].strip():
                        k += 1
                    if k < len(lines) and lines[k].strip().startswith("{"):
                        # Note: assumes Unix line endings (\n only). FPP source files are always
                        # Unix-terminated (the fpp toolchain enforces this).
                        char_pos = sum(len(lines[n]) + 1 for n in range(k)) + lines[k].index("{")
                        end = _fpp_extract_block(text, char_pos)
                        if end != -1:
                            end_line = text[:end].count("\n")
                            construct_lines.extend(lines[k:end_line + 1])
            break  # Non-continuation, non-instance-phase: collection complete.

        construct_text = "\n".join(construct_lines)

        # Belt-and-suspenders: a "state machine" match from _FPP_LINE_CONSTRUCTS
        # that includes a '{' was already handled by Pass 1 and excluded via
        # _in_extracted above. This guard catches any edge case where the range
        # check missed it.
        if keyword == "state machine" and "{" in construct_text:
            continue

        if ann:
            construct_text = ann + "\n" + construct_text

        chunks.append(_fpp_make_chunk(construct_text, name, source, module_prefix))

    # ------------------------------------------------------------------
    # Fallback: if nothing extracted, emit whole file as one chunk.
    # ------------------------------------------------------------------
    if not chunks:
        chunks.append({
            "text": _truncate(text),
            "source_file": source,
            "chunk_type": "fpp_block",
            "component_name": "",
            "content_type": "code",
        })

    return chunks


def _fpp_extract_inner_constructs(inner_text: str, source: str, module_prefix: str) -> list[dict]:
    """Extract enum, struct, constant definitions nested inside a component block."""
    chunks: list[dict] = []
    lines = inner_text.split("\n")

    # Block inner constructs: enum, struct
    for m in re.finditer(r"^[ \t]*(?P<keyword>enum|struct)\s+(?P<name>\w+)[^{]*(?P<brace>\{)", inner_text, re.MULTILINE):
        brace_start = m.start("brace")
        end = _fpp_extract_block(inner_text, brace_start)
        if end == -1:
            continue
        block_text = inner_text[m.start():end]
        line_idx = inner_text[:m.start()].count("\n")
        ann = _fpp_collect_annotation(lines, line_idx)
        if ann:
            block_text = ann + "\n" + block_text
        chunks.append(_fpp_make_chunk(block_text, m.group("name"), source, module_prefix))

    # Line inner constructs: constant
    for m in re.finditer(r"^[ \t]*constant\s+(\w+)", inner_text, re.MULTILINE):
        name = m.group(1)
        line_idx = inner_text[:m.start()].count("\n")
        ann = _fpp_collect_annotation(lines, line_idx)
        line_text = lines[line_idx] if line_idx < len(lines) else ""
        if ann:
            line_text = ann + "\n" + line_text
        chunks.append(_fpp_make_chunk(line_text, name, source, module_prefix))

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
    r"^\s+(?:virtual\s+)?(?:[\w:*&]+\s+)+(\w+)\s*\([^)]*\)(?:\s*(?:const|override|=\s*0))?\s*;",
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
