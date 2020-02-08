from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.options import define, options
from tornado.web import Application, RequestHandler

define("port", default=8000, help="port to listen to")


class HelloWorld(RequestHandler):
    def get(self):
        self.write("Hello, WORLD!")


def main():
    app = Application([("/", HelloWorld)])
    http_server = HTTPServer(app)
    http_server.listen(options.port)
    print(f"Listening on http://localhost:{options.port}")
    IOLoop.current().start()


if __name__ == "__main__":
    main()
