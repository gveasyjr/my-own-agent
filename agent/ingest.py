import os
from pathlib import Path
import chromadb
from pypdf import PdfReader

DOCS_PATH = Path("/Users/geoffreyveasy/MYSERVER/agent/docs")
CHROMA_PATH = "/Users/geoffreyveasy/MYSERVER/agent/memory"

chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
collection = chroma_client.get_or_create_collection(name="documents")

def chunk_text(text, chunk_size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def ingest_txt(filepath):
    text = filepath.read_text(errors="ignore")
    return chunk_text(text)

def ingest_pdf(filepath):
    reader = PdfReader(str(filepath))
    text = "\n".join([page.extract_text() or "" for page in reader.pages])
    return chunk_text(text)

def ingest_all():
    files = list(DOCS_PATH.glob("**/*"))
    supported = [f for f in files if f.suffix.lower() in [".txt", ".pdf", ".md"]]

    if not supported:
        print("No supported files found in docs/ folder.")
        print("Add .txt, .pdf, or .md files to ~/MYSERVER/agent/docs/")
        return

    print(f"Found {len(supported)} file(s) to ingest...")

    for filepath in supported:
        print(f"\n📄 Ingesting: {filepath.name}")
        if filepath.suffix.lower() == ".pdf":
            chunks = ingest_pdf(filepath)
        else:
            chunks = ingest_txt(filepath)

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            doc_id = f"{filepath.name}_{i}"
            collection.upsert(
                documents=[chunk],
                ids=[doc_id],
                metadatas=[{"source": filepath.name, "chunk": i}]
            )

        print(f"  ✅ {len(chunks)} chunks stored")

    print(f"\n🎉 Ingestion complete. Total docs in collection: {collection.count()}")

if __name__ == "__main__":
    ingest_all()