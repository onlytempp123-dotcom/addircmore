import socket
import threading
import time
import os
import re
import random
from flask import Flask

# --- Configuration ---
SERVER = "irc.hybridirc.com"
PORT = 6667
CHANNEL = "#chatwithworld"
MASTER_OWNER = "Antonio"

# --- Shared Data & Rankings ---
games_enabled = True
active_game_id = None
lock = threading.Lock()
rankings = {str(i): {} for i in range(1, 6)}
rankings["ov"] = {}

app = Flask(__name__)
@app.route('/')
def home(): return "Bots are active. PING/PONG handled."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- Improved IRC Bot Base Class ---
class IRCBot:
    def __init__(self, nickname):
        self.nickname = nickname
        self.sock = None
        self.is_running = False

    def send_raw(self, msg):
        if self.sock:
            try:
                self.sock.send((msg + "\r\n").encode('utf-8'))
                print(f"[{self.nickname}] SENT: {msg}")
            except Exception as e:
                print(f"[{self.nickname}] Send Error: {e}")

    def send_msg(self, target, msg):
        self.send_raw(f"PRIVMSG {target} :{msg}")

    def connect_and_listen(self):
        while True: # Infinite reconnection loop
            try:
                print(f"[{self.nickname}] Attempting connection...")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(240) # Server usually pings every 90-180s
                self.sock.connect((SERVER, PORT))
                
                # 1. Registration
                self.send_raw(f"NICK {self.nickname}")
                self.send_raw(f"USER {self.nickname} 0 * :Bot Service")

                buffer = ""
                registered = False

                while True:
                    data = self.sock.recv(4096).decode('utf-8', errors='ignore')
                    if not data: break
                    buffer += data
                    lines = buffer.split("\r\n")
                    buffer = lines.pop()

                    for line in lines:
                        if not line: continue
                        print(f"[{self.nickname}] RECV: {line}")

                        # Handle PING/PONG immediately
                        if line.startswith("PING"):
                            self.send_raw("PONG " + line.split()[1])

                        # Wait for code 001 (Welcome) or 376 (End of MOTD) to join
                        if not registered and (" 001 " in line or " 376 " in line):
                            print(f"[{self.nickname}] Registered! Joining {CHANNEL}")
                            self.send_raw(f"JOIN {CHANNEL}")
                            registered = True

                        # Handle commands/messages
                        if registered and "PRIVMSG" in line:
                            self.handle_line(line)

            except Exception as e:
                print(f"[{self.nickname}] Disconnected: {e}. Retrying in 10s...")
                time.sleep(10)

    def handle_line(self, line):
        # To be overridden by child classes
        pass

# --- Bot A: GamesHere ---
class GamesBot(IRCBot):
    def __init__(self):
        super().__init__("GamesHere")
        self.state = {}
        self.cipher_words = ["APPLE", "BANANA", "CHERRY", "GALAXY", "PIZZA", "WIZARD", "LAPTOP"]
        self.locations = {f"loc{i}": n for i, n in enumerate(["Kitchen", "Attic", "Garden", "Garage", "Roof"], 1)}

    def update_score(self, user, amount, gid):
        user = user.lower()
        with lock:
            rankings[str(gid)][user] = rankings[str(gid)].get(user, 0) + amount
            rankings["ov"][user] = rankings["ov"].get(user, 0) + amount

    def handle_line(self, line):
        global active_game_id, games_enabled
        parts = line.split(" ", 3)
        if len(parts) < 4: return
        
        sender = parts[0][1:].split('!')[0]
        target = parts[2]
        msg = parts[3][1:]
        msg_l = msg.lower()

        # Admin Commands (Antonio Only)
        if sender == MASTER_OWNER:
            if msg_l == "!gamemodeon": games_enabled = True; self.send_msg(CHANNEL, "🎮 Game Mode: ON.")
            elif msg_l == "!gamemodeoff": games_enabled = False; self.send_msg(CHANNEL, "🎮 Game Mode: OFF.")
            elif msg_l == "!cancelgame": active_game_id = None; self.state = {}; self.send_msg(CHANNEL, "🛑 Game Cancelled.")
            elif msg_l == "!superhowtoplay": self.send_msg(sender, "1:Cipher, 2:Police, 3:RPS, 4:Battle, 5:Luka. Use !ch <num> to start.")

        if not games_enabled: return

        # Public Commands
        if msg_l == "!gamelist": self.send_msg(CHANNEL, "🎮 1:Cipher | 2:Police | 3:RPS | 4:Battle | 5:Luka")
        elif msg_l.startswith("!ch "):
            if active_game_id: self.send_msg(CHANNEL, "❌ Game in progress.")
            else:
                gid = msg_l.split()[-1]
                if gid in rankings:
                    active_game_id = int(gid)
                    self.state = {"players": []}
                    self.send_msg(CHANNEL, f"🎯 Game {gid} started! !howtoplay {gid}")

        # --- Simplified Game Logic Integration ---
        if active_game_id == 1: # Cipher
            if msg_l == "!cipher":
                self.state["word"] = random.choice(self.cipher_words)
                scrambled = "".join(random.sample(self.state["word"], len(self.state["word"])))
                self.send_msg(CHANNEL, f"🌀 Solve: {scrambled}")
            elif msg_l.startswith("!solve "):
                if msg.split()[-1].upper() == self.state.get("word"):
                    self.update_score(sender, 10, 1); self.send_msg(CHANNEL, f"🎉 {sender} wins! (+10pts)"); self.state["word"] = None

        elif active_game_id == 3: # RPS
            if msg_l.startswith("!rps "):
                bot = random.choice(["rock", "paper", "scissor"])
                self.send_msg(CHANNEL, f"🤖 Bot picks {bot}. (Use !ovrank to check scores)")
                self.update_score(sender, 5, 3) # Simple point for playing

# --- Bot B: YUMI143 ---
class YumiBot(IRCBot):
    def __init__(self):
        super().__init__("YUMI143")

    def run_timer(self):
        while True:
            time.sleep(180) # 3 Minutes
            if self.sock:
                self.send_msg(CHANNEL, "Wishing everyone all the best. May everything continue to go smoothly.")

# --- Start ---
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()

    gb = GamesBot()
    yb = YumiBot()

    # Start Bot Threads
    threading.Thread(target=gb.connect_and_listen, daemon=True).start()
    threading.Thread(target=yb.connect_and_listen, daemon=True).start()
    
    # Start Yumi's 3-minute well-wishes
    threading.Thread(target=yb.run_timer, daemon=True).start()

    while True:
        time.sleep(1)
