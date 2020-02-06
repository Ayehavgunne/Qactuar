import sys

import qactuar

if __name__ == "__main__":
    if len(sys.argv) < 2:
        qactuar_server = qactuar.make_server()
        qactuar_server.serve_forever()
    app_path = sys.argv[1]
    module, app = app_path.split(":")
    module = __import__(module)
    app = getattr(module, app)
    qactuar.run("127.0.0.1", 8000, app)
