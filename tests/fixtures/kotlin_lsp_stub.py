"""Deterministic stdio LSP fixture; never used by the installed application."""
import json
import sys

config = json.loads(sys.argv[1])


def send(message):
    payload = json.dumps({"jsonrpc": "2.0", **message}).encode()
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode() + payload)
    sys.stdout.buffer.flush()


while True:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            sys.exit(0)
        if line == b"\r\n":
            break
        key, value = line.decode().split(":", 1)
        headers[key.lower()] = value.strip()
    message = json.loads(sys.stdin.buffer.read(int(headers["content-length"])))
    method = message.get("method")
    if method == "initialize":
        send({"id": "server-config", "method": "workspace/configuration", "params": {"items": [{"section": "kotlin"}]}})
        send({"id": message["id"], "result": {"capabilities": {"referencesProvider": config.get("supports_references", True)}}})
    elif method == "textDocument/references":
        if config.get("ignore_references"):
            continue
        if config.get("error"):
            send({"id": message["id"], "error": {"code": -32603, "message": "Index failed"}})
            continue
        if "expected_position" in config:
            assert message["params"]["position"] == config["expected_position"]
        if "locations" in config:
            locations = config["locations"]
        else:
            uri = message["params"]["textDocument"]["uri"]
            pos = message["params"]["position"]
            # Callee has a caller on line 2, beginning at column 15.
            locations = [{"uri": uri, "range": {"start": {"line": 1, "character": 15}, "end": {"line": 1, "character": 21}}}] if pos["line"] == 0 else []
        send({"id": message["id"], "result": locations})
