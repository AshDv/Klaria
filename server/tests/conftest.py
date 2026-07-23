import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["DATABASE_URL"] = f"sqlite:///{Path(tempfile.gettempdir()) / 'scribe_test.db'}"
os.environ["UPLOAD_DIR"] = str(Path(tempfile.gettempdir()) / "scribe_test_audio")
os.environ["SECRET_KEY"] = "test-secret-that-is-long-enough"
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["GOOGLE_CLIENT_SECRET"] = ""
os.environ["MISTRAL_API_KEY"] = ""
