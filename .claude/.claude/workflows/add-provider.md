---
description: how to add a new model provider to VoxAgent
---

1. Determine which interfaces the provider implements from `providers/base.py`:
   - `LLMProvider` — for chat/reasoning
   - `STTProvider` — for speech-to-text
   - `TTSProvider` — for text-to-speech
   - `VisionProvider` — for image analysis

2. Create file in the correct subdirectory:
   - `providers/llm/my_provider.py`
   - `providers/stt/my_provider.py`
   - `providers/tts/my_provider.py`
   - `providers/vision/my_provider.py`

3. Implement ALL abstract methods from the interface:
```python
from providers.base import LLMProvider, ModelInfo

class MyProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def chat(self, messages, **kwargs) -> str:
        # Call your API here
        ...

    async def chat_with_tools(self, messages, tools, **kwargs):
        # Tool calling implementation
        ...

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(name=self.model, provider="my_provider")

    async def health_check(self) -> bool:
        # Check if API is reachable
        ...
```

4. Register in `providers/registry.py`:
```python
registry.register("my_provider", MyProvider)
```

5. Add config section in `config.yaml`:
```yaml
providers:
  my_provider:
    api_key: "..."  # Stored in OS keyring, not plaintext
```

6. API keys MUST be stored securely via `keyring`, never hardcoded in config.

7. Write tests:
```bash
python -m pytest tests/test_providers.py -v -k "my_provider"
```
