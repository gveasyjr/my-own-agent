import os
import pickle
import requests
import base64
from pathlib import Path
from langchain_ollama import OllamaLLM
from ddgs import DDGS
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import chromadb
from chromadb.utils import embedding_functions
import sqlite3


# ── Config ────────────────────────────────────────────
llm = OllamaLLM(model="qwen3", base_url="http://0.0.0.0:11434")
#llm = OllamaLLM(model="llama3.2", base_url="http://0.0.0.0:11434")
TOKEN_PATH = Path("/Users/geoffreyveasy/MYSERVER/agent/token.pickle")
DATA_PATH  = Path("/Users/geoffreyveasy/MYSERVER/agent/data")


# ── Short-term memory ─────────────────────────────────
conversation_history = []

def remember(role, content):
    conversation_history.append({"role": role, "content": content})

def get_history_as_text():
    if not conversation_history:
        return ""
    lines = [f"{m['role'].upper()}: {m['content']}" for m in conversation_history]
    return "\n".join(lines)

def clear_history():
    conversation_history.clear()
    print("🧹 Conversation history cleared.")


# ── Long-term memory (ChromaDB) ───────────────────────
chroma_client = chromadb.PersistentClient(
    path="/Users/geoffreyveasy/MYSERVER/agent/memory"
)
collection = chroma_client.get_or_create_collection(name="agent_memory")

def save_to_memory(content, metadata=None):
    import hashlib
    from datetime import datetime
    doc_id = hashlib.md5(content.encode()).hexdigest()
    collection.upsert(
        documents=[content],
        ids=[doc_id],
        metadatas=[metadata or {"saved_at": datetime.now().isoformat()}]
    )
    print(f"\n🧠 Saved to long-term memory: {content[:60]}...")

def search_memory(query, n_results=3):
    if collection.count() == 0:
        return ""
    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count())
    )
    if not results["documents"][0]:
        return ""
    memories = results["documents"][0]
    print(f"\n💾 Retrieved {len(memories)} memories")
    return "\n".join(memories)


# ── RAG (document search) ─────────────────────────────
docs_collection = chroma_client.get_or_create_collection(name="documents")

def search_docs(query, n_results=3):
    if docs_collection.count() == 0:
        return ""
    results = docs_collection.query(
        query_texts=[query],
        n_results=min(n_results, docs_collection.count())
    )
    if not results["documents"][0]:
        return ""
    docs = results["documents"][0]
    print(f"\n📚 Retrieved {len(docs)} document chunks")
    return "\n\n".join(docs)


# ── File-based memory (SQLite) ────────────────────────
DB_PATH = Path("/Users/geoffreyveasy/MYSERVER/agent/memory/facts.db")

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            content TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_fact(category, content):
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO facts (category, content, created_at) VALUES (?, ?, ?)",
        (category, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    print(f"\n🗄 Fact saved [{category}]: {content}")

def get_facts(category=None):
    conn = sqlite3.connect(DB_PATH)
    if category:
        rows = conn.execute(
            "SELECT category, content, created_at FROM facts WHERE category=? ORDER BY created_at DESC",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT category, content, created_at FROM facts ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    if not rows:
        return "No facts found."
    return "\n".join([f"[{r[0]}] {r[1]} ({r[2]})" for r in rows])


# ── Gmail creds ───────────────────────────────────────
def load_gmail_creds():
    if not TOKEN_PATH.exists():
        raise FileNotFoundError(f"Token not found at {TOKEN_PATH}. Run auth.py first.")
    with TOKEN_PATH.open("rb") as f:
        return pickle.load(f)


# ── Tools ─────────────────────────────────────────────
def search_web(query):
    print(f"\n🔍 Searching: {query}")
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
    if not results:
        return "No results found."
    print(f"\n📄 Raw results found: {len(results)}")
    return "\n\n".join([f"Source: {r['href']}\n{r['body']}" for r in results])

def write_file(filename, content):
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    filepath = DATA_PATH / filename
    filepath.write_text(content)
    print(f"\n💾 Saved to: {filepath}")
    return str(filepath)

def read_file(filename):
    filepath = DATA_PATH / filename
    if not filepath.exists():
        return f"File not found: {filename}"
    print(f"\n📖 Read from: {filepath}")
    return filepath.read_text()

def get_weather(city):
    print(f"\n🌤 Getting weather for: {city}")
    geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1").json()
    if not geo.get("results"):
        return f"Could not find city: {city}"
    lat  = geo["results"][0]["latitude"]
    lon  = geo["results"][0]["longitude"]
    name = geo["results"][0]["name"]
    weather = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current_weather=true&temperature_unit=fahrenheit"
    ).json()
    c = weather["current_weather"]
    result = f"Weather in {name}: {c['temperature']}°F, windspeed {c['windspeed']} km/h"
    print(f"\n🌡 {result}")
    return result

def check_email(max_results=5):
    print(f"\n📧 Checking email...")
    service = build('gmail', 'v1', credentials=load_gmail_creds())
    results = service.users().messages().list(
        userId='me', maxResults=max_results, labelIds=['INBOX']
    ).execute()
    messages = results.get('messages', [])
    if not messages:
        print("No messages found.")
        return []
    emails = []
    for msg in messages:
        txt = service.users().messages().get(
            userId='me', id=msg['id'], format='full'
        ).execute()
        headers = txt['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender  = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        emails.append({'id': msg['id'], 'from': sender, 'subject': subject})
        print(f"  📩 From: {sender} | Subject: {subject}")
    return emails

def send_email(to, subject, body):
    print(f"\n📤 Sending email to: {to}")
    service = build('gmail', 'v1', credentials=load_gmail_creds())
    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId='me', body={'raw': raw}).execute()
    print(f"✅ Email sent to {to}")

def get_calendar_events(max_results=5):
    from googleapiclient.discovery import build
    from datetime import datetime, timezone

    print(f"\n📅 Checking calendar...")
    service = build('calendar', 'v3', credentials=load_gmail_creds())

    now = datetime.now(timezone.utc).isoformat()

    events_result = service.events().list(
        calendarId='primary',
        timeMin=now,
        maxResults=max_results,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])

    if not events:
        print("No upcoming events found.")
        return "No upcoming events found."

    output = []
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'No title')
        output.append(f"📌 {summary} — {start}")
        print(f"  📌 {summary} — {start}")

    return "\n".join(output)


# ── Decision ─────────────────────────────────────────
def needs_search(task):
    prompt = f"""You are a decision-making assistant.
Decide if this question requires a live web search.

Reply SEARCH if:
- It involves recent news, events, scores, prices, or anything after 2023
- The answer changes over time

Reply ANSWER if:
- It is a timeless fact you are fully confident about

Question: {task}
Reply one word only: SEARCH or ANSWER"""
    decision = llm.invoke(prompt).strip().upper()
    print(f"\n🤔 Decision: {decision}")
    return "SEARCH" in decision


# ── Agent loop ────────────────────────────────────────
def agent_loop(task):
    print(f"\n🧠 Task received: {task}")
    remember("user", task)

    history = get_history_as_text()
    long_term = search_memory(task)
    doc_results = search_docs(task)

    if needs_search(task):
        results = search_web(task)
        context = f"""You are a helpful AI agent with memory.

LONG-TERM MEMORY:
{long_term}

PERSONAL DOCUMENTS:
{doc_results}

CONVERSATION HISTORY:
{history}

LIVE SEARCH RESULTS:
{results}

QUESTION: {task}

Answer based on all context above:"""
    else:
        print(f"\n💡 Using training data — no search needed")
        context = f"""You are a helpful AI agent with memory.

LONG-TERM MEMORY:
{long_term}

CONVERSATION HISTORY:
{history}

QUESTION: {task}

Answer the question using all context above:"""

    thought = llm.invoke(context)
    remember("assistant", thought)

    # Save important things to long-term memory
    save_to_memory(f"User said: {task}")
    save_to_memory(f"Agent answered: {thought}")

    print(f"\n💭 Agent answer:\n{thought}")
    print(f"\n✅ Done.")
    return thought


# ── Tests ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*50)
    print("TOOL TESTS")
    print("="*50)

    # Weather tool
    get_weather("Lakeville")

    # Email tools
    check_email()
    send_email("geoflveas96@gmail.com", "Agent test7", "Hello from your agent!")

    # Calendar tool
    get_calendar_events()

    # File read/write tool
    write_file("test_note.txt", "This is a test note from the agent.")
    print(read_file("test_note.txt"))

    print("\n" + "="*50)
    print("FILE-BASED MEMORY (SQLite)")
    print("="*50)

    # Save structured facts
    save_fact("user", "Name is Geoffrey")
    save_fact("user", "Lives in Lakeville Minnesota")
    save_fact("preference", "Prefers Fahrenheit for weather")

    # Read them back
    print("\nAll facts:")
    print(get_facts())
    print("\nUser facts only:")
    print(get_facts("user"))

    print("\n" + "="*50)
    print("SHORT-TERM MEMORY (conversation history)")
    print("="*50)

    clear_history()

    agent_loop("My name is John Doe and I live in Minneapolis Minnesota.")
    agent_loop("What is my name?")
    agent_loop("Where do I live?")
    agent_loop("What is the weather where I live?")

    print("\n" + "="*50)
    print("LONG-TERM MEMORY (ChromaDB)")
    print("="*50)

    save_to_memory("User's favorite color is blue", {"category": "preference"})
    save_to_memory("User has a dog named Max", {"category": "user"})

    clear_history()

    agent_loop("What is my favorite color?")
    agent_loop("What is my dog's name?")

    print("\n" + "="*50)
    print("RAG (personal document search)")
    print("="*50)

    clear_history()

    # These answers should come from about_me.txt not web search or training data
    agent_loop("Where does Geoffrey live according to his documents?")
    agent_loop("What is Geoffrey building?")
    agent_loop("What is Geoffrey's favorite programming language?")

    print("\n" + "="*50)
    print("SEARCH + MEMORY COMBINED")
    print("="*50)

    agent_loop("What is the capital of France?")
    agent_loop("Who won the 2026 NBA Western Conference Finals?")
