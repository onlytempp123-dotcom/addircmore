import socket
import time
import random
import threading
import string

# ==========================================
# MASTER CONFIGURATION
# ==========================================
HOST = "irc.hybridirc.com"
PORT = 6667
NICK = "GamesHere"
REALNAME = "GamesHere"
CHANNEL = "#chatwithworld"
ADMIN = "Antonio"

# Game Constants
WORD_POOL = ["APPLE", "BANANA", "CHERRY", "DOG", "CAT", "HOUSE", "PLANE", "RAIN", "SNOW", "FIRE", "WATER", "EARTH", "PHONE", "TABLE", "CHAIR", "BOOK", "PEN", "DOOR", "WINDOW", "WALL"]
LOCS = [f"loc{i}" for i in range(1, 16)]

# ==========================================
# STATE MANAGER
# ==========================================
class BotState:
    def __init__(self):
        self.active_game = None  # None, 1, 2, 3, 4, 5
        self.ban_list = set()
        
        # Game 1: Cipher
        self.cipher = {"word": None, "scrambled": None}
        # Game 2: P&T
        self.pt = {"players": [], "state": "IDLE", "police": "", "thief": "", "innocents": [], "wrong": ""}
        # Game 3: Battle
        self.battle = {"players": {}} # {name: {hp, shield, bleeding, last_tick, last_atk}}
        # Game 4: LukaMari
        self.lm = {"phase": "IDLE", "players": [], "hiders": [], "dums": [], "locs": {}, "code": "", "duel_h": "", "next_dum": None}
        # Game 5: Dice Duel
        self.dice = {"p1": None, "p2": None}

S = BotState()

# ==========================================
# IRC HELPERS
# ==========================================
def send_raw(irc, msg):
    irc.send(f"{msg}\r\n".encode("utf-8"))

def say(irc, msg):
    send_raw(irc, f"PRIVMSG {CHANNEL} :{msg}")

def pm(irc, user, msg):
    send_raw(irc, f"PRIVMSG {user} :{msg}")

def notice(irc, user, msg):
    send_raw(irc, f"NOTICE {user} :{msg}")

def reset_all():
    S.active_game = None
    S.cipher = {"word": None, "scrambled": None}
    S.pt = {"players": [], "state": "IDLE", "police": "", "thief": "", "innocents": [], "wrong": ""}
    S.battle = {"players": {}}
    S.lm = {"phase": "IDLE", "players": [], "hiders": [], "dums": [], "locs": {}, "code": "", "duel_h": ""}
    S.dice = {"p1": None, "p2": None}

# ==========================================
# GAME GUIDES
# ==========================================
HOW_TO_PLAY = {
    "1": "🔠 [CIPHER] The bot scrambles a word. Type !solve <word> to win.",
    "2": "👮 [POLICE & THIEF] Needs 4 players. Police must guess who the Thief is among 3 suspects. Commands: !thief <name>, !reqguess, !giveup.",
    "3": "⚔️ [BATTLE] 2 Player PVP. 1000 HP. !fire <name> deals damage + bleeding. !shield stops bleeding and blocks next hit.",
    "4": "🙈 [LUKAMARI] Hide & Seek. Hide via PM (!hide locX). Seeker checks locations (!check locX). If found, race to type the code provided!",
    "5": "🎲 [DICE DUEL] 2 Players. Both roll a 100-sided die. Highest roll wins! Command: !roll"
}

# ==========================================
# CORE LOGIC
# ==========================================
def main():
    irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    irc.connect((HOST, PORT))
    send_raw(irc, f"NICK {NICK}")
    send_raw(irc, f"USER {NICK} 0 * :{REALNAME}")
    irc.setblocking(False)
    
    buffer = ""
    print(f"[*] {NICK} connected to {HOST}...")

    while True:
        curr_t = time.time()

        # --- REAL-TIME TICKER (Battle Bleeding) ---
        if S.active_game == 3:
            for p_name, p_data in list(S.battle["players"].items()):
                if p_data["bleeding"] and curr_t - p_data["last_tick"] >= 1.0:
                    dmg = 50
                    p_data["hp"] -= dmg
                    p_data["last_tick"] = curr_t
                    say(irc, f"🩸 {p_name} is bleeding! -{dmg} HP. ({p_data['hp']}/1000)")
                    if p_data["hp"] <= 0:
                        winner = next(n for n in S.battle["players"] if n != p_name)
                        say(irc, f"💀 {p_name} collapsed! 🏆 {winner} WINS!")
                        reset_all()

        try:
            data = irc.recv(4096).decode("utf-8", errors="ignore")
            if not data: break
            buffer += data
            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                
                # 24/7 PING PONG
                if line.startswith("PING"):
                    send_raw(irc, f"PONG {line.split()[1]}")
                
                if " 001 " in line or "376" in line:
                    send_raw(irc, f"JOIN {CHANNEL}")

                if "PRIVMSG" in line:
                    sender = line.split("!")[0][1:]
                    msg_section = line.split("PRIVMSG ")[1].split(" :", 1)
                    target = msg_section[0].strip()
                    msg = msg_section[1].strip()
                    msg_low = msg.lower()
                    is_pm = not target.startswith("#")
                    is_admin = (sender.lower() == ADMIN.lower())

                    if sender.lower() in S.ban_list: continue

                    # --- GLOBAL COMMANDS ---
                    if msg_low == "!gamelist":
                        say(irc, "🎮 Games: 1.Cipher | 2.Police&Thief | 3.Battle | 4.LukaMari | 5.DiceDuel")
                    
                    elif msg_low.startswith("!howtoplay "):
                        num = msg_low.split()[-1]
                        if num in HOW_TO_PLAY: say(irc, HOW_TO_PLAY[num])

                    elif msg_low.startswith("!ch "):
                        if S.active_game:
                            say(irc, f"❌ Game {S.active_game} is already running! Use !cancelgame first.")
                        else:
                            choice = msg_low.split()[-1]
                            if choice == "1":
                                S.active_game = 1
                                word = random.choice(WORD_POOL)
                                S.cipher = {"word": word, "scrambled": "".join(random.sample(word, len(word)))}
                                say(irc, f"🌀 Cipher Started! Solve: {S.cipher['scrambled']} (!solve <word>)")
                            elif choice == "2":
                                S.active_game = 2
                                say(irc, "👮 P&T Lobby Open! 4 players needed. Type !joingame")
                            elif choice == "3":
                                S.active_game = 3
                                say(irc, "⚔️ Battle Arena Open! 2 players needed. Type !join")
                            elif choice == "4":
                                S.active_game = 4
                                say(irc, "🏠 LukaMari Lobby Open! Type !play to join.")
                            elif choice == "5":
                                S.active_game = 5
                                say(irc, "🎲 Dice Duel! 2 players needed. Type !roll to join/play.")

                    elif msg_low == "!cancelgame" and is_admin:
                        say(irc, f"🛑 Game {S.active_game} cancelled by Admin.")
                        reset_all()

                    # --- GAME 1: CIPHER ---
                    if S.active_game == 1 and msg_low.startswith("!solve "):
                        guess = msg_low.split()[-1].upper()
                        if guess == S.cipher["word"]:
                            say(irc, f"🎉 {sender} solved it! The word was {S.cipher['word']}.")
                            reset_all()

                    # --- GAME 2: P&T ---
                    elif S.active_game == 2:
                        if msg_low == "!joingame" and S.pt["state"] == "IDLE":
                            if sender not in S.pt["players"]:
                                S.pt["players"].append(sender)
                                say(irc, f"🎮 P&T: {sender} joined ({len(S.pt['players'])}/4)")
                                if len(S.pt["players"]) == 4:
                                    p = S.pt["players"]
                                    random.shuffle(p)
                                    S.pt["police"], S.pt["thief"], S.pt["innocents"] = p[0], p[1], p[2:]
                                    notice(irc, S.pt["thief"], "🥷 You are the THIEF!")
                                    say(irc, f"👮 Police is {S.pt['police']}! Guess the Thief: !thief <name>")
                                    S.pt["state"] = "HUNT"
                        elif msg_low.startswith("!thief ") and sender == S.pt["police"]:
                            target_p = msg.split()[-1]
                            if target_p == S.pt["thief"]:
                                say(irc, f"🎉 Caught! {S.pt['thief']} was the Thief!"); reset_all()
                            else:
                                S.pt["wrong"] = target_p
                                say(irc, f"❌ {target_p} is Innocent! Police, !giveup or !reqguess?")

                    # --- GAME 3: BATTLE ---
                    elif S.active_game == 3:
                        if msg_low == "!join" and len(S.battle["players"]) < 2:
                            S.battle["players"][sender] = {"hp": 1000, "shield": False, "bleeding": False, "last_tick": 0, "last_atk": 0}
                            say(irc, f"⚔️ {sender} joined the Battle! ({len(S.battle['players'])}/2)")
                        elif msg_low.startswith("!fire "):
                            vic_name = msg.split()[-1]
                            if sender in S.battle["players"] and vic_name in S.battle["players"]:
                                atk, vic = S.battle["players"][sender], S.battle["players"][vic_name]
                                if curr_t - atk["last_atk"] < 4: continue
                                atk["last_atk"], atk["shield"] = curr_t, False
                                if vic["shield"]:
                                    vic["shield"] = False
                                    say(irc, f"🛡️ BLOCKED! {vic_name}'s shield broke!")
                                else:
                                    vic["hp"] -= 70; vic["bleeding"] = True; vic["last_tick"] = curr_t
                                    say(irc, f"💥 {sender} hit {vic_name}! 🩸 Bleeding!")
                        elif msg_low == "!shield" and sender in S.battle["players"]:
                            S.battle["players"][sender]["shield"] = True
                            S.battle["players"][sender]["bleeding"] = False
                            say(irc, f"🛡️ {sender} shielded. Bleeding stopped.")

                    # --- GAME 4: LUKAMARI ---
                    elif S.active_game == 4:
                        if msg_low == "!play" and S.lm["phase"] == "IDLE":
                            if sender not in S.lm["players"]: S.lm["players"].append(sender)
                            say(irc, f"✅ {sender} joined LukaMari. Need 2+. Wait 30s...")
                            # In a real bot, you'd use a timer here. For brevity, start now:
                            if len(S.lm["players"]) >= 2: S.lm["phase"] = "LOBBY_READY"
                        elif S.lm["phase"] == "LOBBY_READY" and is_admin: # Admin starts hiding
                            p = S.lm["players"]
                            S.lm["dums"] = [p[0]]; S.lm["hiders"] = p[1:]; S.lm["phase"] = "HIDING"
                            say(irc, f"🙈 Dum: {p[0]}. Hiders, PM me !hide loc1~15. You have 30s.")
                        elif is_pm and msg_low.startswith("!hide "):
                            if S.lm["phase"] == "HIDING" and sender in S.lm["hiders"]:
                                S.lm["locs"][sender] = msg_low.split()[-1]
                                notice(irc, sender, "✅ Hidden!")
                        elif msg_low.startswith("!check ") and sender in S.lm["dums"]:
                            loc = msg_low.split()[-1]
                            found = [h for h, l in S.lm["locs"].items() if l == loc]
                            if found:
                                S.lm["code"] = "".join(random.choices(string.ascii_uppercase, k=5))
                                S.lm["duel_h"], S.lm["phase"] = found[0], "DUEL"
                                say(irc, f"😱 Found {found[0]}! Race: Seeker !aaspas {S.lm['code']} | Hider !dhyapp {S.lm['code']}")
                            else: say(irc, "Empty!")

                    # --- GAME 5: DICE DUEL ---
                    elif S.active_game == 5:
                        if msg_low == "!roll":
                            if not S.dice["p1"]:
                                S.dice["p1"] = (sender, random.randint(1, 100))
                                say(irc, f"🎲 {sender} rolled {S.dice['p1'][1]}. Waiting for challenger...")
                            elif not S.dice["p2"] and sender != S.dice["p1"][0]:
                                S.dice["p2"] = (sender, random.randint(1, 100))
                                say(irc, f"🎲 {sender} rolled {S.dice['p2'][1]}.")
                                p1n, p1v = S.dice["p1"]; p2n, p2v = S.dice["p2"]
                                if p1v > p2v: say(irc, f"🏆 {p1n} WINS!")
                                elif p2v > p1v: say(irc, f"🏆 {p2n} WINS!")
                                else: say(irc, "🤝 It's a DRAW!")
                                reset_all()

        except (BlockingIOError, socket.timeout):
            time.sleep(0.1)
        except Exception as e:
            print(f"Error: {e}"); break

if __name__ == "__main__":
    main()
