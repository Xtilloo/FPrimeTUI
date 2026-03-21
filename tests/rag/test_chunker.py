# tests/rag/test_chunker.py
from rag.chunker import (
    chunk_autocoded_cpp,
    chunk_cpp,
    chunk_fpp,
    chunk_markdown,
    chunk_python,
    deduplicate,
    detect_content_type,
)


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


def test_fpp_spec_larger_chunks():
    # Create content longer than 1200 chars but under 2000
    text = "## FPP Keyword: active component\n" + ("x " * 700)  # ~1400 chars
    chunks = chunk_markdown(text, source="docs/reference/fpp-user-guide.md")
    # Should NOT be truncated at 1200 — FPP spec gets 2000 char limit
    assert len(chunks[0]["text"]) > 1200


def test_chunk_fpp_extracts_enum():
    text = (
        "@ Basic enum\n"
        "enum MyEnum {\n"
        "  VAL_A\n"
        "  VAL_B\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["component_name"] == "MyEnum"
    assert "VAL_A" in chunk["text"]
    assert chunk["chunk_type"] == "fpp_block"
    assert chunk["content_type"] == "code"


def test_chunk_fpp_extracts_enum_with_base_type():
    text = (
        "@ Enum with base type\n"
        "enum StatusEnum : U8 {\n"
        "  OK\n"
        "  ERROR\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert "StatusEnum" in chunks[0]["text"]
    assert ": U8" in chunks[0]["text"]


def test_chunk_fpp_extracts_struct():
    text = (
        "@ A simple struct\n"
        "struct MyStruct {\n"
        "  mVal : U32\n"
        "  mFlag : bool\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "MyStruct"
    assert "mVal" in chunks[0]["text"]


def test_chunk_fpp_extracts_struct_with_default_block():
    text = (
        "struct ComplexStruct {\n"
        "  mEnum : MyEnum\n"
        "} default {\n"
        "  mEnum = MyEnum.VAL_A\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert "default" in chunks[0]["text"]
    assert "VAL_A" in chunks[0]["text"]


def test_chunk_fpp_extracts_constant():
    text = "@ Size constant\nconstant STRING_SIZE = 80\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "STRING_SIZE"
    assert "STRING_SIZE = 80" in chunks[0]["text"]
    assert "@ Size constant" in chunks[0]["text"]


def test_chunk_fpp_extracts_type_alias():
    text = "@ A type alias\ntype MyU32 = U32\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "MyU32"
    assert "type MyU32 = U32" in chunks[0]["text"]


def test_chunk_fpp_extracts_abstract_type():
    text = "@ Abstract type\ntype MyOpaqueBuffer\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "MyOpaqueBuffer"


def test_chunk_fpp_extracts_array():
    text = "@ Fixed-size array\narray MyArray = [3] U32\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "MyArray"
    assert "[3] U32" in chunks[0]["text"]


def test_chunk_fpp_extracts_port_no_args():
    text = "@ No-arg port\nport NoArgsPort\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "NoArgsPort"


def test_chunk_fpp_extracts_port_multiline():
    text = (
        "@ Port with args\n"
        "port PrimitiveArgsPort(\n"
        "  val  : U32\n"
        "  flag : bool\n"
        ") -> bool\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "PrimitiveArgsPort"
    assert "val  : U32" in chunks[0]["text"]
    assert "-> bool" in chunks[0]["text"]


def test_chunk_fpp_extracts_interface():
    text = (
        "interface TimeInterface {\n"
        "  time get port timeGetOut\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "TimeInterface"


def test_chunk_fpp_extracts_state_machine_block():
    text = (
        "@ A simple SM\n"
        "state machine BasicSM {\n"
        "  action doWork\n"
        "  signal SIG_START\n"
        "  initial enter IDLE\n"
        "  state IDLE {\n"
        "    on SIG_START enter RUNNING\n"
        "  }\n"
        "  state RUNNING\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "BasicSM"
    assert "state IDLE" in chunks[0]["text"]


def test_chunk_fpp_extracts_bare_state_machine_declaration():
    text = "@ External SM type\nstate machine MyStateMachine\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "MyStateMachine"


def test_chunk_fpp_extracts_topology():
    text = (
        "topology RefTopology {\n"
        "  instance myComp\n"
        "  connections Normal {\n"
        "    myComp.out -> myComp.in\n"
        "  }\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "RefTopology"
    assert "connections Normal" in chunks[0]["text"]


def test_chunk_fpp_extracts_instance():
    text = (
        "instance myActive: MyActiveComp base id 0x03000 \\\n"
        "  queue size 25 \\\n"
        "  priority 50\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "myActive"
    assert "queue size 25" in chunks[0]["text"]


def test_chunk_fpp_extracts_instance_with_phase_block():
    text = (
        "instance myComp: MyComp base id 0x01000 \\\n"
        "  queue size 10 \\\n"
        "  priority 30 \\\n"
        "{\n"
        "  phase Fpp.ToCpp.Phases.configConstants \"\"\"\n"
        "  enum { MY_CONST = 42 };\n"
        "  \"\"\"\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == "myComp"
    assert "MY_CONST" in chunks[0]["text"]


def test_chunk_fpp_module_prefix_applied_to_chunks():
    text = (
        "module Ref {\n"
        "  constant FOO = 1\n"
        "  enum Bar {\n"
        "    A\n"
        "  }\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 2
    for chunk in chunks:
        assert chunk["text"].startswith("module Ref :: ")


def test_chunk_fpp_nested_enum_inside_component():
    text = (
        "active component MyComp {\n"
        "  enum OperatingMode : U8 {\n"
        "    IDLE\n"
        "    RUNNING\n"
        "  }\n"
        "  async input port schedIn: NoArgsPort\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    names = {c["component_name"] for c in chunks}
    assert "MyComp" in names
    assert "OperatingMode" in names


def test_chunk_fpp_annotation_included_in_chunk_text():
    text = "@ This is a doc annotation\nconstant MY_CONST = 42\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert "@ This is a doc annotation" in chunks[0]["text"]


def test_chunk_fpp_state_machine_block_not_double_emitted():
    """A state machine block must not be emitted once by Pass 1 and again by Pass 3."""
    text = (
        "state machine BasicSM {\n"
        "  signal SIG_START\n"
        "  state IDLE\n"
        "}\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    names = [c["component_name"] for c in chunks]
    assert names.count("BasicSM") == 1


def test_chunk_fpp_port_inside_component_not_separately_emitted():
    """Ports declared inside a component block must not be emitted as separate port chunks."""
    text = (
        "passive component MyComp {\n"
        "  sync input port dataIn: NoArgsPort\n"
        "  output port dataOut: NoArgsPort\n"
        "}\n"
        "port StandalonePort\n"
    )
    chunks = chunk_fpp(text, source="test.fpp")
    names = {c["component_name"] for c in chunks}
    assert "MyComp" in names
    assert "StandalonePort" in names
    assert "dataIn" not in names
    assert "dataOut" not in names


def test_chunk_fpp_reference_file_covers_all_constructs():
    """Smoke test: fpp_reference.fpp must produce chunks for all expected construct types."""
    from pathlib import Path
    ref = Path(__file__).parents[2] / "docs/fprime-docs/fpp_reference.fpp"
    text = ref.read_text()
    chunks = chunk_fpp(text, source="docs/fprime-docs/fpp_reference.fpp")

    names = {c["component_name"] for c in chunks}
    assert "MyEnum" in names
    assert "StatusEnum" in names
    assert "PrimitiveStruct" in names
    assert "MyArray" in names
    assert "STRING_SIZE" in names
    assert "MyU32" in names
    assert "NoArgsPort" in names
    assert "PrimitiveArgsPort" in names
    assert "TimeInterface" in names
    assert "MyPassiveComp" in names
    assert "MyQueuedComp" in names
    assert "MyActiveComp" in names
    assert "BasicSM" in names
    assert "RefTopology" in names
    assert "myActive" in names


def test_chunk_fpp_fallback_for_unrecognised_content():
    text = "# Just a comment with no constructs\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert chunks[0]["component_name"] == ""
    assert chunks[0]["chunk_type"] == "fpp_block"


def test_chunk_fpp_no_module_prefix_at_top_level():
    text = "constant TOP_LEVEL = 1\n"
    chunks = chunk_fpp(text, source="test.fpp")
    assert len(chunks) == 1
    assert not chunks[0]["text"].startswith("module ")
