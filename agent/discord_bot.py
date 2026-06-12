import os
import ssl
import certifi
import aiohttp
import asyncio
import discord
import requests
import pickle
from pathlib import Path
from langchain_ollama import OllamaLLM
from ddgs import DDGS
from googleapiclient.discovery import build


def load_env_file():
    env_path = Path(__file__).resolve().parent.parent / '.env'
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()

TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
if not TOKEN:
    raise RuntimeError("Set DISCORD_BOT_TOKEN in your environment before starting the bot.")

#llm = OllamaLLM(model="llama3.2", base_url="http://0.0.0.0:11434")
llm = OllamaLLM(model="qwen3", base_url="http://0.0.0.0:11434")

intents = discord.Intents.default()
intents.message_content = True


def get_token_path():
    return Path("/Users/geoffreyveasy/MYSERVER/agent/token.pickle")


def load_gmail_creds():
    token_path = get_token_path()
    if not token_path.exists():
        raise FileNotFoundError(f"Gmail token not found at {token_path}. Run auth.py first.")
    with token_path.open("rb") as f:
        return pickle.load(f)


def search_web(query):
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
    if not results:
        return "No results found."
    return "\n\n".join([f"Source: {r['href']}\n{r['body']}" for r in results])


def get_weather(city):
    geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1").json()
    if not geo.get("results"):
        return f"Could not find city: {city}"
    lat = geo["results"][0]["latitude"]
    lon = geo["results"][0]["longitude"]
    name = geo["results"][0]["name"]
    weather = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current_weather=true&temperature_unit=fahrenheit"
    ).json()
    c = weather["current_weather"]
    return f"Weather in {name}: {c['temperature']}°F, windspeed {c['windspeed']} km/h"


def check_email(max_results=5):
    creds = load_gmail_creds()
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().messages().list(
        userId='me', maxResults=max_results, labelIds=['INBOX']
    ).execute()
    messages = results.get('messages', [])
    if not messages:
        return "No messages found."
    emails = []
    for msg in messages:
        txt = service.users().messages().get(
            userId='me', id=msg['id'], format='full'
        ).execute()
        headers = txt['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        emails.append(f"From: {sender} | Subject: {subject}")
    return "\n".join(emails)


def needs_search(task):
    prompt = f"""Decide if this needs a live web search.
Reply SEARCH if it involves recent events after 2023.
Reply ANSWER if it is a timeless fact.
Question: {task}
Reply one word only:"""
    return "SEARCH" in llm.invoke(prompt).strip().upper()


def run_agent(task):
    if any(w in task.lower() for w in ["weather", "temperature", "forecast"]):
        city = task.split()[-1]
        return get_weather(city)
    if any(w in task.lower() for w in ["email", "inbox"]):
        return check_email()
    if needs_search(task):
        results = search_web(task)
        context = f"Use ONLY these search results to answer.\n\nRESULTS:\n{results}\n\nQUESTION: {task}\n\nAnswer:"
    else:
        context = f"Answer this question: {task}"
    return llm.invoke(context)


async def main():
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    bot = discord.Client(intents=intents, connector=connector)

    @bot.event
    async def on_ready():
        print(f"✅ Bot is online as {bot.user}")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        print(f"📨 {message.author}: {message.content}")
        async with message.channel.typing():
            response = await asyncio.get_event_loop().run_in_executor(
                None, run_agent, message.content
            )
        if len(response) > 2000:
            response = response[:1997] + "..."
        await message.channel.send(response)

    await bot.start(TOKEN)


asyncio.run(main())