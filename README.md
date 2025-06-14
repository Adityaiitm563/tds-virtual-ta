# TDS Virtual TA

A virtual Teaching Assistant for IITM's Tools in Data Science course. Answers student questions using course content and Discourse posts.

## Features
- Answers questions using semantic search and LLMs
- Uses course content and Discourse posts (Jan-Apr 2025)
- Accepts text questions and optional base64 images
- Returns answers with relevant links

## Setup

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd tds-project1
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up your API key
- Copy `.env.example` to `.env` and fill in your [aipipe.org](https://aipipe.org/) API key:
```
API_KEY=your_aipipe_api_key_here
```

## Data Preparation

### 1. Scrape Discourse posts
- Run:
```bash
python discourse_scraper_single.py
```
- Log in when prompted. This will create `discourse_posts.json`.

### 2. Scrape course content
- Run:
```bash
python course_content_scraper_full.py
```
- This will create markdown files in `tds_pages_md/` and `metadata.json`.

### 3. Build the knowledge base
- Run:
```bash
python build_knowledge_base.py
```
- This will create `knowledge_base.db` with all embeddings.

## Running the API

Start the FastAPI server:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

## API Usage

Send a POST request to `/api` with JSON:
```json
{
  "question": "Should I use gpt-4o-mini which AI proxy supports, or gpt3.5 turbo?"
}
```

Example using Python:
```python
import requests
url = "http://localhost:8000/api"
data = {"question": "Should I use gpt-4o-mini which AI proxy supports, or gpt3.5 turbo?"}
print(requests.post(url, json=data).json())
```

## Deployment
- Deploy on Vercel, Render, or any platform that supports FastAPI.
- Set your `API_KEY` in the environment variables.
- `vercel.json` is provided for Vercel deployment.

## Bonus: Discourse Scraping Script
- `discourse_scraper_single.py` allows scraping Discourse posts across a date range (login required).

## License
MIT License. See [LICENSE](LICENSE).

---
**Note:**
- `knowledge_base.db` is included for instant API testing. You can use it directly, or rebuild it from scratch using the provided scripts and instructions.
- Do NOT commit your real `.env` file or large raw data files. See `.gitignore` for details.