"""TCP client for the RD30 digital interface behind a Moxa NPort.

The RD30 speaks a raw single-byte protocol (9600 8N1 on the serial side):
event bytes are pushed on every input change, query commands 32..35 return
one state byte each.  Event bytes and query replies share the same value
space, so every query sequence starts with the identify command: its reply
(30) is a value no event byte can take, which makes it a reliable anchor to
realign the stream on.  Bytes arriving before the anchor are pushed events
and are applied as such.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from .const import (
    CMD_IDENTIFY,
    CMD_QUERY,
    EVENT_OFF_BASE,
    EVENT_ON_BASE,
    IDENTIFY_REPLY,
    NUM_INPUTS,
    RECONNECT_MAX,
    RECONNECT_MIN,
    RESYNC_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class RD30Hub:
    """Maintains the TCP connection and the state of all 30 inputs."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.states: list[bool | None] = [None] * (NUM_INPUTS + 1)  # 1-based
        self.available = False
        # Diagnostics: survive connection drops so the diagnostic entity still
        # has something to tell while the link is down.
        self.last_connected: datetime | None = None
        self.last_disconnected: datetime | None = None
        self.last_event: datetime | None = None
        self.last_sync: datetime | None = None
        self.last_error: str | None = None
        self.connect_count = 0
        self.unknown_bytes = 0
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None
        # Callbacks per input number; key None = the diagnostic entity.
        # An event then rewrites only the affected entity instead of all of
        # them — otherwise the resync alone would multiply the state writes
        # without anything having changed.
        self._listeners: dict[int | None, list] = {}
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------- listeners
    def add_listener(self, cb, number: int | None = None) -> None:
        """Register cb for one input; number=None registers for diagnostics."""
        self._listeners.setdefault(number, []).append(cb)

    def remove_listener(self, cb, number: int | None = None) -> None:
        group = self._listeners.get(number)
        if group and cb in group:
            group.remove(cb)

    def _notify(self, numbers: set[int] | None = None) -> None:
        """Fire callbacks.  None means everything — availability changed."""
        if numbers is None:
            for group in list(self._listeners.values()):
                for cb in list(group):
                    cb()
            return
        for number in numbers:
            for cb in list(self._listeners.get(number, ())):
                cb()

    def _notify_diagnostics(self) -> None:
        """Only the diagnostic entity, e.g. because last_error changed."""
        for cb in list(self._listeners.get(None, ())):
            cb()

    # ------------------------------------------------------------- lifecycle
    async def async_start(self) -> None:
        self._task = asyncio.get_running_loop().create_task(self._run())

    async def async_stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._close()

    async def _close(self) -> None:
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except OSError:
                pass
        self._reader = None
        self._writer = None

    # ------------------------------------------------------------- main loop
    async def _run(self) -> None:
        backoff = RECONNECT_MIN
        while True:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - keep the loop alive
                _LOGGER.warning("RD30 %s:%s connection lost: %s",
                                self.host, self.port, err)
                self.last_error = str(err)
            if self.available:
                # The link had been up, so this is a fresh failure and not a
                # device that keeps refusing: restart the backoff instead of
                # inheriting what an earlier flapping phase grew it to.
                self.last_disconnected = datetime.now(timezone.utc)
                self.available = False
                backoff = RECONNECT_MIN
                self._notify()
            else:
                self._notify_diagnostics()
            await self._close()
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, RECONNECT_MAX)

    async def _connect_and_listen(self) -> None:
        _LOGGER.debug("Connecting to RD30 at %s:%s", self.host, self.port)
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout=10
        )

        if not await self._identify():
            raise ConnectionError("device did not answer identify (30)")

        await self._full_sync()
        self.available = True
        self.last_connected = datetime.now(timezone.utc)
        self.last_error = None
        self.connect_count += 1
        self._notify()
        _LOGGER.info("RD30 at %s:%s connected, %d inputs synced",
                     self.host, self.port, NUM_INPUTS)

        loop = asyncio.get_running_loop()
        last_resync = loop.time()
        while True:
            timeout = RESYNC_INTERVAL - (loop.time() - last_resync)
            if timeout <= 0:
                self._notify(await self._full_sync())
                last_resync = loop.time()
                continue
            try:
                data = await asyncio.wait_for(
                    self._reader.read(64), timeout=timeout
                )
            except asyncio.TimeoutError:
                continue
            if not data:
                raise ConnectionError("connection closed by peer")
            seen = (self.last_event, self.unknown_bytes)
            self._notify(self._apply_events(data))
            if (self.last_event, self.unknown_bytes) != seen:
                # Bytes only arrive when something really happened — let the
                # diagnostic entity know without tying it to the resync beat.
                self._notify_diagnostics()

    # ------------------------------------------------------------- protocol
    async def _send(self, byte: int) -> None:
        async with self._write_lock:
            self._writer.write(bytes([byte]))
            await self._writer.drain()

    async def _identify(self, changed: set[int] | None = None) -> bool:
        """Send command 1 and scan for reply 30.

        Event bytes (65..94 / 129..158) can never be 30, so anything else
        arriving in the window is a pushed event: it is applied and skipped.
        Reaching the reply therefore also means the stream is aligned — every
        byte the device still owed us has been consumed.
        """
        await self._send(CMD_IDENTIFY)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 3
        try:
            while loop.time() < deadline:
                data = await asyncio.wait_for(self._reader.read(16), timeout=3)
                if not data:
                    return False
                for index, byte in enumerate(data):
                    if byte == IDENTIFY_REPLY:
                        # Whatever trails the anchor is an event again.
                        found = self._apply_events(data[index + 1:])
                        if changed is not None:
                            changed |= found
                        return True
                    number = self._apply_event(byte)
                    if number is not None and changed is not None:
                        changed.add(number)
        except asyncio.TimeoutError:
            return False
        return False

    async def _full_sync(self) -> set[int]:
        """Query all four state bytes (commands 32..35).

        Realigns the stream first (see _identify).  Without that anchor a
        single event byte landing in the query window is consumed as the
        reply to command 32, which shifts every following reply by one group:
        inputs 25..30 would silently inherit the states of 17..24 and keep
        them until the next resync.
        """
        changed: set[int] = set()
        if not await self._identify(changed):
            raise ConnectionError("no identify reply, cannot align the stream")

        for cmd, first_input in CMD_QUERY.items():
            await self._send(cmd)
            try:
                data = await asyncio.wait_for(self._reader.read(1), timeout=2)
            except asyncio.TimeoutError as err:
                raise ConnectionError(f"no reply to query {cmd}") from err
            if not data:
                raise ConnectionError("connection closed during sync")
            value = data[0]
            count = 6 if cmd == 35 else 8
            for offset in range(count):
                number = first_input + offset
                state = bool(value & (1 << offset))
                if self.states[number] is not state:
                    self.states[number] = state
                    changed.add(number)

        self.last_sync = datetime.now(timezone.utc)
        return changed

    def _apply_events(self, data: bytes) -> set[int]:
        """Apply a run of pushed bytes; returns the inputs that changed."""
        changed: set[int] = set()
        for byte in data:
            number = self._apply_event(byte)
            if number is not None:
                changed.add(number)
        return changed

    def _apply_event(self, byte: int) -> int | None:
        """Apply one pushed event byte; returns the input if it changed."""
        if EVENT_ON_BASE + 1 <= byte <= EVENT_ON_BASE + NUM_INPUTS:
            number = byte - EVENT_ON_BASE
            self.last_event = datetime.now(timezone.utc)
            if self.states[number] is not True:
                self.states[number] = True
                _LOGGER.debug("RD30 input %d -> ON", number)
                return number
        elif EVENT_OFF_BASE + 1 <= byte <= EVENT_OFF_BASE + NUM_INPUTS:
            number = byte - EVENT_OFF_BASE
            self.last_event = datetime.now(timezone.utc)
            if self.states[number] is not False:
                self.states[number] = False
                _LOGGER.debug("RD30 input %d -> OFF", number)
                return number
        else:
            # Nothing the protocol knows.  Counted because a rising value
            # points at garbage on the line: wrong baud rate, data packing on
            # the device server, or a second client on the port.
            self.unknown_bytes += 1
            _LOGGER.debug("RD30 unexpected byte %d", byte)
        return None


async def async_probe(host: str, port: int) -> bool:
    """Standalone identity check used by the config flow."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=8
    )
    try:
        writer.write(bytes([CMD_IDENTIFY]))
        await writer.drain()
        deadline = asyncio.get_event_loop().time() + 3
        while asyncio.get_event_loop().time() < deadline:
            data = await asyncio.wait_for(reader.read(16), timeout=3)
            if not data:
                return False
            if IDENTIFY_REPLY in data:
                return True
        return False
    except asyncio.TimeoutError:
        return False
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass
