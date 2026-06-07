from langchain_ollama import OllamaLLM
from ddgs import DDGS

llm = OllamaLLM(model="llama3.2", base_url="http://0.0.0.0:11434")

def search_web(query):
    print(f"\n🔍 Searching: {query}")
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=3))
    if not results:
        return "No results found."
    snippets = "\n\n".join([f"Source: {r['href']}\n{r['body']}" for r in results])
    print(f"\n📄 Raw results found: {len(results)}")
    return snippets

def write_file(filename, content):
    filepath = f"/Users/geoffreyveasy/MYSERVER/agent/data/{filename}"
    import os
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
    print(f"\n💾 Saved to: {filepath}")
    return filepath

def read_file(filename):
    filepath = f"/Users/geoffreyveasy/MYSERVER/agent/data/{filename}"
    try:
        with open(filepath, "r") as f:
            content = f.read()
        print(f"\n📖 Read from: {filepath}")
        return content
    except FileNotFoundError:
        return f"File not found: {filename}"

def get_weather(city):
    import requests
    print(f"\n🌤 Getting weather for: {city}")
    
    # First geocode the city to get coordinates
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
    geo = requests.get(geo_url).json()
    
    if not geo.get("results"):
        return f"Could not find city: {city}"
    
    lat = geo["results"][0]["latitude"]
    lon = geo["results"][0]["longitude"]
    name = geo["results"][0]["name"]
    
    # Then get the weather
    weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&temperature_unit=fahrenheit"
    weather = requests.get(weather_url).json()
    current = weather["current_weather"]
    
    result = f"Weather in {name}: {current['temperature']}°F, windspeed {current['windspeed']} km/h"
    print(f"\n🌡 {result}")
    return result

def needs_search(task):
    decision_prompt = f"""You are a decision-making assistant.
Decide if this question requires a live web search to answer accurately.

A web search IS needed if:
- The question involves recent news, current events, scores, prices, or anything after 2023
- The answer changes over time
- You are not confident you know the answer

A web search is NOT needed if:
- It's a timeless fact (history, science, math, definitions)
- You are fully confident in the answer

Question: {task}

Reply with only one word: SEARCH or ANSWER"""

    decision = llm.invoke(decision_prompt).strip().upper()
    print(f"\n🤔 Decision: {decision}")
    return "SEARCH" in decision

def agent_loop(task):
    print(f"\n🧠 Task received: {task}")

    if needs_search(task):
        search_results = search_web(task)
        context = f"""You are a helpful AI agent. Use ONLY these live web search results to answer.

SEARCH RESULTS:
{search_results}

QUESTION: {task}

Answer based strictly on the search results above:"""
    else:
        print(f"\n💡 Using training data — no search needed")
        context = f"Answer this question: {task}"

    thought = llm.invoke(context)
    print(f"\n💭 Agent answer:\n{thought}")
    print(f"\n✅ Done.")
    return thought

# Test both paths
print("=" * 50)
agent_loop("Who won the most recent NBA Finals and what was the score?")
print("=" * 50)
agent_loop("What is the capital of France?")

# Save the result to a file
write_file("nba_notes.txt", "San Antonio Spurs beat OKC 4-3 in the 2026 Western Conference Finals")
print(read_file("nba_notes.txt"))
agent_loop("What is earliest movie playing in lakeville emagine theater 6/7/2026?")
get_weather("Minneapolis")
get_weather("Lakeville, MN")
get_weather("Lakeville")