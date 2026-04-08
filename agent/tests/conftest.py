import sys
from unittest.mock import MagicMock

# ── TOP-LEVEL MOCK ───────────────────────────────────────────────────────────
# We MUST patch 'keyring' at the module level in conftest.py. 
# conftest.py is loaded by pytest before it imports any test modules.
# Since test modules often import our application server (which imports 
# providers that import keyring), a fixture-based mock would be too late.

mock_keyring_obj = MagicMock()
mock_keyring_obj.get_password.return_value = "mock-api-key"
mock_keyring_obj.set_password.return_value = None
mock_keyring_obj.delete_password.return_value = None

sys.modules["keyring"] = mock_keyring_obj


import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def mock_keyring_fixture():
    """Provides access to the global keyring mock if needed by individual tests."""
    return mock_keyring_obj
