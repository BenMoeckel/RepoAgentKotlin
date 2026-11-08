"""Small stdio LSP client for Kotlin semantic references.

The language server is an optional, separately installed executable. No shell is
used, and server diagnostics/logging never enter the JSON-RPC stream.
"""

import json
import queue
import shlex
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlparse


class KotlinLsp:
    def __init__(self, command, repo_path, timeout=120):
        self.command = shlex.split(command)
        self.root = Path(repo_path).resolve()
        self.timeout = timeout
        self.messages = queue.Queue()
        self.counter = 0
        self.process = None
        self.opened = set()

    def __enter__(self):
        try:
            self.process = subprocess.Popen(
                self.command,
                cwd=self.root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            threading.Thread(target=self._read, daemon=True).start()
            result = self.request(
                "initialize",
                {
                    "processId": None,
                    "rootUri": self.root.as_uri(),
                    "workspaceFolders": [
                        {"uri": self.root.as_uri(), "name": self.root.name}
                    ],
                    "capabilities": {
                        "general": {"positionEncodings": ["utf-16"]},
                        "workspace": {"configuration": True, "workspaceFolders": True},
                        "window": {"workDoneProgress": True},
                        "textDocument": {"references": {}},
                    },
                },
            )
            capabilities = result.get("capabilities", {})
            if not capabilities.get("referencesProvider"):
                raise RuntimeError(
                    "Kotlin LSP does not support textDocument/references"
                )
            if capabilities.get("positionEncoding", "utf-16") != "utf-16":
                raise RuntimeError("Kotlin LSP must support UTF-16 positions")
            self.notify("initialized", {})
            return self
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                headers = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        raise EOFError("Kotlin LSP exited")
                    if line in {b"\r\n", b"\n"}:
                        break
                    key, value = line.decode("ascii").split(":", 1)
                    headers[key.lower()] = value.strip()
                length = int(headers["content-length"])
                body = bytearray()
                while len(body) < length:
                    part = self.process.stdout.read(length - len(body))
                    if not part:
                        raise EOFError("Incomplete Kotlin LSP response")
                    body.extend(part)
                self.messages.put(json.loads(body))
        except Exception as exc:
            self.messages.put(exc)

    def _send(self, message):
        payload = json.dumps({"jsonrpc": "2.0", **message}).encode("utf-8")
        self.process.stdin.write(
            f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii") + payload
        )
        self.process.stdin.flush()

    def notify(self, method, params):
        self._send({"method": method, "params": params})

    def request(self, method, params):
        self.counter += 1
        request_id = self.counter
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                message = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty as exc:
                raise TimeoutError(f"Kotlin LSP timed out: {method}") from exc
            if isinstance(message, Exception):
                raise message
            if "method" in message:
                if "id" in message:
                    server_method = message["method"]
                    if server_method == "workspace/configuration":
                        result = [
                            None for _ in message.get("params", {}).get("items", [])
                        ]
                    elif server_method == "workspace/workspaceFolders":
                        result = [{"uri": self.root.as_uri(), "name": self.root.name}]
                    elif server_method in {
                        "window/workDoneProgress/create",
                        "client/registerCapability",
                        "client/unregisterCapability",
                    }:
                        result = None
                    else:
                        self._send(
                            {
                                "id": message["id"],
                                "error": {
                                    "code": -32601,
                                    "message": "Unsupported client request",
                                },
                            }
                        )
                        continue
                    self._send({"id": message["id"], "result": result})
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"Kotlin LSP {method}: {message['error']}")
                return message.get("result")

    def open_file(self, file_path):
        path = (self.root / file_path).resolve()
        if path not in self.opened:
            self.notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": path.as_uri(),
                        "languageId": "kotlin",
                        "version": 1,
                        "text": path.read_text(encoding="utf-8"),
                    }
                },
            )
            self.opened.add(path)

    def references(self, file_path, symbol, in_file_only=False):
        path = (self.root / file_path).resolve()
        self.open_file(file_path)
        line = symbol.get("name_line", symbol["code_start_line"]) - 1
        source_line = path.read_text(encoding="utf-8").splitlines()[line]
        column = len(source_line[: symbol["name_column"]].encode("utf-16-le")) // 2
        locations = (
            self.request(
                "textDocument/references",
                {
                    "textDocument": {"uri": path.as_uri()},
                    "position": {"line": line, "character": column},
                    "context": {"includeDeclaration": False},
                },
            )
            or []
        )
        references = []
        for location in locations:
            uri = urlparse(location["uri"])
            if uri.scheme != "file":
                continue
            target = Path(unquote(uri.path)).resolve()
            if not target.is_relative_to(self.root) or (
                in_file_only and target != path
            ):
                continue
            pos = location["range"]["start"]
            target_line = target.read_text(encoding="utf-8").splitlines()[pos["line"]]
            target_column = len(
                target_line.encode("utf-16-le")[: pos["character"] * 2].decode(
                    "utf-16-le"
                )
            )
            references.append(
                (
                    target.relative_to(self.root).as_posix(),
                    pos["line"] + 1,
                    target_column,
                )
            )
        return references

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            for stream in (self.process.stdin, self.process.stdout):
                if stream:
                    stream.close()

    def __exit__(self, *args):
        self.close()
