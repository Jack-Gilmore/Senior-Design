import pymupdf
from ollama import chat, embed
import chromadb 

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
with pymupdf.open("Tyndall NRL Doc.pdf") as doc:
    for page_index in range(len(doc)):
        page_text = doc.load_page(page_index).get_text()
        chunks.extend(split_into_chunks(page_text, page_index + 1))

question = "what is the percent of outages on privatized systems for FY 2019? "
selected_chunks = chunks  # Test only; this may be too much text for a large PDF.





embedding_response = embed(model = "embeddinggemma", input=[chunk["text"] for chunk in chunks])
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("pdf_chunks")
collection.add(ids=[chunk["id"] for chunk in chunks], documents=[chunk["text"] for chunk in chunks], embeddings=embedding_response.embeddings, metadatas =[{"page": chunk["page"]} for chunk in chunks], )
question_embedding = embed(model = "embeddinggemma", input=[question]).embeddings[0]
# allows for 5 closest matches, needs to be tested for potential adjustment 
matches = collection.query(query_embeddings=[question_embedding], n_results=5) 
context = "\n\n".join(f"[{chunk_id}]\n{text}" for chunk_id, text in zip(matches["ids"][0], matches["documents"][0]))
response = chat(
    model="qwen3:8b",
    messages=[{
        "role": "user",
        "content": f"Answer the question using only the provided text and cite your answer with the chunk IDs. \n\nQuestion: {question}\n\n{context}", 
        
    }],
)

print(response.message.content)
