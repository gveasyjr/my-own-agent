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
agent_loop("What is earliest movie playing in lakeville emagine theater 6/7/2026?")