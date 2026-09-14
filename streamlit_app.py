import streamlit as st
import requests


# -------------------------
# Page Configuration
# -------------------------

st.set_page_config(
    page_title="AYS Assistant",
    page_icon="🌀",
    layout="centered",
)


# -------------------------
# FastAPI URL
# -------------------------

API_URL = "http://127.0.0.1:8000/ask"
HEALTH_URL = "http://127.0.0.1:8000/"


# -------------------------
# Theme (dark, teal-accented)
# -------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

    :root {
        --bg: #0a0e13;
        --surface: #141c25;
        --surface-raised: #1a2530;
        --border: #253039;
        --text: #eef3f7;
        --text-muted: #8fa0ad;
        --accent: #2fe6cc;
        --accent-dim: #0f8a78;
        --accent-soft: rgba(47, 230, 204, 0.12);
        --warn: #f4a340;
    }

    html, body, [data-testid="stAppViewContainer"] {
        background-color: var(--bg);
        color: var(--text);
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stHeader"] {
        background-color: transparent;
    }

    .block-container {
        max-width: 720px;
        padding-top: 1.5rem;
        padding-bottom: 6rem;
    }

    h1, h2, h3, .brand-title {
        font-family: 'Space Grotesk', sans-serif;
    }

    /* ---------- Header ---------- */

    .hero {
        position: relative;
        border-radius: 16px;
        border: 1px solid var(--border);
        background:
            radial-gradient(120% 160% at 15% 0%, var(--accent-soft) 0%, transparent 55%),
            var(--surface);
        padding: 1.6rem 1.6rem 1.5rem 1.6rem;
        margin-bottom: 1.75rem;
        overflow: hidden;
    }

    .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .brand {
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .brand-mark {
        width: 42px;
        height: 42px;
        border-radius: 11px;
        background: linear-gradient(155deg, var(--accent) 0%, var(--accent-dim) 100%);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        box-shadow: 0 4px 18px rgba(47, 230, 204, 0.25);
    }

    .brand-text .brand-title {
        font-size: 1.3rem;
        font-weight: 700;
        line-height: 1.15;
        color: var(--text);
        letter-spacing: -0.01em;
    }

    .brand-text .brand-subtitle {
        font-size: 0.82rem;
        color: var(--text-muted);
        margin-top: 3px;
    }

    .status-pill {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.78rem;
        color: var(--text-muted);
        border: 1px solid var(--border);
        background: rgba(0, 0, 0, 0.2);
        border-radius: 999px;
        padding: 0.32rem 0.75rem;
        flex-shrink: 0;
    }

    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        flex-shrink: 0;
    }

    .status-dot.online { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
    .status-dot.offline { background: #55606b; }

    .hero-tagline {
        margin-top: 1.1rem;
        color: var(--text-muted);
        font-size: 0.92rem;
        line-height: 1.5;
        max-width: 52ch;
    }

    /* ---------- Example chip buttons ---------- */

    .chip-label {
        font-size: 0.78rem;
        color: var(--text-muted);
        margin: 0.2rem 0 0.6rem 0;
    }

    div[data-testid="stButton"] > button {
        background-color: var(--surface);
        border: 1px solid var(--border);
        color: var(--text);
        border-radius: 10px;
        padding: 0.6rem 0.95rem;
        font-size: 0.85rem;
        font-family: 'Inter', sans-serif;
        text-align: left;
        width: 100%;
        transition: border-color 0.15s ease, background-color 0.15s ease, transform 0.15s ease;
    }

    div[data-testid="stButton"] > button:hover {
        border-color: var(--accent);
        background-color: var(--surface-raised);
        color: var(--text);
        transform: translateY(-1px);
    }

    div[data-testid="stButton"] > button:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
    }

    /* ---------- Chat messages ---------- */

    [data-testid="stChatMessage"] {
        background-color: transparent;
        padding: 0.35rem 0;
        gap: 0.6rem;
    }

    [data-testid="stChatMessageContent"] {
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.9rem 1.05rem;
        font-size: 0.93rem;
        line-height: 1.6;
    }

    [data-testid="stChatMessageAvatarUser"] {
        background-color: var(--accent) !important;
        color: var(--bg) !important;
    }

    [data-testid="stChatMessageAvatarAssistant"] {
        background: linear-gradient(155deg, var(--accent-dim), #0a4a41) !important;
        color: var(--text) !important;
    }

    /* User turn: reverse the row so the bubble sits on the right,
       and give it the accent tint to read as "you" at a glance. */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {
        background-color: var(--accent-soft);
        border-color: var(--accent-dim);
    }

    /* ---------- Chat input ---------- */

    [data-testid="stChatInput"] {
        background-color: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
    }

    [data-testid="stChatInput"] textarea {
        color: var(--text) !important;
    }

    /* ---------- System / error notes ---------- */

    .system-note {
        border: 1px solid var(--warn);
        background-color: rgba(244, 163, 64, 0.1);
        color: var(--text);
        border-radius: 10px;
        padding: 0.75rem 0.95rem;
        font-size: 0.88rem;
        margin: 0.4rem 0 0.8rem 0;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# -------------------------
# Session State
# -------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None


# -------------------------
# API Health Check
# -------------------------

def check_api_online():
    try:
        r = requests.get(HEALTH_URL, timeout=3)
        return r.status_code == 200
    except requests.exceptions.RequestException:
        return False


api_online = check_api_online()


# -------------------------
# Hero / Header
# -------------------------

status_label = "Connected" if api_online else "Offline"
status_class = "online" if api_online else "offline"

st.markdown(
    f"""
    <div class="hero">
        <div class="app-header">
            <div class="brand">
                <div class="brand-mark">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                        <path d="M12 2C12 2 6 8.5 6 13.5C6 17.09 8.69 20 12 20C15.31 20 18 17.09 18 13.5C18 8.5 12 2 12 2Z"
                            stroke="#0a0e13" stroke-width="2" stroke-linejoin="round"/>
                    </svg>
                </div>
                <div class="brand-text">
                    <div class="brand-title">AYS Assistant</div>
                    <div class="brand-subtitle">Product Q&amp;A for aysonline.pk</div>
                </div>
            </div>
            <div class="status-pill">
                <span class="status-dot {status_class}"></span>
                {status_label}
            </div>
        </div>
        <div class="hero-tagline">
            Ask about prices, specs, or comparisons across the catalog —
            air conditioners, washing machines, refrigerators, and more.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# -------------------------
# Example chips (shown until the first message)
# -------------------------

EXAMPLE_QUESTIONS = [
    "What is the price of Kenwood KLU-18B03S?",
    "Show me 1.5 ton Gree air conditioners",
    "Compare Kenwood KLU-18B03S vs Gree 12AITH24S-T3",
    "Show me 8 kg front load washing machines",
]

if not st.session_state.messages:

    st.markdown('<div class="chip-label">Try asking</div>', unsafe_allow_html=True)

    cols = st.columns(2)
    for i, example in enumerate(EXAMPLE_QUESTIONS):
        with cols[i % 2]:
            if st.button(example, key=f"example_{i}", use_container_width=True):
                st.session_state.pending_question = example


# -------------------------
# Render chat history
# -------------------------

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])


# -------------------------
# Handle new input (typed or from an example chip)
# -------------------------

typed_question = st.chat_input("Ask about a product...")

question_to_process = st.session_state.pending_question or typed_question
st.session_state.pending_question = None

if question_to_process:

    st.session_state.messages.append(
        {"role": "user", "content": question_to_process}
    )

    with st.chat_message("user"):
        st.write(question_to_process)

    with st.chat_message("assistant"):

        with st.spinner("Looking that up..."):

            try:
                response = requests.post(
                    API_URL,
                    json={"question": question_to_process},
                    timeout=120,
                )

                if response.status_code == 200:
                    answer = response.json().get("answer", "")
                    st.write(answer)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": answer}
                    )

                else:
                    error_text = f"The assistant service returned an error (status {response.status_code}). Please try again."
                    st.markdown(f'<div class="system-note">{error_text}</div>', unsafe_allow_html=True)
                    st.session_state.messages.append(
                        {"role": "assistant", "content": error_text}
                    )

            except requests.exceptions.ConnectionError:
                error_text = "Can't reach the assistant service. Make sure the FastAPI backend is running, then try again."
                st.markdown(f'<div class="system-note">{error_text}</div>', unsafe_allow_html=True)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_text}
                )

            except requests.exceptions.Timeout:
                error_text = "That took too long to answer. Please try again."
                st.markdown(f'<div class="system-note">{error_text}</div>', unsafe_allow_html=True)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_text}
                )

            except Exception as e:
                error_text = f"Something went wrong: {e}"
                st.markdown(f'<div class="system-note">{error_text}</div>', unsafe_allow_html=True)
                st.session_state.messages.append(
                    {"role": "assistant", "content": error_text}
                )

    st.rerun()


# -------------------------
# Footer controls
# -------------------------

if st.session_state.messages:
    if st.button("Clear conversation", key="clear_chat"):
        st.session_state.messages = []
        st.rerun()