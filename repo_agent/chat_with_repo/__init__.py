# repo_agent/chat_with_repo/__init__.py

def main(*args, **kwargs):
    """Load the optional chat UI only when it is actually requested."""
    from .main import main as run

    return run(*args, **kwargs)
