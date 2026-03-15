# RAG Evaluation Notes — fprime_training.md

This document records RAG quality observations from testing the TUI against the training dataset in `FPrimeSampleProject/docs/fprime_training.md`.

**Methodology:** Each question from the training table is sent to the TUI in MISSION_CONTROL mode. The response is compared against the expected "Comprehensive Answer." IDs that produce off-target, missing, or misleading responses are recorded below.

---

## Problematic Prompts

| ID | Question | Issue | Notes |
| :--- | :--- | :--- | :--- |
