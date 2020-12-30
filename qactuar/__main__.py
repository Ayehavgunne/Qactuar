import sys
from importlib import import_module

import qactuar


def main() -> None:
    if len(sys.argv) < 2:
        server = qactuar.make_server()
        server.serve_forever()
        sys.exit(0)
    app_path = sys.argv[1]
    module_str, app_str = app_path.split(":")
    module = import_module(module_str)
    app = getattr(module, app_str)
    server = qactuar.make_server(app=app)
    server.serve_forever()


if __name__ == "__main__":
    main()
