# API Reference

VoxAgent exposes a REST API at `http://localhost:8642` for the dashboard and automation.

## System

### GET /api/status
Returns system status, active skills, and provider info.

### POST /api/command
Execute a text command (server mode only).
```json
{"text": "mở chrome"}
```

## Providers

### GET /api/providers
List all registered providers with connection status.

### POST /api/providers/{id}/key
Save an API key: `{"api_key": "sk-..."}`.

### POST /api/providers/{id}/test
Test provider connectivity. Returns latency and status.

### GET /api/providers/{id}/usage
Get usage statistics for a provider.

## Routing

### GET /api/routing
Get current tier routing configuration.

### PUT /api/routing
Update routing preset and tier assignments.

## Skills

### GET /api/skills
List all registered skills with status.

### POST /api/skills/{id}/toggle
Enable or disable a skill.

## Settings

### GET /api/settings
Get current system settings.

### PUT /api/settings
Update system settings (STT, TTS, wake word, security).
