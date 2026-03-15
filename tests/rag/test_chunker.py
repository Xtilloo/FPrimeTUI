# tests/rag/test_chunker.py
from rag.chunker import chunk_autocoded_cpp, chunk_cpp, chunk_fpp, chunk_markdown, chunk_python, deduplicate, detect_content_type


def test_chunk_markdown_splits_on_headers():
    text = "# Title\nIntro text.\n## Section A\nContent A.\n## Section B\nContent B."
    chunks = chunk_markdown(text, source="test.md")
    assert len(chunks) == 3
    assert chunks[0]["chunk_type"] == "markdown"
    assert "Section A" in chunks[1]["text"]


def test_chunk_markdown_includes_metadata():
    text = "## Overview\nSome content here."
    chunks = chunk_markdown(text, source="docs/overview.md")
    assert chunks[0]["source_file"] == "docs/overview.md"
    assert chunks[0]["chunk_type"] == "markdown"


def test_chunk_fpp_splits_on_component_blocks():
    text = 'component A {\n  port p: Fw.Com\n}\ncomponent B {\n  port q: Fw.Com\n}'
    chunks = chunk_fpp(text, source="Comp.fpp")
    assert len(chunks) == 2
    assert chunks[0]["component_name"] == "A"


def test_chunk_python_splits_on_class_and_function():
    text = "class Foo:\n    def bar(self):\n        pass\n\ndef baz():\n    pass\n"
    chunks = chunk_python(text, source="example.py")
    assert len(chunks) == 2


def test_deduplicate_removes_identical_content():
    chunks = [
        {"text": "hello world", "source_file": "a.md", "chunk_type": "markdown"},
        {"text": "hello world", "source_file": "b.md", "chunk_type": "markdown"},
        {"text": "different",   "source_file": "c.md", "chunk_type": "markdown"},
    ]
    result = deduplicate(chunks)
    assert len(result) == 2


def test_detect_content_type_code_by_extension():
    assert detect_content_type("int main() {}", "main.cpp") == "code"
    assert detect_content_type("component A {}", "A.fpp") == "code"
    assert detect_content_type("class Foo:", "foo.py") == "code"


def test_detect_content_type_code_by_fenced_blocks():
    text = "Some text\n```cpp\nint x = 5;\nint y = 10;\nint z = 15;\n```\nMore text"
    assert detect_content_type(text, "guide.md") == "code"


def test_detect_content_type_concept():
    text = "## Overview\nF Prime is a flight software framework designed for reusability and portability."
    assert detect_content_type(text, "overview.md") == "concept"


def test_detect_content_type_reference_table():
    text = "| Parameter | Type | Default |\n|---|---|---|\n| timeout | int | 5 |"
    assert detect_content_type(text, "config.md") == "reference"


def test_detect_content_type_tutorial():
    text = "1. First, create the component\n2. Then, add ports\n3. Finally, build"
    assert detect_content_type(text, "docs/how-to/add-comp.md") == "tutorial"


def test_detect_content_type_tutorial_by_path():
    text = "Some general text about setup."
    assert detect_content_type(text, "docs/getting-started/install.md") == "tutorial"


def test_chunk_markdown_includes_content_type():
    text = "## Overview\nF Prime is a framework for flight software."
    chunks = chunk_markdown(text, source="overview.md")
    assert "content_type" in chunks[0]
    assert chunks[0]["content_type"] == "concept"


def test_chunk_fpp_content_type_is_code():
    text = "component A {\n  port p: Fw.Com\n}"
    chunks = chunk_fpp(text, source="Comp.fpp")
    assert chunks[0]["content_type"] == "code"


def test_chunk_python_content_type_is_code():
    text = "class Foo:\n    def bar(self):\n        pass\n"
    chunks = chunk_python(text, source="example.py")
    assert chunks[0]["content_type"] == "code"


def test_chunk_cpp_splits_on_class():
    text = """
#ifndef GUARD_HPP
#define GUARD_HPP

#include <FpConfig.hpp>

namespace Os {

class Task {
  public:
    enum State { RUNNING, IDLE, EXITED };
    void start();
    void stop();
};

class Mutex {
  public:
    void lock();
    void unlock();
};

}  // namespace Os
"""
    chunks = chunk_cpp(text, source="Os/Task/Task.hpp")
    # Should get chunks for Task and Mutex classes
    assert len(chunks) >= 2
    # Task class chunk should mention namespace
    task_chunk = [c for c in chunks if "Task" in c["text"]][0]
    assert "Os" in task_chunk["text"]  # namespace context preserved
    assert task_chunk["content_type"] == "code"
    assert task_chunk["source_file"] == "Os/Task/Task.hpp"


def test_chunk_cpp_splits_on_enum():
    text = """
namespace Fw {

enum class CmdResponse {
    OK,
    VALIDATION_ERROR,
    EXECUTION_ERROR,
};

}  // namespace Fw
"""
    chunks = chunk_cpp(text, source="Fw/Cmd/CmdResponse.hpp")
    assert len(chunks) >= 1
    assert "CmdResponse" in chunks[0]["text"]


def test_chunk_cpp_skips_preprocessor():
    text = """
#ifndef GUARD
#define GUARD
#include <stdio.h>
#include "FpConfig.hpp"

class Foo {
  public:
    void bar();
};
#endif
"""
    chunks = chunk_cpp(text, source="test.hpp")
    for chunk in chunks:
        assert "#ifndef" not in chunk["text"]
        assert "#define GUARD" not in chunk["text"]
        assert "#include" not in chunk["text"]


def test_chunk_cpp_fallback_whole_file():
    # If no class/enum/namespace found, treat whole file as one chunk
    text = "void standalone_function() { return; }"
    chunks = chunk_cpp(text, source="util.cpp")
    assert len(chunks) == 1


def test_chunk_autocoded_api_extracts_signatures():
    text = """
class HealthComponentBase : public Fw::ActiveComponentBase {
  public:
    HealthComponentBase(const char* name);
    ~HealthComponentBase();
    void init(NATIVE_INT_TYPE instance = 0);

  protected:
    void log_WARNING_HI_PingLate(const Fw::StringBase& entry);
    void tlmWrite_PingLateWarnings(U32 count);
    void cmdResponse_out(FwOpcodeType opCode, U32 cmdSeq, Fw::CmdResponse response);
    void pingIn_handler(NATIVE_INT_TYPE portNum, U32 key);

  private:
    void m_p_cmdIn_in(Fw::PassiveComponentBase* callComp, FwIndexType portNum);
    FW_SERIALIZE_STATUS serialize();
};
"""
    chunks = chunk_autocoded_cpp(text, source="Svc/Health/HealthComponentAc.hpp")
    assert len(chunks) >= 1
    chunk_text = chunks[0]["text"]
    # Should include protected methods (the API surface)
    assert "log_WARNING_HI_PingLate" in chunk_text
    assert "tlmWrite_PingLateWarnings" in chunk_text
    assert "cmdResponse_out" in chunk_text
    assert "pingIn_handler" in chunk_text
    # Should skip private methods and constructors
    assert "m_p_cmdIn_in" not in chunk_text
    assert "serialize" not in chunk_text
    assert chunks[0]["chunk_type"] == "cpp_api"


def test_chunk_autocoded_skips_boilerplate():
    text = """
class FooComponentBase {
  public:
    FooComponentBase(const char* name);
    ~FooComponentBase();

  protected:
    void log_ACTIVITY_HI_SomeEvent(U32 arg);

  private:
    void dispatchMsg(ComponentIpcSerializableBuffer& msg);
    FW_SERIALIZE_STATUS __serialize(NATIVE_INT_TYPE id);
    void __deserialize(Fw::SerialBuffer& buffer);
};
"""
    chunks = chunk_autocoded_cpp(text, source="FooAc.hpp")
    chunk_text = chunks[0]["text"]
    assert "log_ACTIVITY_HI_SomeEvent" in chunk_text
    assert "dispatchMsg" not in chunk_text
    assert "__serialize" not in chunk_text


def test_chunk_autocoded_empty_api():
    text = """
class BarBase {
  private:
    void internal();
};
"""
    chunks = chunk_autocoded_cpp(text, source="BarAc.hpp")
    # Even with no public/protected methods, should return something
    assert len(chunks) >= 1
