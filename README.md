# Qactuar <img src="Qactuar.png" width="100" title="Qactuar">

An ASGI compliant web server the goal of which is to support multiple
asynchronous models. This started as a companion project to the
[Tonberry](https://github.com/Ayehavgunne/Tonberry) ASGI framework.

##### 1. Post-Fork Multiprocessing
The first strategy is a post-fork model creating a new process for every 
request. This is the only model available right now.

##### 2. Async/Await
The second strategy is one that a lot of current ASGI servers already do. In a
single process just handle requests using asyncio/uvloop.

##### 3. Pre-Fork Multiprocessing with Async/Await
Start up a pool of processes which can share a socket and each take a set number
of requests and then handle them internally with async.

## Installing
Just do the usual
```bash
$ pip install qactuar
```

## Usage
During the install it creates a command line app.

### Command Line
```bash
$ qactuar module:app
```
If your module is in the python path then it will get imported and any ASGI
compatible object in the module can be called. If the apps are setup in the
config (see Configuration section below) then you can just start up qactuar
without any arguments.
```bash
$ qactuar
```

### Programatically
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
For a nice ASGI framework, check out
[Tonberry](https://github.com/Ayehavgunne/Tonberry)!

## Configuration
File and programatic based configurations are supported. For a config file just
create an environment variable `QACTUAR_CONFIG` and set the value to the
absolute or relative path of a JSON file. This file can overwride any of the
default values listed here. Only the values you wish to override need to be
provided.

- HOST: `str` = "localhost"
- PORT: `int` = 8000
- ADMIN_HOST: `str` = "localhost"
- ADMIN_PORT: `int` = 1986
- CHECK_PROCESS_INTERVAL: `int` = 1
- SELECT_SLEEP_TIME: `float` = 0.025
- RECV_TIMEOUT: `float` = 0.001
- RECV_BYTES: `int` = 65536
- MAX_PROCESSES: `int` = 500
- GATHER_PROC_STATS: `bool` = False
- REQUEST_TIMEOUT: `float` = 5
- APPS: `Dict[str, str]` = {}
- LOGS: `Dict[str, Any]` = *default_log_setup (see below)*

The `APPS` dictionary takes a `route` as the key and a `module:app` style string
as the value. Multiple applications can be hosted at the same time by
registering each at its own route. A basic example can be seen in the
[qactuar_config.json](https://github.com/Ayehavgunne/Qactuar/blob/develop/tests/qactuar_config.json)
file.

### The Config dataclass
The config is managed in a dataclass object and can be created programmatically.
All arguments are optional and are defined above.
```python
config = qactuar.Config(HOST='0.0.0.0')
qactuar.run(app=app, conf=config)
```

The `LOGS` dictionary is for the logging.config setup as detailed in the Python
documentation [here](https://docs.python.org/3/library/logging.config.html). It
uses logging.config.dictConfig to set the logging configs. The loggers used
throught the code are `qt_server` (used by the parent process), `qt_child` (used
in the child processes), `qt_access` (used to log each request), `qt_exception`
(used to log any exceptions)

### Default Log Setup
```json
{
    "version": 1,
    "disable_existing_loggers": false,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {message}",
            "style": "{"
        },
        "access": {
            "format": "{asctime} ACCESS {message}",
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
            "formatter": "standard",
            "stream": "ext://sys.stderr"
        }
    },
    "loggers": {
        "qt_server": {
            "handlers": ["console"],
            "level": "DEBUG"
        },
        "qt_child": {
            "handlers": ["console"],
            "level": "DEBUG"
        },
        "qt_access": {
            "handlers": ["access"],
            "level": "INFO"
        },
        "qt_exception": {
            "handlers": ["exception"],
            "level": "ERROR"
        }
    }
}
```
If changing the `LOGS` config then the whole dictionary needs to be replaced.
Individual parts of the log config cannot be changed by themselves.

### Future Config Options

- ASYNCRONOUS_MODEL: `Enum` = 1

## Tornado Apps
Included is a utility wrapper to take a Tornado Request Handler and make it work
with ASGI. See
[tornado_app.py](https://github.com/Ayehavgunne/Qactuar/blob/develop/tests/tornado_app.py)
for an example.

## Admin
The plan is to support an extra socket connection that can accept connections
for adminitrative purposes. Maybe for viewing system recources, viewing the
processes and current load, changing configs on the fly, installing new apps
via git clone without restarting the server. This is still in the works.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of
conduct, and the process for submitting pull requests.

## Versioning

[SemVer](http://semver.org/) is used for versioning. For the versions available,
see the [tags on this repository](https://github.com/Ayehavgunne/Qactuar/tags).

### Authors

* **Anthony Post** - [Ayehavgunne](https://github.com/Ayehavgunne)

## License

This project is licensed under the MIT License - see the
[LICENSE.txt](LICENSE.txt) file for details

## TODO
- Admin socket
- [UPD](https://channels.readthedocs.io/en/1.x/asgi/udp.html) support
- WebSockets
- Send http.disconnect to app when each socket closes
- Filter HTTP/2-3 pseudo headers
- Client streaming, check "more_body" in send method
- Async only model
- Pre-Fork model
- TESTS!!!
- Docs
