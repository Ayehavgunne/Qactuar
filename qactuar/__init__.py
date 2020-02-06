from qactuar.server import QactuarServer


def make_server(host, port, application):
    qactuar_server = QactuarServer((host, port))
    qactuar_server.set_app(application)
    return qactuar_server


def run(host, port, application):
    qactuar_server = make_server(host, port, application)
    qactuar_server.serve_forever()
