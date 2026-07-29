# GamesHere — Unified IRC Games Bot

Single IRC bot hosting 4 games on one connection, one game active at a time.

## Games
1. Cipher Scramble — `!cipher`
2. Police & Thief — `!joingame`
3. Fire & Shield Battle — `!join`
4. Hide & Seek (LukaMari) — `!play`

Full command list: type `!howtoplay` or `!superhowtoplay` (admin, sent via PM) once connected.

## Setup
```
pip install -r requirements.txt   # no external deps currently required
python3 app.py
```

## Config
Edit the top of `app.py`:
```python
HOST = "irc.hybridirc.com"
PORT = 6667
NICK = "GamesHere"
CHANNEL = "#chatwithworld"
ADMIN = "Antonio"
```

## 24/7 hosting
`app.py` auto-reconnects on disconnect (5s backoff) and answers PING/PONG.
For the *process* to survive crashes/reboots, run it under a supervisor, e.g.:

**systemd** (`/etc/systemd/system/gameshere.service`):
```ini
[Unit]
Description=GamesHere IRC Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/app.py
Restart=always
RestartSec=5
User=youruser

[Install]
WantedBy=multi-user.target
```
Then: `sudo systemctl enable --now gameshere`

**or pm2**: `pm2 start app.py --interpreter python3 --name gameshere`

## Notes
- Scores/bans are in-memory only — a bot restart clears them. Say the word if you want them persisted to a JSON file across restarts.
- Only one game can run at a time bot-wide.
