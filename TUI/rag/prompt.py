SYSTEM = (
    "You are an fprime expert assistant. "
    "Answer using ONLY the context below. "
    "Cite sources by filename in your answer. "
    "If the context does not contain enough information to answer, say so clearly."
)


def build_prompt(context: str, query: str) -> str:
    """Assemble the full prompt string for the LLM."""
    return f"{SYSTEM}\n\n{context}\n\nQuestion: {query}"
