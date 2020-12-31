import argparse
import sys
from importlib import import_module

import qactuar


class MyFormatter(
    argparse.ArgumentDefaultsHelpFormatter, argparse.MetavarTypeHelpFormatter
):
    pass


def main() -> None:
    default_config = qactuar.Config()
    parser = argparse.ArgumentParser(
        "Qactuar. An ASGI compliant web server",
        formatter_class=MyFormatter,
    )
    parser.add_argument(
        "app_path",
        type=str,
        help="path to a module and variable of an initialised app seperated by a "
        "colon; example -> module:app",
    )
    parser.add_argument(
        "--host",
        type=str,
        dest="HOST",
        default=default_config.HOST,
        help="Host to bind to",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        dest="PORT",
        default=default_config.PORT,
        help="Port to bind to",
    )
    parser.add_argument(
        "-s",
        "--server-type",
        type=str,
        dest="SERVER_TYPE",
        default=default_config.SERVER_TYPE,
        help="Option to set the server concurrency model to async_only, simple_fork or "
        "prefork",
    )
    parser.add_argument(
        "--select-sleep-time",
        type=float,
        dest="SELECT_SLEEP_TIME",
        default=default_config.SELECT_SLEEP_TIME,
        help="How long to wait in seconds between checking the socket for new "
        "connections",
    )
    parser.add_argument(
        "-r",
        "--recv-timeout",
        type=float,
        dest="RECV_TIMEOUT",
        default=default_config.RECV_TIMEOUT,
        help="How long to wait in seconds for data from an open client connection",
    )
    parser.add_argument(
        "--recv-bytes",
        type=int,
        dest="RECV_BYTES",
        default=default_config.RECV_BYTES,
        help="How many bytes to wait for from an open client connection",
    )
    parser.add_argument(
        "--process-pool-size",
        type=int,
        dest="PROCESS_POOL_SIZE",
        default=default_config.PROCESS_POOL_SIZE,
        help="PRE-FORK MODE ONLY - How many processes to start up. Recomended size is "
        "equal to the number of cpu cores; defaults to os.cpu_count()",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        dest="REQUEST_TIMEOUT",
        default=default_config.REQUEST_TIMEOUT,
        help="How long to wait in seconds for a request to be considrered timed-out",
    )
    parser.add_argument(
        "--ssl-cert-path",
        type=str,
        dest="SSL_CERT_PATH",
        default=default_config.SSL_CERT_PATH,
        help="Path to a certification file for SSL",
    )
    parser.add_argument(
        "--ssl-cert-key",
        type=str,
        dest="SSL_KEY_PATH",
        default=default_config.SSL_KEY_PATH,
        help="Path to a certification key file for SSL",
    )
    parser.add_argument(
        "--ssl-ciphers",
        type=str,
        dest="SSL_CIPHERS",
        default=default_config.SSL_CIPHERS,
        help="String representing cipher suites to use in the SSLContext",
    )
    parser.add_argument(
        "-a",
        "--app-dir",
        type=str,
        dest="APP_DIR",
        default=default_config.APP_DIR,
        help="Path to the directory where the module with the app is located",
    )
    parser.add_argument(
        "-u",
        "--use-uvloop",
        type=bool,
        dest="USE_UVLOOP",
        default=default_config.USE_UVLOOP,
        help="Try to use uvloop if it is available",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version="%(prog)s (" + qactuar.__version__ + ")",
    )

    if len(sys.argv) < 2:
        server = qactuar.make_server()
        server.serve_forever()
        sys.exit(0)

    args = parser.parse_args()
    app_path = args.app_path
    sys.path.insert(0, args.APP_DIR)
    args_dict = args.__dict__.copy()
    del args_dict["app_path"]
    config = qactuar.Config(**args_dict)
    module_str, app_str = app_path.split(":")
    module = import_module(module_str)
    app = getattr(module, app_str)
    server = qactuar.make_server(app=app, conf=config)
    server.serve_forever()


if __name__ == "__main__":
    main()
