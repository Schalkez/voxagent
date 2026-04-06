# Configuration

VoxAgent stores its configuration at `~/.voxagent/config.yaml`.

## Full Config Reference

```yaml
routing:
  tier_1:
    provider: groq
    model: llama-3.1-8b-instant
  tier_2:
    provider: ollama
    model: qwen2.5:7b
  tier_3:
    provider: anthropic
    model: claude-sonnet-4-20250514

stt:
  provider: whisper_local    # whisper_local | openai_whisper
  model: base                # tiny | base | small | medium | large-v3
  language: vi

tts:
  provider: edge_tts
  voice: vi-female           # vi-female | vi-male | en-female | en-male
  speed: 1.0

wake_word:
  engine: openwakeword
  phrase: voxagent
  sensitivity: 0.7

security:
  confirm_dangerous_actions: true
  max_file_delete_without_confirm: 3

audio:
  sample_rate: 16000
  channels: 1
  vad_threshold: 0.5
```

## API Keys

API keys are stored securely in your OS credential manager (Windows Credential Locker / macOS Keychain / Linux SecretService). Use the setup wizard:

```bash
voxagent setup
```

Or manage via the dashboard at `/providers`.
