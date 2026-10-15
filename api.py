
import os
import re
from functools import lru_cache
from typing import Optional

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="SmartNews Summarizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_BASE = "https://newsapi.org/v2"
NEWS_TIMEOUT = 20

VALID_COUNTRIES = {"in", "us", "gb"}
VALID_CATEGORIES = {
    "general",
    "business",
    "technology",
    "sports",
    "entertainment",
    "health",
    "science",
}

# India-specific queries used only when top headlines are unavailable.
INDIA_CATEGORY_QUERIES = {
    "general": (
        'India AND (government OR policy OR parliament OR '
        'state OR Indian)'
    ),
    "business": (
        'India AND (economy OR business OR finance OR market OR '
        'RBI OR startup)'
    ),
    "technology": (
        'India AND (technology OR artificial intelligence OR '
        'software OR startup OR digital)'
    ),
    "sports": (
        'India AND (cricket OR football OR badminton OR hockey OR '
        'Indian team OR tournament OR athlete)'
    ),
    "entertainment": (
        'India AND (Bollywood OR Indian cinema OR Indian film OR '
        'Indian actor OR Indian actress)'
    ),
    "health": (
        'India AND (healthcare OR hospital OR medical OR '
        'health ministry OR public health)'
    ),
    "science": (
        'India AND (ISRO OR Indian science OR Indian research OR '
        'space mission OR scientific discovery)'
    ),
}

CATEGORY_KEYWORDS = {
    "general": {
        "india", "indian", "government", "parliament", "policy",
        "minister", "court", "state", "election",
    },
    "business": {
        "business", "economy", "economic", "finance", "financial",
        "market", "markets", "bank", "banking", "rbi", "startup",
        "investment", "company", "companies", "trade",
    },
    "technology": {
        "technology", "tech", "software", "artificial intelligence",
        "ai", "digital", "cyber", "startup", "robotics",
        "smartphone", "semiconductor", "computer",
    },
    "sports": {
        "sports", "sport", "cricket", "football", "soccer",
        "hockey", "badminton", "tennis", "olympics", "olympic",
        "tournament", "athlete", "match", "team", "ipl",
        "world cup", "championship",
    },
    "entertainment": {
        "entertainment", "bollywood", "cinema", "film", "films",
        "movie", "movies", "actor", "actress", "celebrity",
        "singer", "music", "television",
    },
    "health": {
        "health", "healthcare", "hospital", "medical", "medicine",
        "doctor", "disease", "treatment", "patient", "health ministry",
    },
    "science": {
        "science", "scientific", "research", "researchers",
        "discovery", "space", "isro", "nasa", "satellite",
        "astronomy", "physics", "biology", "climate",
    },
}

# Common Indian locations and institutions help reject clearly unrelated
# international stories. This is a relevance heuristic, not a guarantee.
INDIA_TERMS = {
    "india", "indian", "delhi", "mumbai", "bengaluru", "bangalore",
    "chennai", "hyderabad", "kolkata", "pune", "ahmedabad",
    "karnataka", "kerala", "tamil nadu", "maharashtra",
    "uttar pradesh", "gujarat", "rajasthan", "goa", "odisha",
    "punjab", "haryana", "bihar", "assam", "jharkhand",
    "telangana", "andhra pradesh", "madhya pradesh",
    "uttarakhand", "himachal pradesh", "jammu and kashmir",
    "ladakh", "isro", "bcci", "rbi", "supreme court of india",
    "lok sabha", "rajya sabha", "narendra modi",
}

# Avoid returning articles whose titles clearly indicate another country.
FOREIGN_LOCATION_TERMS = {
    "united states", "u.s.", "us election", "washington dc",
    "white house", "donald trump", "united kingdom", "britain",
    "british parliament", "uk election", "canada", "canadian",
    "australia", "australian", "new zealand", "pakistan",
    "pakistani", "bangladesh", "bangladeshi", "sri lanka",
    "sri lankan", "nepal", "nepali", "china", "chinese",
    "japan", "japanese", "south korea", "north korea",
    "russia", "russian", "ukraine", "ukrainian",
    "israel", "israeli", "iran", "iranian",
}

class SummaryRequest(BaseModel):
    text: str
    detail: bool = False


def get_news_api_key():
    if not NEWS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail=(
                "NEWS_API_KEY is missing. Add it to your .env file "
                "and restart the API."
            ),
        )
    return NEWS_API_KEY


def news_request(endpoint: str, params: dict) -> dict:
    """Call NewsAPI and convert provider errors into useful messages."""
    params = dict(params)
    params["apiKey"] = get_news_api_key()

    try:
        response = requests.get(
            f"{NEWS_API_BASE}/{endpoint}",
            params=params,
            timeout=NEWS_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to NewsAPI: {exc}",
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="NewsAPI returned an invalid response.",
        ) from exc

    if not response.ok or data.get("status") == "error":
        message = data.get("message", "Unknown NewsAPI error")
        code = data.get("code", "newsapi_error")
        raise HTTPException(
            status_code=502,
            detail=f"NewsAPI error ({code}): {message}",
        )

    return data


def article_text(article: dict) -> str:
    """Combine the article fields used for relevance checking."""
    source = article.get("source") or {}

    return " ".join(
        str(value)
        for value in [
            article.get("title"),
            article.get("description"),
            article.get("content"),
            source.get("name"),
        ]
        if value
    ).lower()


def contains_any(text: str, terms: set[str]) -> bool:
    """Match whole words or multiword phrases."""
    for term in terms:
        pattern = r"(?<!\w)" + re.escape(term.lower()) + r"(?!\w)"
        if re.search(pattern, text):
            return True
    return False


def is_india_relevant(article: dict) -> bool:
    """
    Keep articles with evidence connecting them to India.
    Generic international stories without such evidence are rejected.
    """
    title = (article.get("title") or "").lower()
    combined = article_text(article)

    if contains_any(title, FOREIGN_LOCATION_TERMS):
        # Allow an explicitly India-related story even when another
        # country is mentioned in the headline.
        if not contains_any(combined, INDIA_TERMS):
            return False

    return contains_any(combined, INDIA_TERMS)


def is_category_relevant(article: dict, category: str) -> bool:
    """Keep articles with at least one keyword for the selected category."""
    if category == "general":
        return True

    combined = article_text(article)
    return contains_any(combined, CATEGORY_KEYWORDS[category])


def clean_articles(
    articles: list,
    country: str,
    category: str,
    limit: int,
) -> list:
    """Remove unusable, duplicate, off-topic, or irrelevant articles."""
    cleaned = []
    seen_urls = set()
    seen_titles = set()

    for article in articles:
        title = (article.get("title") or "").strip()
        url = (article.get("url") or "").strip()

        if not title or not url:
            continue

        if title.lower() == "[removed]":
            continue

        if url in seen_urls or title.lower() in seen_titles:
            continue

        if country == "in" and not is_india_relevant(article):
            continue

        if not is_category_relevant(article, category):
            continue

        seen_urls.add(url)
        seen_titles.add(title.lower())
        cleaned.append(article)

        if len(cleaned) >= limit:
            break

    return cleaned


@app.get("/")
def home():
    return {
        "message": "SmartNews Summarizer API is running.",
        "news_endpoint": "/news",
        "summarize_endpoint": "/summarize",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/news")
def get_news(
    country: str = Query(default="in"),
    category: str = Query(default="technology"),
    page_size: int = Query(default=20, ge=1, le=100),
):
    country = country.lower().strip()
    category = category.lower().strip()

    if country not in VALID_COUNTRIES:
        raise HTTPException(
            status_code=400,
            detail="Country must be in, us, or gb.",
        )

    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="Invalid news category.",
        )

    # First try the requested country and category.
    top_data = news_request(
        "top-headlines",
        {
            "country": country,
            "category": category,
            "pageSize": page_size,
            "page": 1,
        },
    )

    articles = clean_articles(
        top_data.get("articles", []),
        country,
        category,
        page_size,
    )

    fallback_used = False

    # India can return no usable headlines for some categories.
    # Search with category-specific keywords instead of generic "India".
    if country == "in" and len(articles) < page_size:
        fallback_used = True
        query = INDIA_CATEGORY_QUERIES[category]

        try:
            search_data = news_request(
                "everything",
                {
                    "q": query,
                    "searchIn": "title,description",
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 100,
                    "page": 1,
                },
            )

            fallback_articles = clean_articles(
                search_data.get("articles", []),
                country,
                category,
                page_size,
            )

            # Merge without duplicates; prefer the original headlines.
            existing_urls = {
                article.get("url") for article in articles
            }

            for article in fallback_articles:
                if article.get("url") not in existing_urls:
                    articles.append(article)
                    existing_urls.add(article.get("url"))

                if len(articles) >= page_size:
                    break

        except HTTPException as exc:
            # Preserve valid top-headline results if fallback search fails.
            print("India category fallback failed:", exc.detail)

    return {
        "status": "ok",
        "country": country,
        "category": category,
        "fallback_used": fallback_used,
        "totalResults": len(articles),
        "articles": articles,
        "message": (
            "Articles loaded."
            if articles
            else (
                f"No relevant {category} articles were found for "
                f"{country.upper()}. Try another category later."
            )
        ),
    }


@lru_cache(maxsize=1)
def load_summarizer():
    """Load the BART summarization model once and reuse it."""
    try:
        from transformers import pipeline

        return pipeline(
            "summarization",
            model="sshleifer/distilbart-cnn-12-6",
        )
    except Exception as exc:
        raise RuntimeError(
            "Could not load the summarization model. "
            "Check your transformers and torch installations. "
            f"Details: {exc}"
        ) from exc


@app.post("/summarize")
def summarize(request: SummaryRequest):
    text = (request.text or "").strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Please provide article text to summarize.",
        )

    if len(text) < 80:
        return {
            "summary": text,
            "message": "The article text is too short to summarize further.",
        }

    # DistilBART has a limited input size. Keep the input bounded.
    text = text[:12000]

    if request.detail:
        max_length = 150
        min_length = 45
    else:
        max_length = 90
        min_length = 25

    try:
        summarizer = load_summarizer()
        result = summarizer(
            text,
            max_length=max_length,
            min_length=min_length,
            do_sample=False,
            truncation=True,
        )
        summary = result[0]["summary_text"].strip()

        return {"summary": summary}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Summary generation failed: {exc}",
        ) from exc
