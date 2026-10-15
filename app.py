# SmartNews Summarizer - app.py

import html
import os
import random
from datetime import datetime

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="News Summarizer",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API_BASE = os.getenv(
    "API_BASE", "http://127.0.0.1:8000"
).rstrip("/")

COUNTRIES = {
    "India": "in",
    "USA": "us",
    "UK": "gb",
}

CATEGORIES = [
    "General",
    "Business",
    "Technology",
    "Sports",
    "Entertainment",
    "Health",
    "Science",
]


# -------------------- CSS DESIGN --------------------

st.markdown(
    """
    <style>
    :root {
        --navy: #17243b;
        --muted: #64748b;
        --red: #ff4b4b;
        --border: #e2e8f0;
    }

    .stApp {
        background: #f4f7fb;
        color: var(--navy);
    }

    /* Add top spacing so the entire banner is visible */
    .block-container {
        max-width: 1580px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    .hero {
        width: 100%;
        box-sizing: border-box;
        background: linear-gradient(
            120deg,
            #17243b 0%,
            #263e63 70%,
            #365b89 100%
        );
        border-radius: 18px;
        padding: 28px 30px;
        margin-top: 0;
        margin-bottom: 22px;
        box-shadow: 0 8px 24px rgba(23, 36, 59, 0.12);
    }

    .hero-title {
        color: white;
        font-size: clamp(1.7rem, 3vw, 2.5rem);
        font-weight: 800;
        letter-spacing: -0.6px;
        line-height: 1.2;
        margin: 0;
    }

    .news-source {
        display: inline-block;
        background: #edf2f8;
        color: #29405f;
        font-size: 0.72rem;
        font-weight: 750;
        border-radius: 6px;
        padding: 5px 8px;
        margin: 8px 0 5px 0;
    }

    .news-title {
        color: #17243b;
        font-size: 1rem;
        line-height: 1.45;
        font-weight: 750;
        margin: 6px 0 9px 0;
        overflow-wrap: anywhere;
    }

    .news-description {
        color: #526783;
        font-size: 0.88rem;
        line-height: 1.65;
        overflow-wrap: anywhere;
    }

    .news-date {
        color: #8290a4;
        font-size: 0.76rem;
        margin-top: 10px;
    }

    .small-note {
        color: #64748b;
        font-size: 0.82rem;
    }

    div.stButton > button,
    div.stLinkButton > a {
        border-radius: 10px;
        min-height: 40px;
        font-weight: 600;
    }

    div.stButton > button[kind="primary"] {
        background: #ff4b4b;
        border: 1px solid #ff4b4b;
        color: white;
    }

    div.stButton > button[kind="primary"]:hover {
        background: #e63e3e;
        border-color: #e63e3e;
        color: white;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 12px;
        box-shadow: 0 3px 12px rgba(23, 36, 59, 0.035);
    }

    [data-testid="stImage"] img {
        border-radius: 9px;
        object-fit: cover;
    }

    footer {
        visibility: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------- SESSION STATE --------------------

def initialize_state():
    defaults = {
        "articles": [],
        "summaries": {},
        "details": {},
        "selected_country": "India",
        "selected_category": "General",
        "loaded_query": None,
        "last_fetch_error": None,
        "initial_fetch_attempted": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


initialize_state()


# -------------------- FETCH NEWS --------------------

def fetch_articles(country_code: str, category: str):
    """Fetch news from FastAPI and randomize article order."""

    try:
        response = requests.get(
            f"{API_BASE}/news",
            params={
                "country": country_code,
                "category": category.lower(),
                "page_size": 20,
            },
            timeout=60,
        )

        response.raise_for_status()
        data = response.json()

        articles = data.get("articles", [])
        random.shuffle(articles)

        return articles, data.get("message", "")

    except requests.RequestException as exc:
        return [], (
            "Could not connect to the backend. "
            "Make sure api.py is running on port 8000. "
            f"Details: {exc}"
        )

    except (ValueError, TypeError):
        return [], "The backend returned an invalid response."


# -------------------- AI SUMMARIZATION --------------------

def summarize_article(article: dict, detailed: bool = False):
    """Send article text to the FastAPI summarization endpoint."""

    parts = [
        article.get("title") or "",
        article.get("description") or "",
        article.get("content") or "",
    ]

    text_to_summarize = " ".join(
        part.strip()
        for part in parts
        if part and part.strip()
    ).strip()

    if not text_to_summarize:
        return None, "This article does not contain enough text to summarize."

    try:
        response = requests.post(
            f"{API_BASE}/summarize",
            json={
                "text": text_to_summarize,
                "detail": detailed,
            },
            timeout=180,
        )

        response.raise_for_status()
        data = response.json()
        summary = data.get("summary")

        if not summary:
            return None, "The API did not return a summary."

        return summary, None

    except requests.RequestException as exc:
        return None, f"Could not generate the summary. Details: {exc}"

    except (ValueError, TypeError):
        return None, "The summarization API returned an invalid response."


# -------------------- HELPER FUNCTIONS --------------------

def clear_results_for_new_selection():
    """Clear old results when filters change."""

    st.session_state.articles = []
    st.session_state.summaries = {}
    st.session_state.details = {}
    st.session_state.loaded_query = None
    st.session_state.last_fetch_error = None

    st.session_state.selected_country = (
        st.session_state.country_picker
    )
    st.session_state.selected_category = (
        st.session_state.category_picker
    )


def safe_text(value):
    return html.escape(str(value or ""))


def format_date(value):
    if not value:
        return "Date unavailable"

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
        return parsed.strftime("%d %b %Y, %I:%M %p")

    except (ValueError, TypeError, AttributeError):
        return str(value)


def article_id(article, index):
    return article.get("url") or f"article-{index}"


def load_selected_news(show_spinner=True):
    """Load articles for the selected country and category."""

    country_name = st.session_state.country_picker
    category_name = st.session_state.category_picker
    country_code = COUNTRIES[country_name]

    if show_spinner:
        with st.spinner(
            f"Finding {category_name.lower()} news for {country_name}..."
        ):
            articles, message = fetch_articles(
                country_code,
                category_name.lower(),
            )
    else:
        articles, message = fetch_articles(
            country_code,
            category_name.lower(),
        )

    st.session_state.articles = articles
    st.session_state.summaries = {}
    st.session_state.details = {}

    st.session_state.selected_country = country_name
    st.session_state.selected_category = category_name

    st.session_state.loaded_query = (
        country_code,
        category_name.lower(),
    )

    st.session_state.last_fetch_error = (
        message if not articles else None
    )


# -------------------- HEADER --------------------

# Only the requested heading appears in the blue banner.
st.markdown(
    """
    <div class="hero">
        <p class="hero-title">📰 News Summarizer</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# -------------------- FILTERS --------------------

if "country_picker" not in st.session_state:
    st.session_state.country_picker = (
        st.session_state.selected_country
    )

if "category_picker" not in st.session_state:
    st.session_state.category_picker = (
        st.session_state.selected_category
    )

# No extra "Explore the headlines" heading or subtitle.

country_col, category_col, button_col = st.columns(
    [1.15, 1.45, 1]
)

with country_col:
    st.selectbox(
        "Country",
        options=list(COUNTRIES.keys()),
        key="country_picker",
        on_change=clear_results_for_new_selection,
    )

with category_col:
    st.selectbox(
        "News category",
        options=CATEGORIES,
        key="category_picker",
        on_change=clear_results_for_new_selection,
    )

with button_col:
    st.write("")
    st.write("")

    fetch_clicked = st.button(
        "🔄 Fetch Latest News",
        type="primary",
        use_container_width=True,
    )

st.markdown(
    f'<p class="small-note">AI engine: DistilBART &nbsp; • &nbsp; API: '
    f'<a href="{html.escape(API_BASE)}" target="_blank">'
    f'{html.escape(API_BASE)}</a></p>',
    unsafe_allow_html=True,
)


# -------------------- AUTOMATIC NEWS LOADING --------------------

# Automatically load news when the app first opens.
if not st.session_state.initial_fetch_attempted:
    st.session_state.initial_fetch_attempted = True
    load_selected_news(show_spinner=True)

# Fetch another selection when the button is clicked.
if fetch_clicked:
    load_selected_news(show_spinner=True)


# -------------------- DISPLAY NEWS --------------------

current_query = (
    COUNTRIES[st.session_state.country_picker],
    st.session_state.category_picker.lower(),
)

if st.session_state.loaded_query != current_query:

    st.info(
        "Your filter changed. Click Fetch Latest News to load "
        "articles for the selected country and category."
    )

elif st.session_state.last_fetch_error:

    st.error(st.session_state.last_fetch_error)

    if st.button("Try Again", type="primary"):
        load_selected_news(show_spinner=True)
        st.rerun()

elif not st.session_state.articles:

    st.warning(
        f"No relevant {st.session_state.category_picker.lower()} news "
        f"was found for {st.session_state.country_picker}. "
        "Try another category or fetch again."
    )

    if st.button("Fetch Again", type="primary"):
        load_selected_news(show_spinner=True)
        st.rerun()

else:

    articles = st.session_state.articles
    country_name = st.session_state.selected_country
    category_name = st.session_state.selected_category

    st.success(
        f"{len(articles)} articles loaded · "
        f"{country_name} · {category_name}"
    )

    toolbar_left, toolbar_right = st.columns([2, 1])

    with toolbar_left:
        detailed_summaries = st.toggle(
            "Generate longer, detailed summaries",
            value=False,
            help="Turn this on for longer summaries.",
        )

    with toolbar_right:
        st.markdown(
            f'<p style="text-align:right;color:#64748b;'
            f'padding-top:8px;">Showing {len(articles)} stories</p>',
            unsafe_allow_html=True,
        )

    st.divider()

    # Four news cards per row.
    for start in range(0, len(articles), 4):

        row_articles = articles[start:start + 4]
        columns = st.columns(4, gap="medium")

        for offset, article in enumerate(row_articles):

            index = start + offset
            key = article_id(article, index)

            title = article.get("title") or "Untitled article"

            description = (
                article.get("description")
                or "No description is available for this article."
            )

            source_data = article.get("source") or {}
            source_name = source_data.get("name") or "Unknown source"

            image_url = article.get("urlToImage")
            article_url = article.get("url")
            published = format_date(article.get("publishedAt"))

            with columns[offset]:

                with st.container(border=True):

                    if image_url:
                        try:
                            st.image(
                                image_url,
                                use_container_width=True,
                            )
                        except Exception:
                            st.markdown("📰 *Image unavailable*")
                    else:
                        st.markdown("📰 *No image available*")

                    st.markdown(
                        f'<span class="news-source">'
                        f'{safe_text(source_name)}</span>',
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f'<div class="news-title">'
                        f'{safe_text(title)}</div>',
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f'<div class="news-description">'
                        f'{safe_text(description)}</div>',
                        unsafe_allow_html=True,
                    )

                    st.markdown(
                        f'<div class="news-date">'
                        f'🕒 {safe_text(published)}</div>',
                        unsafe_allow_html=True,
                    )

                    if article_url:
                        st.link_button(
                            "Read Full Article ↗",
                            article_url,
                            use_container_width=True,
                        )

                    # Article details
                    if st.button(
                        "Article Details",
                        key=f"details-{key}",
                        use_container_width=True,
                    ):
                        st.session_state.details[key] = (
                            not st.session_state.details.get(key, False)
                        )

                    if st.session_state.details.get(key, False):

                        st.markdown("**Article Information**")
                        st.write(f"**Source:** {source_name}")
                        st.write(f"**Published:** {published}")

                        author = article.get("author")
                        if author:
                            st.write(f"**Author:** {author}")

                        content = article.get("content")
                        if content:
                            st.write(content)

                    # Individual AI summary
                    if st.button(
                        "✨ Summarize",
                        key=f"summarize-{key}",
                        type="primary",
                        use_container_width=True,
                    ):
                        with st.spinner("Generating AI summary..."):
                            summary, error = summarize_article(
                                article,
                                detailed=detailed_summaries,
                            )

                        if error:
                            st.error(error)
                        else:
                            st.session_state.summaries[key] = summary

                    if key in st.session_state.summaries:
                        st.markdown("**✨ AI Summary**")
                        st.write(st.session_state.summaries[key])


# -------------------- SUMMARIZE ALL ARTICLES --------------------

if st.session_state.articles:

    st.divider()
    st.markdown("### AI Summarization")
    st.caption(
        "Generate summaries for all currently loaded articles."
    )

    if st.button(
        "✨ Summarize All Loaded Articles",
        type="primary",
        use_container_width=True,
    ):

        progress = st.progress(0)
        status = st.empty()

        articles = st.session_state.articles
        total = len(articles)

        for index, article in enumerate(articles):

            key = article_id(article, index)

            if key not in st.session_state.summaries:

                status.write(
                    f"Summarizing article {index + 1} of {total}..."
                )

                summary, error = summarize_article(
                    article,
                    detailed=detailed_summaries,
                )

                if error:
                    st.warning(
                        f"Could not summarize "
                        f"{article.get('title', 'this article')}: {error}"
                    )
                else:
                    st.session_state.summaries[key] = summary

            progress.progress((index + 1) / total)

        status.success("All available summaries are ready.")
        st.rerun()


# -------------------- FOOTER --------------------

st.markdown("---")

st.markdown(
    """
    <div style="text-align:center;color:#8190a5;font-size:0.8rem;">
        News Summarizer · Powered by NewsAPI, FastAPI and DistilBART
    </div>
    """,
    unsafe_allow_html=True,
)
