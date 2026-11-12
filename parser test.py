import pymupdf
from ollama import chat

def split_into_chunks(text, page_number, chunk_size=3000, overlap=300):
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()

        if chunk_text:
            chunk_id = f"P{page_number}-C{len(chunks) + 1}"
            chunks.append({
                "id": chunk_id,
                "page": page_number,
                "text": chunk_text,
            })

        if end == len(text):
            break
        start = end - overlap

    return chunks


chunks = []
with pymupdf.open("FY23-AEPRR-Report.pdf") as doc:
    for page_index in range(len(doc)):
        page_text = doc.load_page(page_index).get_text()
        chunks.extend(split_into_chunks(page_text, page_index + 1))

question = "What is the largest number in this PDF?"
selected_chunks = chunks  # Test only; this may be too much text for a large PDF.

context = "\n\n".join(
    f"[{chunk['id']}]\n{chunk['text']}"
    for chunk in selected_chunks
)

response = chat(
    model="qwen3:4b",
    messages=[{
        "role": "user",
        "content": (
            "Answer using the supplied text. Cite supporting chunk IDs exactly. "
            "If the text doesn't answer the question, say so.\n\n"
            f"Question: {question}\n\nText:\n{context}"
        ),
    }],
)

print(response.message.content)