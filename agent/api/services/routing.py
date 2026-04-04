"""Routing business logic."""

from typing import Any

from api.state.store import routing_config_state


def get_routing_config() -> dict[str, Any]:
    """Retrieve the routing configuration from state."""
    return routing_config_state


def update_routing_config(preset: str, tiers: list[dict[str, Any]], status: str) -> None:
    """Update the routing configuration in state."""
    global routing_config_state
    routing_config_state.clear()
    routing_config_state.update(
        {
            "preset": preset,
            "tiers": tiers,
            "status": status,
        }
    )
