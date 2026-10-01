"""Configuration for the RAG measurement system."""

# Chunking parameters
CHUNK_SIZE = 400  # words per chunk
CHUNK_OVERLAP = 50  # word overlap between chunks

# Retrieval parameters
K_TOP_RESULTS = 3  # number of chunks to retrieve
SIMILARITY_THRESHOLD = 0.0  # minimum similarity to include

# Embedding model (via Ollama)
EMBEDDING_MODEL = "nomic-embed-text"  # must be available in Ollama
OLLAMA_BASE_URL = "http://localhost:11434"

# Measurement parameters
NOISE_LEVELS = [10, 50, 100, 200]  # documents to add as noise
GOLD_SET_SIZE = 25  # test cases with known answers

# Storage paths
EMBEDDINGS_CACHE_PATH = "./embeddings/cache.json"
CORPUS_INDEX_PATH = "./embeddings/corpus_index.json"
RESULTS_CSV_PATH = "./measurements/results.csv"

# Logging
VERBOSE = True
DEBUG = False
