Qactuar
-------

An ASGI compliant web server the goal of which is to support multiple strategies
for asynchronicity.

#### 1. Post-Fork Multiprocessing
The first strategy is a post-fork model creating a new process for every 
request. This is where I have started and it is mostly working.

#### 2. Async/Await
The second strategy is one that a lot of current ASGI servers already do. In a
single process just handle requests using asyncio/uvloop.

#### 3. Pre-Fork Multiprocessing with Async/Await
Start up a pool of processes which can share a socket and each take a set number
of requests and then handle them internally with async.

### Installing
Just do the usual
```bash
pip install qactuar
```

### Usage
It installs as a command line app. You can start it up like so
```bash
qactuar module:app
```
If your module is in the python path then it will get imported and any ASGI
compatible object in the module can be called.

Alternatively, there is a config file that can be set up. Just create an
environment variable `QACTUAR_CONFIG` and set the value to the absolute path of
a JSON file. This file can overwride any of the default values listed here.

- `HOST: str = "localhost"`
- `PORT: int = 8000`
- `ADMIN_HOST: str = "localhost"`
- `ADMIN_PORT: int = 8520`
- `LOG_LEVEL: str = "DEBUG"`
- `CHECK_PROCESS_INTERVAL: int = 1`
- `SELECT_SLEEP_TIME: float = 0.025`
- `RECV_TIMEOUT: float = 0.001`
- `RECV_BYTES: int = 65536`
- `MAX_PROCESSES: int = 500`
- `APPS: Dict[str, str] = {}`

The `APPS` dictionary takes a `route` as the key and a `module:app` style string
as the value.
