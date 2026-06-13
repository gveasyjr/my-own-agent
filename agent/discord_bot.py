import os
import ssl
import certifi
import aiohttp
import asyncio
import discord
from pathlib import Path
from agent import agent_loop, get_weather, check_email, send_email, get_calendar_events, clear_history


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

intents = discord.Intents.default()
intents.message_content = True


def run_agent(message):
    if "weather" in message.lower():
        city = message.split()[-1]
        return get_weather(city)
    if any(w in message.lower() for w in ["email", "inbox"]):
        emails = check_email()
        if not emails:
            return "No emails found."
        return "\n".join([f"From: {e['from']} | Subject: {e['subject']}" for e in emails])
    if "calendar" in message.lower():
        return get_calendar_events()
    if message.lower() == "clear":
        clear_history()
        return "Conversation history cleared."
    return agent_loop(message)


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