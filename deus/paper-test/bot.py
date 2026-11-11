#!/usr/bin/env python3
"""Dev-only 1.21.11 protocol bot for headless plugin testing. Never shipped.

Packet IDs come from proto/packet_ids.json (extracted from the Mojang-mapped
server jar's protocol registration order). Handles login -> configuration ->
play, resource packs, keep-alives, teleports, auto-respawn, and logs chat /
titles / boss bar / health / sounds / particles so a show cycle can be
verified without a real client.
"""
import hashlib
import json
import socket
import struct
import sys
import time
import uuid
import zlib

HOST = "127.0.0.1"
PORT = 25566
NAME = sys.argv[1] if len(sys.argv) > 1 else "Bot"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def enc_varint(n):
    out = bytearray()
    n &= 0xFFFFFFFF
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def enc_utf(s):
    b = s.encode("utf-8")
    return enc_varint(len(b)) + b


class Reader:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def take(self, n):
        b = self.d[self.p:self.p + n]
        if len(b) != n:
            raise EOFError(f"need {n} have {len(b)}")
        self.p += n
        return b

    def varint(self):
        v = 0
        for i in range(5):
            b = self.take(1)[0]
            v |= (b & 0x7F) << (7 * i)
            if not b & 0x80:
                return v
        raise ValueError("varint too long")

    def utf(self):
        return self.take(self.varint()).decode("utf-8")

    def uuid(self):
        return uuid.UUID(bytes=self.take(16))

    def bool(self):
        return self.take(1)[0] != 0

    def byte(self):
        return self.take(1)[0]

    def int(self):
        return struct.unpack(">i", self.take(4))[0]

    def long(self):
        return struct.unpack(">q", self.take(8))[0]

    def float(self):
        return struct.unpack(">f", self.take(4))[0]

    def rest(self):
        return self.d[self.p:]


def nbt_text(data):
    """Walk an NBT component tree and collect strings in order (good enough for logs).
    NBT strings use a 2-byte big-endian length, NOT varints."""
    r = Reader(data)
    strings = []

    def nstr():
        n = struct.unpack(">H", r.take(2))[0]
        return r.take(n).decode("utf-8", "replace")

    def payload(t):
        if t == 1:
            r.take(1)
        elif t == 2:
            r.take(2)
        elif t == 3:
            r.take(4)
        elif t == 4:
            r.take(8)
        elif t == 5:
            r.take(4)
        elif t == 6:
            r.take(8)
        elif t == 7:
            r.take(r.int())
        elif t == 8:
            strings.append(nstr())
        elif t == 9:
            et = r.byte()
            n = r.int()
            for _ in range(n):
                payload(et)
        elif t == 10:
            while True:
                tt = r.byte()
                if tt == 0:
                    return
                nstr()  # name
                payload(tt)
        elif t == 11:
            r.take(4 * r.int())
        elif t == 12:
            r.take(8 * r.int())
        else:
            raise ValueError(f"nbt tag {t}")

    try:
        t = r.byte()
        if t != 0:
            payload(t)  # network NBT root is unnamed
    except Exception:
        pass
    return " ".join(s for s in strings if s.strip())


def offline_uuid(name):
    digest = hashlib.md5(("OfflinePlayer:" + name).encode("utf-8")).digest()
    return uuid.UUID(bytes=digest, version=3)


class Bot:
    def __init__(self, name):
        self.name = name
        self.sock = socket.create_connection((HOST, PORT))
        self.buf = b""
        self.state = "login"
        self.threshold = -1
        self.entity_id = None
        self.sounds = 0
        self.particles = 0
        self.last_summary = time.time()
        self.loaded_sent = False

    # ---- framing ----
    def send(self, pid, payload=b""):
        body = enc_varint(pid) + payload
        if self.threshold >= 0:
            if len(body) >= self.threshold:
                comp = zlib.compress(body)
                data = enc_varint(len(body)) + comp
            else:
                data = enc_varint(0) + body
            frame = enc_varint(len(data)) + data
        else:
            frame = enc_varint(len(body)) + body
        self.sock.sendall(frame)

    def recv_exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("server closed connection")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv_packet(self):
        # length-prefixed frame, read byte-wise for the varint
        length = 0
        for i in range(5):
            b = self.recv_exact(1)[0]
            length |= (b & 0x7F) << (7 * i)
            if not b & 0x80:
                break
        data = self.recv_exact(length)
        if self.threshold >= 0:
            r = Reader(data)
            dlen = r.varint()
            body = r.rest()
            if dlen > 0:
                body = zlib.decompress(body)
        else:
            body = data
        r = Reader(body)
        return r.varint(), r

    # ---- helpers ----
    def client_information(self, pid):
        p = (enc_utf("en_us") + bytes([4]) + enc_varint(0) + b"\x01"
             + bytes([0x7F]) + enc_varint(1) + b"\x00\x00" + enc_varint(0))
        self.send(pid, p)

    def resource_pack_reply(self, pid, r):
        pack_id = r.uuid()
        url = r.utf()
        pack_hash = r.utf()
        required = r.bool()
        has_prompt = r.bool()
        prompt = nbt_text(r.rest()) if has_prompt else ""
        log(f"RESOURCE PACK push url={url} hash={pack_hash} required={required} prompt={prompt!r}")
        self.send(pid, pack_id.bytes + enc_varint(0))  # SUCCESSFULLY_LOADED
        log("RESOURCE PACK replied SUCCESSFULLY_LOADED")

    def summary(self):
        now = time.time()
        if now - self.last_summary >= 10:
            log(f"SUMMARY sounds={self.sounds} particles={self.particles}")
            self.last_summary = now

    # ---- states ----
    def do_login(self, pid, r):
        if pid == 0x00:
            log(f"LOGIN DISCONNECT: {nbt_text(r.rest())}")
            sys.exit(1)
        if pid == 0x01:
            log("ENCRYPTION REQUEST - online mode? aborting")
            sys.exit(1)
        if pid == 0x02:
            gid = r.uuid()
            gname = r.utf()
            log(f"LOGIN FINISHED as {gname} ({gid})")
            self.send(0x03)  # login acknowledged
            self.state = "configuration"
            self.client_information(0x00)
            return
        if pid == 0x03:
            self.threshold = r.varint()
            log(f"COMPRESSION threshold={self.threshold}")
            return
        log(f"login: ignoring packet {pid:#x}")

    def do_config(self, pid, r):
        if pid == 0x02:
            log(f"CONFIG DISCONNECT: {nbt_text(r.rest())}")
            sys.exit(1)
        if pid == 0x03:
            self.send(0x03)
            self.state = "play"
            self.client_information(0x0D)
            log("ENTERED PLAY")
            return
        if pid == 0x04:
            self.send(0x04, struct.pack(">q", r.long()))
            return
        if pid == 0x05:
            self.send(0x05, struct.pack(">i", r.int()))
            return
        if pid == 0x09:
            self.resource_pack_reply(0x06, r)
            return
        if pid == 0x0E:
            n = r.varint()
            packs = [(r.utf(), r.utf(), r.utf()) for _ in range(n)]
            log(f"KNOWN PACKS request {packs} -> replying empty")
            self.send(0x07, enc_varint(0))
            return
        if pid == 0x01:
            channel = r.utf()
            if channel == "minecraft:brand":
                log(f"BRAND: {r.utf()}")
            return
        # registry data, tags, features, links, dialogs... nothing to answer
        return

    def do_play(self, pid, r):
        if pid == 0x20:
            log(f"PLAY DISCONNECT: {nbt_text(r.rest())}")
            sys.exit(1)
        if pid == 0x2B:  # keep alive
            self.send(0x1B, struct.pack(">q", r.long()))
            return
        if pid == 0x3B:  # ping
            self.send(0x2C, struct.pack(">i", r.int()))
            return
        if pid == 0x30:  # play login
            self.entity_id = r.int()
            log(f"PLAY LOGIN entity_id={self.entity_id}")
            return
        if pid == 0x46:  # player position sync
            tid = r.varint()
            self.send(0x00, enc_varint(tid))
            log(f"TELEPORT {tid} accepted")
            return
        if pid == 0x0B:  # chunk batch finished
            if not self.loaded_sent:
                self.send(0x0A, struct.pack(">f", 25.0))
                self.send(0x2B)  # player loaded
                self.loaded_sent = True
                log("CHUNKS loaded ack sent")
            return
        if pid == 0x66:  # set health
            hp = r.float()
            food = r.varint()
            sat = r.float()
            log(f"HEALTH {hp:.1f} food={food} sat={sat:.1f}")
            if hp <= 0:
                self.send(0x0B, enc_varint(0))
                log("DIED -> auto-respawn requested")
            return
        if pid == 0x77:  # system chat
            text = nbt_text(r.rest())
            log(f"CHAT: {text}")
            return
        if pid in (0x70, 0x6E, 0x55):  # title / subtitle / actionbar
            kind = {0x70: "TITLE", 0x6E: "SUBTITLE", 0x55: "ACTIONBAR"}[pid]
            log(f"{kind}: {nbt_text(r.rest())}")
            return
        if pid == 0x09:  # boss event: UUID id + varint operation
            r.uuid()
            action = r.varint()
            if action == 0:
                title = nbt_text(r.rest())
                log(f"BOSSBAR ADD: {title}")
            elif action == 1:
                log("BOSSBAR REMOVE")
            elif action == 2:
                log(f"BOSSBAR HP {r.float():.3f}")
            elif action == 3:
                log(f"BOSSBAR TITLE: {nbt_text(r.rest())}")
            elif action == 4:
                log(f"BOSSBAR STYLE color={r.varint()} division={r.varint()}")
            elif action == 5:
                log(f"BOSSBAR FLAGS {r.byte():#x}")
            return
        if pid == 0x4F:  # play resource pack push
            self.resource_pack_reply(0x30, r)
            return
        if pid == 0x80:
            log("ADVANCEMENTS packet received")
            return
        if pid == 0x50:
            log("RESPAWN packet")
            return
        if pid in (0x73, 0x72):
            self.sounds += 1
            self.summary()
            return
        if pid == 0x2E:
            self.particles += 1
            self.summary()
            return
        if pid == 0x2D:  # level event
            log(f"LEVEL EVENT type={r.int()}")
            return
        if pid == 0x24:
            log("EXPLODE packet")
            return
        if pid == 0x19:
            log("DAMAGE EVENT packet")
            return
        if pid == 0x63:  # entity motion (LpVec3 packed payload, values not decoded)
            eid = r.varint()
            if eid == self.entity_id:
                log("MOTION SET (knockback/pull)")
            return
        if pid == 0x82:  # mob effect
            eid = r.varint()
            if eid == self.entity_id:
                eff = r.varint()
                amp = r.byte()
                log(f"EFFECT id={eff} amplifier={amp}")
            return
        if pid == 0x4C:  # remove mob effect
            eid = r.varint()
            if eid == self.entity_id:
                log(f"EFFECT REMOVED id={r.varint()}")
            return
        if pid == 0x81:  # attributes
            eid = r.varint()
            if eid == self.entity_id:
                n = r.varint()
                vals = []
                for _ in range(n):
                    aid = r.varint()
                    base = struct.unpack(">d", r.take(8))[0]
                    mods = r.varint()
                    for _ in range(mods):
                        r.utf()
                        r.take(8)
                        r.varint()
                    vals.append(f"{aid}={base:.4f}")
                log(f"ATTRIBUTES [{', '.join(vals)}]")
            return
        if pid == 0x26:  # game event
            et = r.varint()
            val = r.float()
            names = {0: "NO_RESPAWN_BLOCK", 1: "START_RAINING", 2: "STOP_RAINING",
                     3: "CHANGE_GAMEMODE", 4: "WIN_GAME", 6: "ARROW_HIT",
                     7: "RAIN_LEVEL_CHANGE", 8: "THUNDER_LEVEL_CHANGE",
                     10: "ELDER_GUARDIAN", 11: "IMMEDIATE_RESPAWN"}
            log(f"GAME EVENT {names.get(et, et)} value={val:.2f}")
            return
        if pid == 0x22:  # entity event
            eid = r.int()
            if eid == self.entity_id:
                log(f"ENTITY EVENT {r.byte()}")
            return
        if pid == 0x74:
            log("START CONFIGURATION (reconfig) - not handled, exiting")
            sys.exit(1)
        return

    def run(self):
        proto = self.status_protocol()
        log(f"protocol={proto}")
        handshake = (enc_varint(proto) + enc_utf(HOST)
                     + struct.pack(">H", PORT) + enc_varint(2))
        self.send(0x00, handshake)
        uid = offline_uuid(self.name)
        self.send(0x00, enc_utf(self.name) + uid.bytes)
        log(f"LOGIN hello name={self.name} uuid={uid}")
        while True:
            pid, r = self.recv_packet()
            if self.state == "login":
                self.do_login(pid, r)
            elif self.state == "configuration":
                self.do_config(pid, r)
            else:
                self.do_play(pid, r)

    def status_protocol(self):
        s = socket.create_connection((HOST, PORT))
        try:
            hs = enc_varint(0) + enc_varint(-1) + enc_utf(HOST) + struct.pack(">H", PORT) + enc_varint(1)
            s.sendall(enc_varint(len(hs)) + hs)
            s.sendall(enc_varint(1) + enc_varint(0))
            buf = b""

            def exact(n):
                nonlocal buf
                while len(buf) < n:
                    c = s.recv(65536)
                    if not c:
                        raise ConnectionError("closed")
                    buf += c
                out, buf = buf[:n], buf[n:]
                return out

            length = 0
            for i in range(5):
                b = exact(1)[0]
                length |= (b & 0x7F) << (7 * i)
                if not b & 0x80:
                    break
            r = Reader(exact(length))
            r.varint()  # packet id 0
            resp = json.loads(r.utf())
            return resp["version"]["protocol"]
        finally:
            s.close()


if __name__ == "__main__":
    log(f"bot {NAME} starting")
    Bot(NAME).run()