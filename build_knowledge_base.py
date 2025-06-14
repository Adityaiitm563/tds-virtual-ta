import os
import json
import sqlite3
import glob
import re
import asyncio
import aiohttp
import logging
from datetime import datetime
from dotenv import load_dotenv

# --- CONFIG ---
DB_PATH = "knowledge_base.db"
DISCOURSE_JSON = "discourse_posts.json"
MARKDOWN_DIR = "tds_pages_md"
METADATA_JSON = "metadata.json"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_URL = "https://aipipe.org/openai/v1/embeddings"
MAX_RETRIES = 3
CONCURRENT_REQUESTS = 4

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ENV ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise RuntimeError("API_KEY environment variable not set. Please set it in your .env file.")

# --- DB SCHEMA ---
SCHEMA = [
    '''CREATE TABLE IF NOT EXISTS discourse_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER,
        topic_id INTEGER,
        topic_title TEXT,
        post_number INTEGER,
        author TEXT,
        created_at TEXT,
        likes INTEGER,
        chunk_index INTEGER,
        content TEXT,
        url TEXT,
        embedding TEXT
    )''',
    '''CREATE TABLE IF NOT EXISTS markdown_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_title TEXT,
        original_url TEXT,
        downloaded_at TEXT,
        chunk_index INTEGER,
        content TEXT,
        embedding TEXT
    )'''
]

# --- UTILS ---
def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        if end == len(text):
            break
        start += chunk_size - overlap
    return chunks

async def get_embedding(session, text, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            headers = {
                "Authorization": API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "model": EMBEDDING_MODEL,
                "input": text
            }
            async with session.post(EMBEDDING_URL, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return json.dumps(data["data"][0]["embedding"])
                elif resp.status == 429:
                    logger.warning(f"Rate limited. Retrying in {2 ** attempt} seconds...")
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error(f"Embedding API error: {resp.status} {await resp.text()}")
                    await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Embedding request failed: {e}")
            await asyncio.sleep(2)
    raise RuntimeError("Failed to get embedding after retries.")

async def process_discourse(conn, session):
    if not os.path.exists(DISCOURSE_JSON):
        logger.warning(f"{DISCOURSE_JSON} not found. Skipping discourse.")
        return
    with open(DISCOURSE_JSON, "r", encoding="utf-8") as f:
        posts = json.load(f)
    logger.info(f"Processing {len(posts)} discourse posts...")
    to_insert = []
    for post in posts:
        chunks = chunk_text(post["content"])
        for idx, chunk in enumerate(chunks):
            to_insert.append((post, idx, chunk))
    logger.info(f"Total discourse chunks: {len(to_insert)}")
    for i in range(0, len(to_insert), CONCURRENT_REQUESTS):
        batch = to_insert[i:i+CONCURRENT_REQUESTS]
        tasks = [get_embedding(session, chunk) for _, _, chunk in batch]
        embeddings = await asyncio.gather(*tasks)
        for (post, idx, chunk), emb in zip(batch, embeddings):
            conn.execute('''
                INSERT INTO discourse_chunks (post_id, topic_id, topic_title, post_number, author, created_at, likes, chunk_index, content, url, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                post["post_id"], post["topic_id"], post.get("topic_title", ""), post["post_number"], post["author"],
                post["created_at"], post.get("like_count", 0), idx, chunk, post["url"], emb
            ))
        conn.commit()
        logger.info(f"Inserted {i+len(batch)}/{len(to_insert)} discourse chunks.")

async def process_markdown(conn, session):
    if not os.path.exists(METADATA_JSON):
        logger.warning(f"{METADATA_JSON} not found. Skipping markdown.")
        return
    with open(METADATA_JSON, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    logger.info(f"Processing {len(metadata)} markdown files...")
    to_insert = []
    for meta in metadata:
        md_path = os.path.join(MARKDOWN_DIR, meta["filename"])
        if not os.path.exists(md_path):
            continue
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Remove YAML front matter
        content = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL)
        chunks = chunk_text(content)
        for idx, chunk in enumerate(chunks):
            to_insert.append((meta, idx, chunk))
    logger.info(f"Total markdown chunks: {len(to_insert)}")
    for i in range(0, len(to_insert), CONCURRENT_REQUESTS):
        batch = to_insert[i:i+CONCURRENT_REQUESTS]
        tasks = [get_embedding(session, chunk) for _, _, chunk in batch]
        embeddings = await asyncio.gather(*tasks)
        for (meta, idx, chunk), emb in zip(batch, embeddings):
            conn.execute('''
                INSERT INTO markdown_chunks (doc_title, original_url, downloaded_at, chunk_index, content, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                meta["title"], meta["original_url"], meta["downloaded_at"], idx, chunk, emb
            ))
        conn.commit()
        logger.info(f"Inserted {i+len(batch)}/{len(to_insert)} markdown chunks.")

async def main():
    if os.path.exists(DB_PATH):
        logger.info(f"Removing existing {DB_PATH}")
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    for stmt in SCHEMA:
        conn.execute(stmt)
    async with aiohttp.ClientSession() as session:
        await process_discourse(conn, session)
        await process_markdown(conn, session)
    conn.close()
    logger.info("Knowledge base build complete.")

if __name__ == "__main__":
    asyncio.run(main()) 