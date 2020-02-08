import sys

import qactuar


def main():
    if len(sys.argv) < 2:
        qactuar.make_server()
        sys.exit(0)
    app_path = sys.argv[1]
    module, app = app_path.split(":")
    module = __import__(module)
    app = getattr(module, app)
    qactuar.make_server("127.0.0.1", 8000, app)


if __name__ == "__main__":
    main()
