import sys

from qactuar import run

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Provide a ASGI application object as module:callable")
    app_path = sys.argv[1]
    module, app = app_path.split(":")
    module = __import__(module)
    app = getattr(module, app)
    run("127.0.0.1", 8000, app)
