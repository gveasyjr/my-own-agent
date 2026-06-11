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


# ── Config ────────────────────────────────────────────
#llm = OllamaLLM(model="qwen3", base_url="http://0.0.0.0:11434")
llm = OllamaLLM(model="llama3.2", base_url="http://0.0.0.0:11434")
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

    if needs_search(task):
        results = search_web(task)
        context = f"""You are a helpful AI agent with memory.

LONG-TERM MEMORY:
{long_term}

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
    agent_loop("What is my name and where do I live?")
    agent_loop("What is the weather where I live?")
    get_weather("Lakeville")
    check_email()
    send_email("geoflveas96@gmail.com", "Agent test5", "Hello from your agent!")
    get_calendar_events()
    agent_loop("What is the capital of France?")
    agent_loop("Who won the 2026 NBA Western Conference Finals?")