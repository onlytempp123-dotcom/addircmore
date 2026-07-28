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
active_game_id = None  # 0=None, 1=Cipher, 2=Police, 3=RPS, 4=Battle, 5=Luka
lock = threading.Lock()

# Rankings Structure: { "1": {user: score}, ..., "ov": {user: score} }
rankings = {str(i): {} for i in range(1, 6)}
rankings["ov"] = {}

# --- Flask Server (Keep-Alive) ---
app = Flask(__name__)
@app.route('/')
def home(): return "GamesHere & Yumi143 are running 24/7."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- IRC Bot Base Class ---
class IRCBot:
    def __init__(self, nickname):
        self.nickname = nickname
        self.sock = None

    def send_raw(self, msg):
        if self.sock:
            try: self.sock.send((msg + "\r\n").encode('utf-8'))
            except: pass

    def send_msg(self, target, msg):
        self.send_raw(f"PRIVMSG {target} :{msg}")

    def connect(self):
        print(f"[{self.nickname}] Connecting to {SERVER}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        try:
            self.sock.connect((SERVER, PORT))
            self.send_raw(f"NICK {self.nickname}")
            self.send_raw(f"USER {self.nickname} 0 * :Bot Service")
            
            # Simple registration wait
            time.sleep(2)
            self.send_raw(f"JOIN {CHANNEL}")
        except Exception as e:
            print(f"Connection error: {e}")

# --- Bot A: GamesHere (The Game Master) ---
class GamesBot(IRCBot):
    def __init__(self):
        super().__init__("GamesHere")
        self.state = {} # Holds variables for the current active game
        self.cipher_words = ["APPLE", "BANANA", "CHERRY", "DANCE", "GALAXY", "GUITAR", "PIZZA", "MOUNTAIN", "WIZARD"]
        self.locations = {f"loc{i}": n for i, n in enumerate(["Bathroom", "Rooftop", "Basement", "Kitchen", "Attic", "Garden", "Garage"], 1)}

    def update_score(self, user, amount, gid):
        user = user.lower()
        with lock:
            rankings[str(gid)][user] = rankings[str(gid)].get(user, 0) + amount
            rankings["ov"][user] = rankings["ov"].get(user, 0) + amount

    def handle_admin(self, sender, msg):
        global games_enabled, active_game_id
        if sender != MASTER_OWNER: return

        if msg == "!gamemodeon": games_enabled = True; self.send_msg(CHANNEL, "🎮 Game Mode: ON.")
        elif msg == "!gamemodeoff": games_enabled = False; self.send_msg(CHANNEL, "🎮 Game Mode: OFF.")
        elif msg == "!cancelgame":
            active_game_id = None; self.state = {}
            self.send_msg(CHANNEL, "🛑 Current game has been terminated.")
        
        # !setrank<num> user score
        sr_match = re.match(r"!setrank(\d+) (\S+) (\d+)", msg)
        if sr_match:
            gid, user, score = sr_match.groups()
            if gid in rankings:
                rankings[gid][user.lower()] = int(score)
                self.send_msg(CHANNEL, f"✅ Game {gid} rank for {user} updated to {score}.")

        elif msg.startswith("!setrankov "):
            parts = msg.split()
            if len(parts) == 3:
                rankings["ov"][parts[1].lower()] = int(parts[2])
                self.send_msg(CHANNEL, f"✅ Overall rank for {parts[1]} updated to {parts[2]}.")

        elif msg == "!superhowtoplay":
            self.send_msg(sender, "Manual: !ch 1=Cipher(!solve), 2=Police(!joingame/!thief), 3=RPS(!rps), 4=Battle(!join/!fire/!shield), 5=Luka(!play/!hide/!check)")

    def process_msg(self, sender, target, msg):
        global active_game_id
        if not games_enabled: return
        msg_l = msg.lower()

        # --- General Commands ---
        if msg_l == "!gamelist":
            self.send_msg(CHANNEL, "🎮 1:Cipher | 2:Police&Thief | 3:RPS | 4:Fire&Shield | 5:LukaMari")
        
        elif msg_l.startswith("!ch "):
            if active_game_id:
                self.send_msg(CHANNEL, "❌ A game is already running. Please finish or !cancelgame.")
            else:
                gid = msg_l.split()[-1]
                if gid in ["1","2","3","4","5"]:
                    active_game_id = int(gid)
                    self.state = {"players": [], "sub_phase": "IDLE"}
                    self.send_msg(CHANNEL, f"🎯 Game {gid} Activated! Type !howtoplay {gid} for rules.")

        elif msg_l.startswith("!howtoplay "):
            gid = msg_l.split()[-1]
            helps = {"1":"Cipher: Solve scrambled words with !solve <word>","2":"Police: 4 players. Police guesses thief via !thief <name>","3":"RPS: Challenge bot via !rps <rock/paper/scissor>","4":"Battle: 2 players. Use !fire <nick> or !shield","5":"Luka: Hide & Seek. PM me !hide <loc1-7>, Seeker uses !check <loc1-7>"}
            self.send_msg(CHANNEL, helps.get(gid, "Select 1-5"))

        elif msg_l == "!ovrank":
            top = sorted(rankings["ov"].items(), key=lambda x: x[1], reverse=True)[:5]
            self.send_msg(CHANNEL, "🏆 TOTAL RANK: " + " | ".join([f"{u}({s})" for u, s in top]))

        # --- Game 1: Cipher Master ---
        if active_game_id == 1:
            if msg_l == "!cipher":
                self.state["word"] = random.choice(self.cipher_words)
                scrambled = "".join(random.sample(self.state["word"], len(self.state["word"])))
                self.send_msg(CHANNEL, f"🌀 Scramble: {scrambled} | Solve: !solve <word>")
            elif msg_l.startswith("!solve "):
                guess = msg.split()[-1].upper()
                if guess == self.state.get("word"):
                    self.update_score(sender, 10, 1)
                    self.send_msg(CHANNEL, f"🎉 {sender} solved it! (+10pts)"); self.state["word"] = None

        # --- Game 2: Police & Thief ---
        elif active_game_id == 2:
            if msg_l == "!joingame" and sender not in self.state["players"] and len(self.state["players"]) < 4:
                self.state["players"].append(sender)
                self.send_msg(CHANNEL, f"👤 {sender} joined ({len(self.state['players'])}/4)")
                if len(self.state["players"]) == 4:
                    roles = ["Police", "Thief", "Innocent", "Innocent"]; random.shuffle(roles)
                    self.state["roles"] = dict(zip(self.state["players"], roles))
                    for p, r in self.state["roles"].items():
                        if r == "Police": self.state["police"] = p
                        elif r == "Thief": self.state["thief"] = p
                        self.send_raw(f"NOTICE {p} :You are: {r}")
                    self.send_msg(CHANNEL, f"👮 Police is {self.state['police']}. Guess the Thief: !thief <name>")

            elif msg_l.startswith("!thief ") and sender == self.state.get("police"):
                target = msg.split()[-1]
                if target.lower() == self.state.get("thief","").lower():
                    self.update_score(sender, 100, 2); self.send_msg(CHANNEL, f"🏆 {sender} caught the Thief! (+100pts)")
                else:
                    self.update_score(sender, -50, 2); self.send_msg(CHANNEL, f"💀 Wrong! Police loses -50pts.")
                active_game_id = None

        # --- Game 3: RPS ---
        elif active_game_id == 3:
            if msg_l.startswith("!rps "):
                u_choice = msg_l.split()[-1]
                bot = random.choice(["rock", "paper", "scissor"])
                if u_choice == bot: res = "Tie!"
                elif (u_choice=="rock" and bot=="scissor") or (u_choice=="paper" and bot=="rock") or (u_choice=="scissor" and bot=="paper"):
                    self.update_score(sender, 10, 3); res = "You Win! (+10pts)"
                else: self.update_score(sender, -5, 3); res = "I Win! (-5pts)"
                self.send_msg(CHANNEL, f"🤖 Bot picks {bot}. {res}")

        # --- Game 4: BattleBot ---
        elif active_game_id == 4:
            if msg_l == "!join" and len(self.state["players"]) < 2 and sender not in self.state["players"]:
                self.state["players"].append(sender); self.state[sender] = {"hp": 1000, "shield": False}
                self.send_msg(CHANNEL, f"⚔️ {sender} entered the arena ({len(self.state['players'])}/2)")
            elif msg_l.startswith("!fire ") and sender in self.state["players"]:
                target = msg.split()[-1]
                if target in self.state and target != sender:
                    if self.state[target]["shield"]:
                        self.state[target]["shield"] = False; self.send_msg(CHANNEL, f"🛡️ {target} blocked the hit!")
                    else:
                        dmg = random.randint(70, 150); self.state[target]["hp"] -= dmg
                        self.send_msg(CHANNEL, f"💥 {sender} hits {target} for {dmg} DMG! (HP: {self.state[target]['hp']})")
                        if self.state[target]["hp"] <= 0:
                            self.send_msg(CHANNEL, f"🏆 {sender} wins the battle!"); active_game_id = None
            elif msg_l == "!shield" and sender in self.state:
                self.state[sender]["shield"] = True; self.send_msg(CHANNEL, f"🛡️ {sender} raised a shield!")

        # --- Game 5: LukaMari ---
        elif active_game_id == 5:
            if msg_l == "!play" and sender not in self.state["players"]:
                self.state["players"].append(sender)
                self.send_msg(CHANNEL, f"🏃 {sender} joined LukaMari.")
                if len(self.state["players"]) == 3:
                    self.state["dum"] = random.choice(self.state["players"])
                    self.state["hiders"] = [p for p in self.state["players"] if p != self.state["dum"]]
                    self.state["hider_spots"] = {}
                    self.send_msg(CHANNEL, f"👹 Seeker: {self.state['dum']}. Hiders: PM me !hide <loc1-7>")
            
            # PM logic for hiding
            if target == self.nickname and msg_l.startswith("!hide "):
                loc = msg_l.split()[-1]
                if loc in self.locations:
                    self.state["hider_spots"][sender] = loc
                    self.send_msg(sender, f"🤫 You are hidden in the {self.locations[loc]}.")

            elif msg_l.startswith("!check ") and sender == self.state.get("dum"):
                loc = msg_l.split()[-1]
                found = [h for h, l in self.state.get("hider_spots",{}).items() if l == loc]
                if found:
                    for h in found: self.send_msg(CHANNEL, f"👀 Found {h} at {loc}!"); self.state["hiders"].remove(h)
                else: self.send_msg(CHANNEL, f"💨 No one at {loc}.")
                if not self.state.get("hiders"): self.send_msg(CHANNEL, "🏆 All hiders found! Seeker wins."); active_game_id = None

    def listen(self):
        while True:
            try:
                line = self.sock.recv(2048).decode('utf-8', errors='ignore')
                if not line: break
                if "PING" in line: self.send_raw("PONG " + line.split()[1])
                if "PRIVMSG" in line:
                    parts = line.split(" ", 3)
                    sender = parts[0][1:].split('!')[0]
                    target = parts[2]
                    message = parts[3][1:] if len(parts) > 3 else ""
                    self.handle_admin(sender, message)
                    self.process_msg(sender, target, message)
            except: time.sleep(5); self.connect()

# --- Bot B: YUMI143 (Activity Bot) ---
class YumiBot(IRCBot):
    def __init__(self):
        super().__init__("YUMI143")

    def run_activity(self):
        while True:
            time.sleep(180) # 3 Minutes
            self.send_msg(CHANNEL, "Wishing everyone all the best. May everything continue to go smoothly.")

    def listen(self):
        while True:
            try:
                line = self.sock.recv(2048).decode('utf-8', errors='ignore')
                if not line: break
                if "PING" in line: self.send_raw("PONG " + line.split()[1])
            except: time.sleep(5); self.connect()

# --- Main Execution ---
if __name__ == "__main__":
    # Start Flask
    threading.Thread(target=run_flask, daemon=True).start()

    # Init Bots
    bot_a = GamesBot()
    bot_b = YumiBot()

    # Run Bot A
    threading.Thread(target=lambda: (bot_a.connect(), bot_a.listen()), daemon=True).start()
    # Run Bot B
    threading.Thread(target=lambda: (bot_b.connect(), bot_b.listen()), daemon=True).start()
    # Run B's 3-min loop
    threading.Thread(target=bot_b.run_activity, daemon=True).start()

    while True: time.sleep(1)
