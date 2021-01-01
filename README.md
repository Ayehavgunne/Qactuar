# Qactuar <img src="https://raw.githubusercontent.com/Ayehavgunne/Qactuar/master/Qactuar.png" width="100" title="Qactuar Logo">

An ASGI compliant web server which started as a companion project to the
[Tonberry](https://github.com/Ayehavgunne/Tonberry) ASGI framework.

## Installing
Just do the usual.

```bash
$ pip install qactuar
```

## Concurrency Models

### 1. Async Only
One process handles all requests using coroutines. Right now this is the only model that Windows supports. With WSL
though you can run the other models just fine.

### 2. Simple Fork
Forks a new process per request. Within the fork all requests are handled with coroutines.

### 3. Prefork
Creates a pool of processes (by default limited to the number of cpu cores) that the main process will cycle through and
hand off requests to as they come in. Within the fork all requests are handled with coroutines.

## Usage
During the installation it creates a command line app.

### Command Line

```bash
$ qactuar module:app
```

If your module is in the python path then it will get imported and any ASGI compatible object in the module can be
called. If the apps are set up in the config (see Configuration section below) then you can just start up qactuar
without any arguments.

Command line options can be seen with `-h`

```bash
$ qactuar -h

positional arguments:
  str                   path to a module and variable of an initialised app seperated by a colon; example -> module:app

optional arguments:
  -h, --help            show this help message and exit
  --host str            Host to bind to (default: 127.0.0.1)
  -p int, --port int    Port to bind to (default: 8000)
  -s str, --server-type str
                        Option to set the server concurrency model to async_only, simple_fork or prefork (default: async_only)
  --select-sleep-time float
                        How long to wait in seconds between checking the socket for new connections (default: 0.025)
  -r float, --recv-timeout float
                        How long to wait in seconds for data from an open client connection (default: 0.001)
  --recv-bytes int      How many bytes to wait for from an open client connection (default: 65536)
  --process-pool-size int
                        PRE-FORK MODE ONLY - How many processes to start up. Recomended size is equal to the number of cpu cores (default: os.cpu_count())
  --request-timeout float
                        How long to wait in seconds for a request to be considrered timed-out (default: 5)
  --ssl-cert-path str   Path to a certification file for SSL (default: )
  --ssl-cert-key str    Path to a certification key file for SSL (default: )
  --ssl-ciphers str     String representing cipher suites to use in the SSLContext (default: EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH)
  -a str, --app-dir str
                        Path to the directory where the module with the app is located (default: .)
  -u bool, --use-uvloop bool
                        Try to use uvloop if it is available (default: True)
  -v, --version         show program's version number and exit
```

### Programmatically

```python
from tonberry import create_app, expose
from tonberry.content_types import TextPlain

import qactuar

class Root:
    @expose.get
    async def index(self) -> TextPlain:
        return "Hello, world!"


if __name__ == "__main__":
    app = create_app(Root)
    qactuar.run(app=app)
    # other keyword arguments for run() are host, port and conf
```

For an intuitive but powerful ASGI framework, check out [Tonberry](https://github.com/Ayehavgunne/Tonberry)!

## Configuration
File, command line and programatic based configurations are supported. For a config file just create an environment
variable `QACTUAR_CONFIG` and set the value to the absolute or relative path of a JSON file. This file can overwride
any of the default values listed here. Only the values you wish to override need to be provided.

- HOST: `str` = "127.0.0.1"
- PORT: `int` = 8000 
- SERVER_TYPE: `str` = "async_only" | "prefork" | "simple_fork"
- SELECT_SLEEP_TIME: `float` = 0.025
- RECV_TIMEOUT: `float` = 0.001
- RECV_BYTES: `int` = 65536
- PROCESS_POOL_SIZE: `int` = os.cpu_count()
- REQUEST_TIMEOUT: `float` = 5
- SSL_CERT_PATH: `str` = ""
- SSL_KEY_PATH: `str` = ""
- SSL_CIPHERS: `str` = "EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH"
- APP_DIR: `str` = "."
- USE_UVLOOP: `bool` = True
- APPS: `Dict[str, str]` = {}
- LOGS: `Dict[str, Any]` = *default_log_setup (see below)*

The `APPS` dictionary takes a `route` as the key and a `module:app` style string as the value. Multiple applications
can be hosted at the same time by registering each at its own route. A basic example can be seen in the
[qactuar_config.json](https://github.com/Ayehavgunne/Qactuar/blob/master/tests/qactuar_config.json) file.

### The Config dataclass
The config is managed in a dataclass object and can be created programmatically. All arguments are optional and are
defined above.

```python
config = qactuar.Config(HOST='0.0.0.0')
qactuar.run(app=app, conf=config)
```

The `LOGS` dictionary is for the logging.config setup as detailed in the 
[Python documentation](https://docs.python.org/3/library/logging.config.html). It uses logging.config.dictConfig to set
the logging configs. The loggers used throught the code are `qt_server` (used by the parent process), `qt_child` (used
in the child processes), `qt_access` (used to log each request), `qt_exception` (used to log any exceptions)

### Default Log Setup
```json
{
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
        "standard": {"format": "{asctime} {levelname} {message}", "style": "{"},
        "access": {
            "format": "{asctime} ACCESS {host}:{port} {request_id} {method} HTTP/{http_version} {path} {status} {message}",
            "style": "{"
        },
        "exception": {
            "format": "{asctime} {levelname} {request_id} {message}",
            "style": "{"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": "ext://sys.stdout"
        },
        "access": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "access",
            "stream": "ext://sys.stdout"
        },
        "exception": {
            "class": "logging.StreamHandler",
            "level": "ERROR",
            "formatter": "exception",
            "stream": "ext://sys.stderr"
        }
    },
    "loggers": {
        "qt_server": {"handlers": ["console"], "level": "DEBUG"},
        "qt_child": {"handlers": ["console"], "level": "DEBUG"},
        "qt_access": {"handlers": ["access"], "level": "INFO"},
        "qt_exception": {"handlers": ["exception"], "level": "ERROR"}
    }
}
```

If changing the `LOGS` config then the whole dictionary needs to be replaced. Individual parts of the log config cannot
be changed by themselves.

## Tornado Apps
Included is a utility wrapper to take a Tornado Request Handler and make it work with ASGI. See
[tornado_app.py](https://github.com/Ayehavgunne/Qactuar/blob/develop/tests/tornado_app.py) for an example.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull
requests.

## Versioning

[SemVer](http://semver.org/) is used for versioning. For the versions available, see the
[tags on this repository](https://github.com/Ayehavgunne/Qactuar/tags).

### Authors

* **Anthony Post** - [Ayehavgunne](https://github.com/Ayehavgunne)

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.

## TODO
- [UPD](https://channels.readthedocs.io/en/1.x/asgi/udp.html) support
- WebSockets
- Filter HTTP/2-3 pseudo headers
- Client streaming
- TESTS!!!
- Docs
