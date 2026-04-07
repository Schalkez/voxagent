# API Reference

VoxAgent exposes a REST API at `http://localhost:8642` for the dashboard and automation.

## Authentication

Endpoints marked with **Auth** require the `X-VoxAgent-Key` header.

- The expected key is read from the `VOXAGENT_API_KEY` environment variable.
- When `VOXAGENT_API_KEY` is **not set**, authentication is disabled and all requests are allowed through.
- When it **is set**, every authenticated endpoint validates the header and returns `401 Unauthorized` on mismatch.

```
X-VoxAgent-Key: your-secret-key-here
```

## Rate Limiting

Authenticated and command-execution endpoints enforce rate limiting.

| Limit | Value |
|-------|-------|
| Requests per minute per IP | 60 |
| Response on exceeded limit | `429 Too Many Requests` |

When the limit is exceeded the response body is:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Try again in 42 seconds.",
  "retry_after_seconds": 42
}
```

## HTTP Status Codes

Every endpoint may return the following status codes:

| Code | Meaning |
|------|---------|
| `200 OK` | Request succeeded. |
| `400 Bad Request` | Invalid or missing request body / parameters. |
| `401 Unauthorized` | Missing or invalid `X-VoxAgent-Key` header (auth-protected endpoints only). |
| `404 Not Found` | Resource (provider, skill, route) does not exist. |
| `429 Too Many Requests` | Rate limit exceeded. |

---

## System

### GET /api/status

Returns system status including uptime, active skills, provider info, and voice pipeline state.

**Auth:** No | **Rate Limited:** No

**Response `200`:**

```json
{
  "status": "running",
  "uptime_seconds": 3742,
  "voice_pipeline": {
    "wake_word": "hey_vox",
    "stt_provider": "whisper_local",
    "tts_provider": "edge_tts"
  },
  "active_skills": 8,
  "active_providers": 3
}
```

---

### POST /api/command

Execute a text command in server mode. The command is routed through the intent classifier and executed by the matching skill.

**Auth:** Yes | **Rate Limited:** Yes

**Request body:**

```json
{
  "text": "open chrome"
}
```

**Response `200`:**

```json
{
  "success": true,
  "skill": "app_launcher",
  "action": "open",
  "tts_response": "Chrome has been opened.",
  "tier_used": "NATIVE_API",
  "execution_ms": 120
}
```

**Response `400`:**

```json
{
  "error": "invalid_request",
  "message": "Field 'text' is required and must be a non-empty string."
}
```

**Response `401`:**

```json
{
  "error": "unauthorized",
  "message": "Missing or invalid X-VoxAgent-Key header."
}
```

---

### GET /api/server/health

Lightweight health check for monitoring and load balancers.

**Auth:** No | **Rate Limited:** No

**Response `200`:**

```json
{
  "healthy": true,
  "version": "0.3.0",
  "timestamp": "2026-04-07T12:00:00Z"
}
```

---

## Providers

### GET /api/providers

List all registered LLM / TTS / STT providers with their connection status.

**Auth:** No | **Rate Limited:** No

**Response `200`:**

```json
{
  "providers": [
    {
      "id": "openai",
      "name": "OpenAI",
      "type": "llm",
      "connected": true,
      "has_key": true
    },
    {
      "id": "edge_tts",
      "name": "Edge TTS",
      "type": "tts",
      "connected": true,
      "has_key": false
    }
  ]
}
```

---

### POST /api/providers/{id}/key

Save an API key for the specified provider. The key is stored in the OS keyring, **not** in configuration files.

**Auth:** Yes | **Rate Limited:** No

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Provider identifier (e.g. `openai`, `gemini`). |

**Request body:**

```json
{
  "api_key": "sk-..."
}
```

**Response `200`:**

```json
{
  "success": true,
  "message": "API key saved for provider 'openai'."
}
```

**Response `400`:**

```json
{
  "error": "invalid_request",
  "message": "Field 'api_key' is required."
}
```

**Response `404`:**

```json
{
  "error": "not_found",
  "message": "Provider 'unknown_provider' does not exist."
}
```

---

### POST /api/providers/{id}/test

Test connectivity for a provider. Returns latency and connection status.

**Auth:** Yes | **Rate Limited:** No

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Provider identifier. |

**Response `200`:**

```json
{
  "success": true,
  "provider": "openai",
  "latency_ms": 340,
  "model": "gpt-4o-mini",
  "message": "Connection successful."
}
```

**Response `404`:**

```json
{
  "error": "not_found",
  "message": "Provider 'unknown_provider' does not exist."
}
```

---

### GET /api/providers/{id}/usage

Get usage statistics for a specific provider (token counts, request history, estimated cost).

**Auth:** No | **Rate Limited:** No

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Provider identifier. |

**Response `200`:**

```json
{
  "provider": "openai",
  "total_requests": 1284,
  "total_tokens": 524000,
  "estimated_cost_usd": 1.57,
  "period": "current_session"
}
```

**Response `404`:**

```json
{
  "error": "not_found",
  "message": "Provider 'unknown_provider' does not exist."
}
```

---

## Routing

### GET /api/routing

Get the current tier routing configuration, including the active preset and per-tier provider assignments.

**Auth:** No | **Rate Limited:** No

**Response `200`:**

```json
{
  "preset": "balanced",
  "tiers": {
    "intent_classification": "gemini_flash",
    "quick_response": "gemini_flash",
    "complex_reasoning": "openai_gpt4o",
    "creative": "openai_gpt4o"
  }
}
```

---

### PUT /api/routing

Update the routing preset and tier assignments.

**Auth:** Yes | **Rate Limited:** No

**Request body:**

```json
{
  "preset": "performance",
  "tiers": {
    "intent_classification": "openai_gpt4o_mini",
    "quick_response": "openai_gpt4o_mini",
    "complex_reasoning": "openai_gpt4o",
    "creative": "openai_gpt4o"
  }
}
```

**Response `200`:**

```json
{
  "success": true,
  "message": "Routing configuration updated."
}
```

**Response `400`:**

```json
{
  "error": "invalid_request",
  "message": "Unknown preset 'turbo'. Valid presets: balanced, performance, economy."
}
```

---

## Skills

### GET /api/skills

List all registered skills with their enabled/disabled status, supported actions, and execution tiers.

**Auth:** No | **Rate Limited:** No

**Response `200`:**

```json
{
  "skills": [
    {
      "id": "media_control",
      "name": "Media Control",
      "enabled": true,
      "actions": ["play", "pause", "next", "volume"],
      "execution_tiers": ["NATIVE_API"],
      "permissions": ["media:control"]
    },
    {
      "id": "app_launcher",
      "name": "App Launcher",
      "enabled": true,
      "actions": ["open", "close", "list_running"],
      "execution_tiers": ["NATIVE_API", "SHELL"],
      "permissions": ["app:launch"]
    }
  ]
}
```

---

### POST /api/skills/{id}/toggle

Enable or disable a skill at runtime.

**Auth:** Yes | **Rate Limited:** No

**Path parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | string | Skill identifier (e.g. `media_control`). |

**Response `200`:**

```json
{
  "success": true,
  "skill": "media_control",
  "enabled": false,
  "message": "Skill 'media_control' has been disabled."
}
```

**Response `404`:**

```json
{
  "error": "not_found",
  "message": "Skill 'nonexistent_skill' does not exist."
}
```

---

## Settings

### GET /api/settings

Get current system settings including STT, TTS, wake word, and security configuration.

**Auth:** No | **Rate Limited:** No

**Response `200`:**

```json
{
  "wake_word": {
    "phrase": "hey_vox",
    "sensitivity": 0.5
  },
  "stt": {
    "provider": "whisper_local",
    "language": "en",
    "model_size": "base"
  },
  "tts": {
    "provider": "edge_tts",
    "voice": "en-US-AriaNeural",
    "speed": 1.0
  },
  "security": {
    "require_confirmation": ["file:delete", "terminal:write"],
    "api_auth_enabled": true
  }
}
```

---

### PUT /api/settings

Update system settings. Accepts a partial object; only provided fields are updated.

**Auth:** Yes | **Rate Limited:** No

**Request body (partial update):**

```json
{
  "tts": {
    "voice": "en-US-GuyNeural",
    "speed": 1.2
  }
}
```

**Response `200`:**

```json
{
  "success": true,
  "message": "Settings updated.",
  "updated_fields": ["tts.voice", "tts.speed"]
}
```

**Response `400`:**

```json
{
  "error": "invalid_request",
  "message": "Invalid value for 'tts.speed': must be between 0.5 and 2.0."
}
```
