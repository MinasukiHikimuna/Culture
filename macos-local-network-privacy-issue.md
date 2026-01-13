# macOS Local Network Privacy Issue with Terminal Multiplexers over SSH

## Environment

**Computers involved:**
- **Mac mini** (10.0.1.7) - Ethernet connection, running macOS 26 Tahoe. This is the "server" machine where Zellij/tmux sessions and Python scripts run.
- **Windows server** (10.0.1.1 / fraktal.piilukko.fi) - Hosts LM Studio (port 1234) and Stashapp (port 443, hostname stash-aural.chiefsclub.com)
- **MacBook Air** (10.0.1.6) - WiFi, running macOS 26 Tahoe. Used to SSH into Mac mini for remote work.

**Services being accessed from Mac mini:**
- LM Studio API: `http://10.0.1.1:1234/v1/chat/completions`
- Stashapp GraphQL: `https://stash-aural.chiefsclub.com/graphql` (resolves to 10.0.1.1)

## The Problem

Python scripts running in terminal multiplexer sessions on the Mac mini lose TCP connectivity to **local network hosts only** after a specific sequence of events:

1. SSH from MacBook Air to Mac mini
2. Start or attach to a Zellij/tmux session
3. Detach from the session
4. Disconnect SSH

After step 4, **all** TCP connections to local network hosts (10.0.1.1, even gateway 10.0.0.1) fail with `[Errno 65] No route to host` - including connections that were already established before SSH disconnect.

## What Works vs What Breaks

| Scenario | Result |
|----------|--------|
| Running scripts directly on Mac mini (no multiplexer) | ✅ Works |
| Running scripts outside the multiplexer while session is broken | ✅ Works |
| Internet connections (google.com, 8.8.8.8) from broken session | ✅ Works |
| ICMP ping to local hosts from broken session | ✅ Works |
| New TCP connections to local network from broken session | ❌ Fails |
| Existing TCP connections to local network from broken session | ❌ Also fails |
| **Running multiplexer as root** (`sudo screen`) and scripts as root | ✅ Works |

## Testing Performed

### Tested with Zellij
- SSH → create session → start connectivity test → detach → disconnect SSH → **FAILS**
- Codesigning Zellij (`codesign --force --deep --sign -`) → **Still fails**
- Multiple exited Zellij sessions caused **alternating OK/FAIL** behavior; clearing them with `zellij delete-all-sessions` fixed the alternation but not the root cause

### Tested with tmux
- Same sequence: SSH → `tmux new-session` → start test → detach → disconnect SSH → **FAILS**

### Tested with screen
- Same behavior as user → **FAILS**
- **Running as root** (`sudo screen`, then running scripts as root inside) → **WORKS**

This confirms the issue is **not specific to any terminal multiplexer** but affects all of them (Zellij, tmux, screen) when running as a regular user.

### Other tests
- Running script with `sudo` inside a non-root multiplexer session → **Still fails**
- Persistent connection test (open socket before SSH disconnect, try to use it after) → **Also fails**
- Zellij not appearing in System Settings → Privacy & Security → Local Network list (no way to grant permission)

## Root Cause

macOS Tahoe's **Local Network Privacy** feature revokes local network TCP permissions when the originating SSH session disconnects. The terminal multiplexer server continues running but loses the network permission context it inherited from SSH. Even already-established connections are killed.

**Root processes are exempt from Local Network Privacy**, which is why `sudo screen` with root scripts works.

This breaks legitimate remote work workflows where you need to:
1. SSH into a machine
2. Start long-running work
3. Disconnect and leave it running

## Workaround

Run the terminal multiplexer as root:
```bash
sudo screen -S work
# or
sudo tmux new-session -s work
```

Then run scripts as root within that session. This bypasses Local Network Privacy.

**Downsides:** Running everything as root is a security risk and may cause file permission issues.

## Current Status

- **Workaround available:** Run multiplexer and scripts as root
- **No proper fix:** Apple has not provided MDM controls or a way to grant Local Network Privacy to CLI tools/multiplexers
- Filing a bug with Apple via Feedback Assistant is recommended

## References

- [Ghostty GitHub Discussion #2998](https://github.com/ghostty-org/ghostty/discussions/2998)
- [Michael Tsai - Local Network Privacy on Sequoia](https://mjtsai.com/blog/2024/10/02/local-network-privacy-on-sequoia/)
- [Apple Developer Forums - Local Network Privacy and MDM](https://developer.apple.com/forums/thread/762054)
- [Apple TN3179: Understanding Local Network Privacy](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)
