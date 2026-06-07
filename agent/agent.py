from langchain_ollama import OllamaLLM

llm = OllamaLLM(model="llama3.2", base_url="http://0.0.0.0:11434")

def agent_loop(task):
    print(f"\n🧠 Task received: {task}")
    
    # PERCEIVE — take in the task
    context = f"You are a helpful AI agent. Complete this task: {task}"
    
    # THINK — ask the LLM what to do
    thought = llm.invoke(context)
    print(f"\n💭 Agent thought:\n{thought}")
    
    # ACT — for now just return the thought
    result = thought
    
    # OBSERVE — report what happened
    print(f"\n✅ Done.")
    return result

# Test it
agent_loop("Sing a silly song")