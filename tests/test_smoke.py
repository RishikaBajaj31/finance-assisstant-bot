from app.main import app


def test_app_imports():
    assert app.title == "AI Financial Assistant"
