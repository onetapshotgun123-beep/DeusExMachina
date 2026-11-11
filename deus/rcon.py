"""Minimal RCON client for driving the NeoForge dev server during the 1.1.0 show probe.

Used by probe_show.py so the harness can send commands and read scoreboard/weather state
without a console attached to the gradle run.
"""
import re
import socket
import struct


class RconError(RuntimeError):
    pass


class Rcon:
    def __init__(self, host="127.0.0.1", port=25575, password="deusprobe", timeout=15.0):
        self.sock = socket.create_connection((host, port), timeout)
        self.sock.settimeout(timeout)
        rid, _, _ = self._request(3, password)
        if rid == -1:
            raise RconError("rcon authentication failed")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def command(self, text):
        rid, _, body = self._request(2, text)
        if rid == -1:
            raise RconError("rcon command rejected: " + text)
        return body

    def _request(self, kind, body):
        payload = body.encode("utf-8")
        packet = struct.pack("<ii", 0, kind) + payload + b"\x00\x00"
        self.sock.sendall(struct.pack("<i", len(packet)) + packet)
        return self._recv()

    def _recv(self):
        head = self._exact(4)
        (length,) = struct.unpack("<i", head)
        data = self._exact(length)
        rid, kind = struct.unpack("<ii", data[:8])
        return rid, kind, data[8:-2].decode("utf-8", "replace")

    def _exact(self, n):
        chunks = []
        while n:
            chunk = self.sock.recv(n)
            if not chunk:
                raise RconError("rcon connection closed")
            chunks.append(chunk)
            n -= len(chunk)
        return b"".join(chunks)


def score(rcon, name):
    """Read a deusex objective score; returns None when the objective/score is absent."""
    out = rcon.command("scoreboard players get %s deusex" % name)
    if "Unknown scoreboard objective" in out or "Can't get value" in out:
        return None
    match = re.search(r"(-?\d+)\s*\[deusex\]", out)
    if not match:
        raise RconError("unparsed score output: " + out)
    return int(match.group(1))


def raining(rcon):
    """Weather probe: say is chat-only, so the predicate writes a bridge score instead."""
    rcon.command("scoreboard players set #rain deusex 0")
    rcon.command('execute if predicate {"condition":"minecraft:weather_check","raining":true} '
                 'run scoreboard players set #rain deusex 1')
    return score(rcon, "#rain") == 1
