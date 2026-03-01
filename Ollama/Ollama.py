# Ollama.py
# Contains functions for communicating with Ollama
#

import ollama

def ai_response(user_input):
    # This is the "Persona" that ensures it doesn't give you generic code
    system_prompt = (
        "You are an F' (F Prime) v4.0 expert. "
        "Provide concise, valid FPP or C++ code. "
        "Prioritize flight-software best practices."
    )

    print(f"\n Thinking...\n{'-'*30}")

    # We use stream=True for that satisfying TUI feel
    stream = ollama.chat(
        model='qwen3:8b',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_input},
        ],
        stream=True,
    )

    for chunk in stream:
        print(chunk['message']['content'], end='', flush=True)
    print(f"\n{'-'*30}")

if __name__ == "__main__":
    while True:
        user_msg = input("\n[F' Project Prompt]: ")
        if user_msg.lower() in ['exit', 'q']:
            break
        ai_response(user_msg)