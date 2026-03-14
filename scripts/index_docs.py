import os
import json
import asyncio
import re
from pathlib import Path
import ollama
from typing import List, Dict

# Configuration
DOC_DIRS = ["docs", "FPrimeSampleProject/fprime"]
FILE_EXTENSIONS = [".md", ".fpp"]
EMBEDDING_MODEL = "mxbai-embed-large" # Recommended, fallback to qwen3:8b if needed
INDEX_FILE = "TUI/fprime_index.json"

async def get_embedding(client: ollama.AsyncClient, text: str) -> List[float]:
    """Fetches embedding from Ollama."""
    try:
        response = await client.embeddings(model=EMBEDDING_MODEL, prompt=text)
        return response['embedding']
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return []

def chunk_markdown(content: str) -> List[str]:
    """Chunks markdown by headers."""
    chunks = re.split(r'(^#+\s.*)', content, flags=re.MULTILINE)
    combined_chunks = []
    current_chunk = ""
    for segment in chunks:
        if segment.startswith("#"):
            if current_chunk:
                combined_chunks.append(current_chunk.strip())
            current_chunk = segment
        else:
            current_chunk += segment
    if current_chunk:
        combined_chunks.append(current_chunk.strip())
    return [c for c in combined_chunks if len(c) > 50]

def chunk_fpp(content: str) -> List[str]:
    """Chunks FPP by component/port/topology definitions."""
    # Simple regex-based chunking for FPP
    chunks = re.split(r'(^\s*(?:active|passive|queued|topology|port|instance|array|enum|struct|constant|type)\s+.*)', content, flags=re.MULTILINE)
    combined_chunks = []
    current_chunk = ""
    for segment in chunks:
        if re.match(r'^\s*(?:active|passive|queued|topology|port|instance|array|enum|struct|constant|type)\s+', segment):
            if current_chunk:
                combined_chunks.append(current_chunk.strip())
            current_chunk = segment
        else:
            current_chunk += segment
    if current_chunk:
        combined_chunks.append(current_chunk.strip())
    return [c for c in combined_chunks if len(c) > 50]

async def index_docs():
    """Main indexing loop."""
    client = ollama.AsyncClient()
    index = []
    
    print(f"🔍 Scanning directories: {DOC_DIRS}")
    files_to_index = []
    for doc_dir in DOC_DIRS:
        for ext in FILE_EXTENSIONS:
            files_to_index.extend(list(Path(doc_dir).rglob(f"*{ext}")))
    
    print(f"📄 Found {len(files_to_index)} files. Starting indexing...")
    
    for i, file_path in enumerate(files_to_index):
        try:
            content = file_path.read_text(encoding="utf-8")
            if file_path.suffix == ".md":
                chunks = chunk_markdown(content)
            elif file_path.suffix == ".fpp":
                chunks = chunk_fpp(content)
            else:
                chunks = [content]
            
            print(f"[{i+1}/{len(files_to_index)}] Indexing {file_path} ({len(chunks)} chunks)...")
            
            for chunk in chunks:
                embedding = await get_embedding(client, chunk)
                if embedding:
                    index.append({
                        "path": str(file_path),
                        "content": chunk,
                        "embedding": embedding
                    })
        except Exception as e:
            print(f"Error indexing {file_path}: {e}")

    print(f"💾 Saving index to {INDEX_FILE}...")
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f)
    print("✅ Indexing complete!")

if __name__ == "__main__":
    asyncio.run(index_docs())
