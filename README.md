# 📰 News Summarizer

An AI-powered web application that fetches the latest news articles and generates concise summaries using Artificial Intelligence and Natural Language Processing.

## Features

- Fetch news articles from different countries.
- Browse news by category.
- View article headlines, images, sources, and publication dates.
- Open the original news article.
- Generate AI summaries for individual articles.
- Summarize selected news articles.
- Interactive web interface using Streamlit.
- REST API backend using FastAPI.

## Technologies Used

- Python
- Streamlit
- FastAPI
- NewsAPI
- Hugging Face Transformers
- DistilBART
- PyTorch

## Project Structure

- `app.py` — Streamlit frontend.
- `api.py` — FastAPI backend and summarization logic.
- `requirements.txt` — Required Python packages.
- `.env.example` — Example environment variables.
- `.gitignore` — Files excluded from Git.

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/sonalisantosh2002-sudo/news-summarizer.git
cd news-summarizer
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the API Key

Create a `.env` file in the project folder using `.env.example` as a template.

Add your own NewsAPI key:

```env
NEWS_API_KEY=your_actual_newsapi_key
API_BASE=http://127.0.0.1:8000
```

Keep your `.env` file private. Never upload your API key to GitHub.

## Running the Application

### Start the FastAPI Backend

Open a terminal and run:

```bash
python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

### Start the Streamlit Frontend

Open another terminal in the project folder and run:

```bash
python -m streamlit run app.py
```

Open the local URL displayed in the terminal to use the application.

## Purpose

The project demonstrates how AI-powered text summarization can help users understand news articles quickly and efficiently.

## Author

Sonali Naik