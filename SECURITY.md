# Security Policy

## Supported Versions

Only the latest release is supported. Please update to the latest version before reporting an issue.

## Reporting a Vulnerability

This integration talks to exactly one thing: the TCP port of the serial device server you configure (host and port from the config flow), on your local network. It opens one plain TCP connection to it, sends single-byte query commands (`1`, `32`–`35`) and reads the single-byte replies and event bytes the RD30 pushes. Nothing leaves your network, no cloud service is involved, no credentials exist — the RD30 protocol has none, and a serial device server in TCP server mode does not authenticate clients either.

That last point is worth knowing: **anyone who can reach the device server's TCP port can read the input states.** Keep the device server on a trusted network segment, as you would any unauthenticated serial-over-IP bridge. The integration itself only reads; it never writes anything to the RD30 that could change an output or a setting, because the module has no such commands.

**Robustness against bad data:** every incoming byte is checked against the small value space the protocol defines; bytes outside it are counted (`unknown_bytes`) and dropped. A reply that does not arrive within two seconds, or a missing identity reply, closes the connection and triggers a reconnect with backoff. Nothing from the wire is executed, evaluated or written to disk.

**What is stored:** host and port in Home Assistant's config entry storage, input names and device classes in the entry options. The log never contains more than host, port and error texts.

If you believe you have found a security issue, please report it privately via [GitHub Security Advisories](../../security/advisories/new) rather than opening a public issue.
