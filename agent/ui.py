import gradio as gr
import sys
from pathlib import Path

# Import everything from agent.py
sys.path.insert(0, str(Path(__file__).parent))
from agent import agent_loop, get_weather, check_email, send_email, get_calendar_events, clear_history

def chat(message, history):
    # Handle special commands
    if message.lower().startswith("weather"):
        city = message.split()[-1]
        return get_weather(city)
    if message.lower() in ["check email", "check my email", "inbox"]:
        emails = check_email()
        if not emails:
            return "No emails found."
        return "\n".join([f"📩 From: {e['from']} | Subject: {e['subject']}" for e in emails])
    if message.lower() == "calendar":
        return get_calendar_events()
    if message.lower() == "clear":
        clear_history()
        return "🧹 Conversation history cleared."

    # Default: run through agent
    return agent_loop(message)

demo = gr.ChatInterface(
    fn=chat,
    title="My Personal AI Agent",
    description="Powered by Ollama + llama3.2/qwen3 | Running locally on my Mac",
    examples=[
        "What is the weather in Lakeville?",
        "Check my email",
        "Calendar",
        "What is the capital of France?",
        "Who won the 2026 NBA Western Conference Finals?"
    ],
)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
        prevent_thread_lock=False
    )