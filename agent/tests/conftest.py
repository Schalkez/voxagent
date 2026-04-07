import pytest
from unittest.mock import MagicMock
import sys

@pytest.fixture(autouse=True, scope="session")
def mock_keyring():
    """Globally mock keyring to prevent NoKeyringError in CI environments."""
    mock = MagicMock()
    # Mock common methods used in the app
    mock.get_password.return_value = "mock-api-key"
    mock.set_password.return_value = None
    mock.delete_password.return_value = None
    
    # Patch the module in sys.modules so imports find our mock
    sys.modules["keyring"] = mock
    return mock
