# tests/conftest.py
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

# Mock the heavy imports before importing your main module
import sys
sys.modules['whisper'] = MagicMock()
sys.modules['huggingface_hub'] = MagicMock()
sys.modules['Neeko.embd_roles'] = MagicMock()
sys.modules['Neeko.infer'] = MagicMock()

# Now import your app
sys.path.append(
    os.path.dirname( # AIPersonas
        os.path.dirname( # AIPersonas\tests
            os.path.dirname( # AIPersonas\tests\backend
                os.path.dirname( # AIPersonas\tests\backend\backend_tests
                    os.path.abspath(  # AIPersonas\tests\backend\test_integration.py
                        __file__ 
                    )
                )
            )
        )
    )
)

from main import app

@pytest.fixture(scope="session")
def client():
    """Create a test client"""
    return TestClient(app)

@pytest.fixture
def mock_user():
    """Mock user for authentication"""
    mock_user = Mock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    return mock_user

@pytest.fixture
def override_auth(mock_user):
    """Override the auth dependency"""
    from users import current_active_user
    app.dependency_overrides[current_active_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.clear()

@pytest.fixture
def temp_personas_dir():
    """Create temporary personas directory with test images"""
    with tempfile.TemporaryDirectory() as temp_dir:
        personas_dir = Path(temp_dir) / "personas"
        personas_dir.mkdir()
        
        # Create test images
        (personas_dir / "test_image.png").write_bytes(b"fake png content")
        (personas_dir / "another_image.png").write_bytes(b"another fake png")
        
        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        
        yield personas_dir
        
        os.chdir(original_cwd)

# Mock global variables that might cause issues
@pytest.fixture(autouse=True)
def mock_global_models():
    """Mock the global model variables"""
    import backend.main as main_module
    main_module.whisper_model = Mock()
    main_module.neeko_model = Mock()
    main_module.neeko_tokenizer = Mock()