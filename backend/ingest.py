import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone

# --- Configurare ---
# Încărcăm cheile API din fișierul .env
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
INDEX_NAME = "land-advisor-kb" # Asigurați-vă că este același nume ca în contul Pinecone
KNOWLEDGE_BASE_DIR = "./knowledge_base"

def run_ingestion():
    """
    Citește documentele dintr-un folder, le procesează și le încarcă în Pinecone.
    """
    if not PINECONE_API_KEY or not PINECONE_ENVIRONMENT:
        print("Eroare: Cheile PINECONE_API_KEY și PINECONE_ENVIRONMENT trebuie setate în fișierul .env")
        return

    print("--- Începe procesul de încărcare a documentelor ---")

    # --- Pasul 1: Citirea documentelor din folder ---
    documents = []
    for filename in os.listdir(KNOWLEDGE_BASE_DIR):
        filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
        try:
            if filename.endswith(".pdf"):
                loader = PyPDFLoader(filepath)
                documents.extend(loader.load())
                print(f"✔️  Încărcat: {filename}")
            elif filename.endswith(".txt"):
                loader = TextLoader(filepath, encoding='utf-8')
                documents.extend(loader.load())
                print(f"✔️  Încărcat: {filename}")
        except Exception as e:
            print(f"❌ Eroare la încărcarea fișierului {filename}: {e}")

    if not documents:
        print("Niciun document valid găsit în folderul 'knowledge_base'. Procesul s-a oprit.")
        return

    # --- Pasul 2: Spargerea documentelor în bucăți mai mici (chunks) ---
    print("\n--- Se sparg documentele în bucăți (chunks)... ---")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    docs_chunks = text_splitter.split_documents(documents)
    print(f"Total bucăți de text create: {len(docs_chunks)}")

    # --- Pasul 3: Încărcarea în Pinecone ---
    # LangChain se va ocupa de crearea vectorilor (embeddings) și de încărcare.
    # Folosim modelul 'multilingual-e5-large' pe care l-ați selectat în Pinecone.
    print("\n--- Se încarcă datele în Pinecone... (Acest pas poate dura câteva minute) ---")
    try:
        PineconeVectorStore.from_documents(
            documents=docs_chunks,
            index_name=INDEX_NAME,
            embedding="multilingual-e5-large" # Specificăm modelul de embedding
        )
        print("\n✅ Procesul de încărcare a fost finalizat cu succes!")
        print("Puteți verifica în panoul Pinecone că 'RECORD COUNT' a crescut.")
    except Exception as e:
        print(f"\n❌ A apărut o eroare la încărcarea în Pinecone: {e}")

if __name__ == "__main__":
    run_ingestion()
