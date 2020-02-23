import json
import ssl
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Dict

from qactuar.exceptions import HTTPError
from qactuar.processes.base import BaseProcessHandler

if TYPE_CHECKING:
    from qactuar import QactuarServer

APPS_PATH = Path(__file__).parent.parent / "apps"  # type: ignore


class AdminProcess(BaseProcessHandler):
    def __init__(self, server: "QactuarServer", admin_socket: ssl.SSLSocket):
        super().__init__(server, admin_socket)

    def handle_request(self) -> None:
        route = self.request_data.path.replace("/", "", 1)
        method = getattr(self, route)
        method()

    def add_app(self) -> None:
        if self.request_data.method != "POST":
            raise HTTPError(405)
        if self.request_data.headers["content-type"] != "application/json":
            raise HTTPError(415)
        body: Dict[str, str] = json.loads(self.request_data.body.decode("utf-8"))
        if "version" in body:
            app_path = f"{body['version']}/{body['app_name']}"
        else:
            app_path = body["app_name"]
        subprocess.run(
            (
                "git",
                "clone",
                "--branch",
                body["branch_name"],
                "--single-branch",
                body["git_uri"],
                app_path,
            ),
            cwd=APPS_PATH,
            check=True,
        )


def make_admin(server: "QactuarServer", admin_socket: ssl.SSLSocket) -> None:
    admin = AdminProcess(server, admin_socket)
    admin.start()
