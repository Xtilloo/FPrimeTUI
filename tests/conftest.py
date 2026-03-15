
import pytest

from tests.test_helpers import MockAIClient


@pytest.fixture
def mock_ai_client():
    """
    Fixture to provide a mock AI client instance for testing.
    This instance is shared across a single test function.
    """
    return MockAIClient()

@pytest.fixture(autouse=True)
def patch_ai_client(monkeypatch, mock_ai_client):
    """
    Automatically replaces the FPrimeAIClient with our mock client in all tests.
    This prevents real Ollama API calls from being made. The app instantiates
    the client with `FPrimeAIClient()`, so we replace the class with a factory
    that returns our single mock instance.
    """
    monkeypatch.setattr("TUI.app.FPrimeAIClient", lambda **kwargs: mock_ai_client)
    monkeypatch.setattr("TUI.fprime_ai_client.FPrimeAIClient", lambda **kwargs: mock_ai_client)

@pytest.fixture
def temp_project(tmp_path):
    """Creates a dummy F' project structure for testing."""
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    venv_dir = project_dir / "fprime-venv"
    venv_dir.mkdir()
    (venv_dir / "bin").mkdir()
    (venv_dir / "bin" / "activate").touch()

    # Create a sub-component directory
    comp_dir = project_dir / "Components" / "MyComp"
    comp_dir.mkdir(parents=True)

    return project_dir
