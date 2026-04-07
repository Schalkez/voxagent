# VoxAgent Architecture Diagram

VoxAgent is designed around a strictly unidirectional tiered execution pipeline enforcing Solid principles, ensuring modularity and secure context separation.

## High-Level Pipeline

```mermaid
graph TD
    User([User Voice]) --> EARS(Ears `stt_provider`)
    EARS -->|Transcribed Text| BRAIN(Brain `Routing & Tiers`)
    
    subgraph BRAIN
        T0[Tier 0: Keyword Matching]
        T1[Tier 1: Local Ollama / 1-7B]
        T2[Tier 2: Groq / Deepseek / 8-32B]
        
        T0 -- "Fallback" --> T1
        T1 -- "Fallback" --> T2
    end
    
    BRAIN -->|Structured Intent| HANDS(Hands `Safety Evaluator`)
    
    subgraph PIPELINE BOUNDARIES
        HANDS -->|Requires Voice Confirm| EARS
        HANDS -->|Inject Vision Context| EYES(Eyes `Screen Interaction`)
    end
    
    HANDS -->|Tool Execution| SKILLS([Skill Registry])
    
    SKILLS -->|Execution Result| MOUTH(Mouth `tts_provider`)
    MOUTH --> SystemSpeaker([System Speaker])
```

## Core Modules

- **Agent (`app.py`)**: The `VoxAgentApp` coordinates module lifecycle, graceful shutdowns via SIGINT, and the global background `Autopilot` thread instance.
- **Brain (`brain.py`)**: Routes intents intelligently based on cost constraints and required capability. Uses a strict JSON tool schema and intercepts implicit vision intent routing to the **Eyes**.
- **SyncManager (`sync.py`)**: Handles non-blocking persistent JSON local and intra-network syncs. Safe multi-device operations driven asynchronously (`asyncio.to_thread`).
- **Hands (`hands.py`)**: Responsible for execution layer validation. It rejects potentially dangerous system-level activities without dual-validation from input sources.

## Security Constraints

The current iteration (v0.1.0) blocks system calls via:
1. `terminal.py` whitelist limits string chains. No `shell=True` configurations.
2. API interactions are bounded statically, enforcing rate-limits at a 10k cache lock. Timing-safe verifications block remote bypasses.
