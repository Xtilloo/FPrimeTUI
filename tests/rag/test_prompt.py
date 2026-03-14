from rag.prompt import build_prompt


def test_build_prompt_includes_context_and_query():
    context = "[SOURCE: Fw/Com.fpp | type: fpp_block]\nPort stuff."
    prompt = build_prompt(context=context, query="What is a port?")
    assert "What is a port?" in prompt
    assert "Fw/Com.fpp" in prompt


def test_build_prompt_includes_system_instruction():
    prompt = build_prompt(context="ctx", query="q")
    assert "fprime expert" in prompt.lower()
    assert "ONLY the context" in prompt


def test_build_prompt_empty_context_still_valid():
    prompt = build_prompt(context="", query="What is fprime?")
    assert "What is fprime?" in prompt
