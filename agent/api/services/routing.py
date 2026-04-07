"""Routing business logic."""

from api.state.store import RoutingConfigState, TierEntry, routing_config_state, save_state


def get_routing_config() -> RoutingConfigState:
    """Retrieve the routing configuration from state."""
    return routing_config_state


def update_routing_config(preset: str, tiers: list[TierEntry], status: str) -> None:
    """Update the routing configuration in state and persist to disk."""
    routing_config_state.clear()
    routing_config_state.update(
        {
            "preset": preset,
            "tiers": tiers,
            "status": status,
        }
    )
    save_state()
