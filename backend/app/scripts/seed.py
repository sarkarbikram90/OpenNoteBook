"""OpenNotebook — Demo Database and Vector Store Seeder.

Dynamically generates 3 PDF files using the fpdf2 library, uploads them to MinIO,
performs text chunking and indexing into Qdrant/PostgreSQL, inserts high-fidelity
summaries, and populates a demo conversation with inline citations.
"""

from __future__ import annotations

import logging
import os
import random
import sys
import uuid
from datetime import datetime, timezone

from bcrypt import hashpw, gensalt
from fpdf import FPDF
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.infrastructure.db.models import (
    Base, User, Notebook, Source, SourceSummary, ChatSession, Message, Settings
)
from app.infrastructure.minio.client import ensure_bucket, get_minio_client
from app.infrastructure.qdrant.client import get_qdrant_client
from app.domain.sources.bm25_index import build_bm25_index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Content Definitions for PDFs ─────────────────────────────────────────────

attention_text = """
Attention Is All You Need
The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.
We propose a new simple network architecture, the Transformer, based solely on attention mechanisms,
dispensing with recurrence and convolutions entirely.

Self-Attention
An attention function can be described as mapping a query and a set of key-value pairs to an output.
The output is computed as a weighted sum of the values, where the weight assigned to each value is
computed by a compatibility function of the query with the corresponding key.
We compute the matrix of outputs as: Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V.
Self-attention, sometimes called intra-attention, is an attention mechanism relating different
positions of a single sequence in order to compute a representation of the sequence. It has been
used successfully in a variety of tasks including reading comprehension, abstractive summarization,
textual entailment and learning task-independent sentence representations.
"""

deep_learning_text = """
Deep Learning Overview
Deep learning allows computational models that are composed of multiple processing layers to learn
representations of data with multiple levels of abstraction. These methods have dramatically improved
the state-of-the-art in speech recognition, visual object recognition, object detection and many other
domains such as drug discovery and genomics.

Multi-Layer Neural Networks
Deep learning discovers intricate structure in large data sets by using the backpropagation algorithm
to indicate how a machine should change its internal parameters that are used to compute the
representation in each layer from the representation in the previous layer.
Deep convolutional nets have brought about breakthroughs in processing images, video, speech and audio,
whereas recurrent nets have shone on sequential data such as text and speech.
"""

lorem_ipsum_text = """
Lorem Ipsum Research on Large Language Models
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore
et dolore magna aliqua. Large language models (LLMs) have demonstrated exceptional capabilities in
generating text that is coherent and contextually appropriate.

Generative Capabilities
Generative artificial intelligence refers to AI systems capable of generating text, images, or other
media in response to prompts. These models learn the patterns and structure of their input training
data and then generate new data that has similar characteristics.
Through training on massive corpora of text, these models develop a nuanced understanding of syntactic
and semantic structure, allowing them to perform translations, summarizations, and conversational tasks.
"""

# ── Dynamic PDF Generation Helper ─────────────────────────────────────────────

def generate_pdf(filename: str, title: str, content: str) -> str:
    """Create a standard PDF file using fpdf2 and return its path."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(10)
    
    pdf.set_font("Helvetica", size=12)
    # Split text by lines to print nicely
    for line in content.split("\n"):
        if line.strip():
            pdf.multi_cell(0, 8, line.strip())
            pdf.ln(2)
            
    # Save file temporarily
    temp_dir = "/tmp" if os.name != "nt" else "C:\\Temp"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, filename)
    pdf.output(file_path)
    logger.info("Generated PDF file locally: %s", file_path)
    return file_path

# ── Database Session Helper ───────────────────────────────────────────────

def get_db_session():
    settings = get_settings()
    # Convert asyncpg driver to standard sync pg driver
    sync_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

# ── Vector Generation Helper ──────────────────────────────────────────────────

def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Try to generate real BGE embeddings, otherwise fallback to mock random vectors."""
    try:
        from sentence_transformers import SentenceTransformer
        settings = get_settings()
        model = SentenceTransformer(settings.embedding_model)
        prefixed = [f"Represent this sentence: {t}" for t in texts]
        embeddings = model.encode(prefixed, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.warning("Could not use sentence-transformers for real embeddings: %s. Generating mock vectors.", e)
        # BGE small has 384 dimensions
        return [[random.uniform(-0.1, 0.1) for _ in range(384)] for _ in texts]

# ── Seeder Logic ─────────────────────────────────────────────────────────────

def seed_db() -> None:
    logger.info("Initializing seeder...")
    session = get_db_session()
    
    try:
        # 1. Create or retrieve Default User
        email = "demo@opennotebook.local"
        user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        
        if not user:
            hashed_pwd = hashpw("password123".encode("utf-8"), gensalt(12)).decode("utf-8")
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=hashed_pwd,
                is_active=True,
            )
            session.add(user)
            session.commit()
            logger.info("Created default demo user: %s", email)
            
            # Create user settings
            user_settings = Settings(
                id=uuid.uuid4(),
                user_id=user.id,
                llm_model="llama3:8b-instruct",
                embedding_model="BAAI/bge-small-en-v1.5",
                reranker_model="BAAI/bge-reranker-base",
                llm_temperature=0.1,
                context_window=8192,
                max_chunks=10,
            )
            session.add(user_settings)
            session.commit()
        else:
            logger.info("Demo user already exists.")

        # 2. Create Demo Notebook
        notebook = Notebook(
            id=uuid.uuid4(),
            user_id=user.id,
            name="AI Research Notebook",
            description="Default notebook populated with public domain papers and research notes.",
        )
        session.add(notebook)
        session.commit()
        logger.info("Created demo notebook: %s", notebook.name)

        # Ensure MinIO & Qdrant are available
        ensure_bucket()
        minio_client = get_minio_client()
        qdrant_client = get_qdrant_client()
        settings = get_settings()

        # 3. Create, Ingest, and Index 3 PDFs
        pdf_definitions = [
            ("attention_is_all_you_need.pdf", "Attention Is All You Need", attention_text),
            ("deep_learning_overview.pdf", "Deep Learning Overview", deep_learning_text),
            ("lorem_ipsum_research.pdf", "Lorem Ipsum Research on Large Language Models", lorem_ipsum_text),
        ]

        chunks_to_upsert = []
        
        for filename, title, raw_text in pdf_definitions:
            local_path = generate_pdf(filename, title, raw_text)
            
            # Upload to MinIO
            bucket_name = settings.minio_bucket
            object_name = f"sources/{notebook.id}/{filename}"
            
            minio_client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=local_path,
                content_type="application/pdf"
            )
            logger.info("Uploaded %s to MinIO", filename)
            
            # Create Source database record
            source = Source(
                id=uuid.uuid4(),
                notebook_id=notebook.id,
                name=filename,
                source_type="pdf",
                storage_path=object_name,
                status="READY",
                page_count=1,
                chunk_count=1,
                embedding_model=settings.embedding_model,
                metadata={"title": title, "author": "Research Community"},
            )
            session.add(source)
            session.commit()
            
            # Generate pre-composed source summary
            summary = SourceSummary(
                id=uuid.uuid4(),
                source_id=source.id,
                executive_summary=f"This paper covers fundamental mechanisms behind {title}, emphasizing modern deep learning advancements and architecture.",
                key_findings=[
                    "Replacing recurrent layers with multi-head attention mechanisms speeds up training.",
                    "Higher level abstractions represent intricate structures in complex datasets.",
                    "Evaluation shows impressive zero-shot capability on various benchmarks."
                ],
                entities={
                    "people": ["Vaswani et al.", "LeCun", "Bengio", "Hinton"],
                    "organisations": ["Google Research", "OpenAI", "Research Community"],
                    "concepts": ["Self-Attention", "Backpropagation", "Neural Networks", "LLMs"]
                },
                suggested_questions=[
                    f"What is the main contribution of the paper {filename}?",
                    "How does self-attention differ from standard RNNs?",
                    "What are the primary applications mentioned?"
                ]
            )
            session.add(summary)
            session.commit()
            logger.info("Saved summary for %s", filename)
            
            # Index chunk into Qdrant vector store
            text_snippet = raw_text.strip()
            vector = get_embeddings([text_snippet])[0]
            
            chunk_id = str(uuid.uuid4())
            chunks_to_upsert.append({
                "id": chunk_id,
                "vector": vector,
                "payload": {
                    "chunk_id": chunk_id,
                    "source_id": str(source.id),
                    "notebook_id": str(notebook.id),
                    "source_name": filename,
                    "text": text_snippet,
                    "token_count": len(text_snippet.split()),
                    "page": 1,
                    "section": "Main",
                    "embedding_model": settings.embedding_model,
                }
            })
            
            # Clean up local file
            if os.path.exists(local_path):
                os.remove(local_path)

        # Upsert all vectors in Qdrant
        from qdrant_client.models import PointStruct
        points = [
            PointStruct(
                id=c["id"],
                vector=c["vector"],
                payload=c["payload"]
            )
            for c in chunks_to_upsert
        ]
        
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection,
            points=points
        )
        logger.info("Upserted %d vector points in Qdrant", len(points))

        # 4. Build BM25 index for the notebook
        build_bm25_index(str(notebook.id))
        logger.info("Built BM25 index for notebook %s", notebook.id)

        # 5. Populate Demo Chat Session and Messages with citations
        session_chat = ChatSession(
            id=uuid.uuid4(),
            notebook_id=notebook.id,
            title="Understanding Attention Mechanisms",
        )
        session.add(session_chat)
        session.commit()

        # Add user message
        msg_user = Message(
            id=uuid.uuid4(),
            session_id=session_chat.id,
            role="user",
            content="Explain the core concept of self-attention in the Transformer model.",
        )
        session.add(msg_user)

        # Add assistant message with citation mapping
        citations = [
            {
                "chunk_id": chunks_to_upsert[0]["id"],
                "source_name": "attention_is_all_you_need.pdf",
                "source_id": chunks_to_upsert[0]["payload"]["source_id"],
                "page": 1,
                "section": "Self-Attention",
                "relevance_score": 0.9856
            }
        ]

        assistant_content = (
            "The core concept of self-attention in the Transformer model is to map a query and a set of "
            "key-value pairs to an output, computing a weighted sum of the values [Source 1]. This enables "
            "the model to learn dependencies across sequences regardless of their distance, replacing recurrent "
            "and convolutional structures entirely."
        )

        msg_assistant = Message(
            id=uuid.uuid4(),
            session_id=session_chat.id,
            role="assistant",
            content=assistant_content,
            citations=citations,
            retrieval_meta={
                "dense_latency_ms": 12.5,
                "bm25_latency_ms": 3.4,
                "fusion_latency_ms": 0.5,
                "rerank_latency_ms": 22.1,
                "retrieval_total_ms": 38.5,
                "model": "llama3:8b-instruct",
                "total_latency_ms": 420.0
            }
        )
        session.add(msg_assistant)
        session.commit()
        logger.info("Created default chat session with a grounded citation-rich message.")
        logger.info("Database and Vector Store seeding completed successfully!")

    except Exception as e:
        logger.error("Seeder execution failed: %s", e, exc_info=True)
        session.rollback()
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    seed_db()
