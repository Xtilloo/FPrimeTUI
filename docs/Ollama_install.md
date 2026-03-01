Date Created: 2026-03-01 01:43

## Overview

Ollama is an open source tool designed to run Large Language Models (LLMs) locally on your machine. Ollama prioritizes data privacy and offline functionality, and for our purposes, run LLM models without cost. This file will explain Ollama and the Ollama setup process.

## Setup

Follow these steps to ensure your environment is setup correctly:

### 1. Install the AI Engine (Ollama)

1. Download the audit-safe script:

	`curl -fsSL https://ollama.com/install.sh -o ollama_install.sh`

2. If you are safety-conscious, run `cat ollama_install.sh` to make sure the script is safe before executing it
3. Execute: 

	`sh ollama_install.sh`
    

### 2. Pull the model

We use `Qwen3:8b` for its reasoning capabilities and FPP syntax accuracy.

Run: 
```ollama pull qwen3:8b```

### 3. Python Integration

Inside your F' virtual environment:
`pip install ollama textual httpx`

### 4. Verification

Run the following to ensure the TUI can talk to the brain:
`python3 -c "import ollama; print(ollama.list())"`

### Configure

Once installed, follow the procedures below:

**Windows**; 