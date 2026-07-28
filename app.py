import threading
import time
import random
import socket
import ssl
from flask import Flask

app = Flask(__name__)

# ==========================================
# CONFIGURATION CONSTANTS
# ==========================================
IRC_HOST = "irc.hybridirc.com"
IRC_PORT = 6697  # Updated to SSL port 6697
CHANNEL = "#chatwithworld"
ADMIN = "Antonio"

CIPHER_POOL = [
    "APPLE", "BANANA", "CHERRY", "DOG", "CAT", "MOUSE", "HOUSE", "PLANE", "TRAIN", "BOAT",
    "SUN", "MOON", "STAR", "CLOUD", "RAIN", "SNOW", "WIND", "FIRE", "WATER", "EARTH",
    "PHONE", "TABLE", "CHAIR", "DESK", "LAMP", "BOOK", "PEN", "PAPER", "KEY", "LOCK"
]


# ==========================================
# BOT B: YUMI143 (Automated 3-min Broadcaster)
# ==========================================
def run_yumi143_bot():
    nick = "YUMI143"
    while True:
        try:
            print(f"[*] YUMI143 connecting via SSL to {IRC_HOST}:{IRC_PORT}...")
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            context = ssl.create_default_context()
            irc = context.wrap_socket(raw_socket, server_hostname=IRC_HOST)
            irc.connect((IRC_HOST, IRC_PORT))
            
            irc.send(f"NICK {nick}\r\nUSER {nick} 0 * :YUMI Broadcast Bot\r\n".encode("utf-8"))
            
            irc.setblocking(False)
            buffer = ""
            joined = False
            last_broadcast = time.time()

            while True:
                current_time = time.time()
                if joined and (current_time - last_broadcast >= 180):
                    msg = "Wishing everyone all the best. May everything continue to go smoothly."
                    print(f">> YUMI143 Broadcasting: {msg}")
                    irc.send(f"PRIVMSG {CHANNEL} :{msg}\r\n".encode("utf-8"))
                    last_broadcast = time.time()

                try:
                    data = irc.recv(2048).decode("utf-8", errors="ignore")
                    if not data:
                        break
                    buffer += data
                    lines = buffer.split("\r\n")
                    buffer = lines.pop()

                    for line in lines:
                        if line.startswith("PING"):
                            irc.send(f"PONG {line.split()[1]}\r\n".encode("utf-8"))
                        if not joined and (" 001 " in line or "376" in line or "422" in line):
                            print(f"[*] YUMI143 joining {CHANNEL}...")
                            irc.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))
                            joined = True
                except (BlockingIOError, ssl.SSLWantReadError):
                    time.sleep(0.5)
        except Exception as e:
            print(f"[!] YUMI143 error: {e}. Reconnecting in 10 seconds...")
            time.sleep(10)


# ==========================================
# BOT A: GamesHere (All 5 Games & Core Loop)
# ==========================================
def run_gameshere_bot():
    nick = "GamesHere"
    
    game_leaderboards = {1: {}, 2: {}, 3: {}, 4: {}, 5: {}}
    overall_leaderboard = {}
    
    game_mode_active = True
    current_active_game = None 
    
    cipher_word = None
    cipher_scrambled = None

    pt_state = "IDLE"
    pt_players = []
    pt_police = ""
    pt_thief = ""

    battle_ban_list = set()
    battle_players = {}  
    battle_active = False

    num_target = 0

    def send_msg(irc_socket, target, text):
        print(f">> GamesHere to {target}: {text}")
        irc_socket.send(f"PRIVMSG {target} :{text}\r\n".encode("utf-8"))

    while True:
        try:
            print(f"[*] GamesHere connecting via SSL to {IRC_HOST}:{IRC_PORT}...")
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            context = ssl.create_default_context()
            irc = context.wrap_socket(raw_socket, server_hostname=IRC_HOST)
            irc.connect((IRC_HOST, IRC_PORT))
            
            irc.send(f"NICK {nick}\r\nUSER {nick} 0 * :Master Gaming Bot\r\n".encode("utf-8"))

            irc.setblocking(False)
            buffer = ""
            joined = False

            while True:
                current_time = time.time()

                # --- Game 4 Loop: Apply Dynamic -50 HP/sec Bleeding Damage ---
                if current_active_game == "battle" and battle_active:
                    dead_players = []
                    for p_name, p_data in list(battle_players.items()):
                        if p_data["bleeding"]:
                            seconds_passed = current_time - p_data["last_bleed_tick"]
                            if seconds_passed >= 1.0:
                                ticks = int(seconds_passed)
                                damage = ticks * 50
                                p_data["hp"] -= damage
                                p_data["last_bleed_tick"] += ticks

                                send_msg(irc, CHANNEL, f"🩸 **{p_name}** is bleeding out! Lost -{damage} HP. (Remaining: {p_data['hp']}/1000 HP)")

                                if p_data["hp"] <= 0:
                                    dead_players.append(p_name)

                    for dead_p in dead_players:
                        send_msg(irc, CHANNEL, f"💀 **{dead_p}** couldn't stop the bleeding and collapsed in battle!")
                        survivor = [name for name in battle_players if name != dead_p]
                        if survivor:
                            survivor_name = survivor[0]
                            send_msg(irc, CHANNEL, f"🏆 **👑 {survivor_name} 👑** wins the battle! Match ended.")
                            u = survivor_name.lower()
                            game_leaderboards[4][u] = game_leaderboards[4].get(u, 0) + 100
                            overall_leaderboard[u] = overall_leaderboard.get(u, 0) + 100
                        battle_active = False
                        battle_players.clear()
                        current_active_game = None

                try:
                    data = irc.recv(2048).decode("utf-8", errors="ignore")
                    if not data:
                        break
                    buffer += data
                    lines = buffer.split("\r\n")
                    buffer = lines.pop()

                    for line in lines:
                        if line.startswith("PING"):
                            irc.send(f"PONG {line.split()[1]}\r\n".encode("utf-8"))

                        if not joined and (" 001 " in line or "376" in line or "422" in line):
                            print(f"[*] GamesHere joining {CHANNEL}...")
                            irc.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))
                            joined = True

                        if f"PRIVMSG {CHANNEL}" in line:
                            parts = line.split("!")
                            if not parts: continue
                            sender = parts[0][1:]
                            msg_full = line.split(f"PRIVMSG {CHANNEL} :")[-1].strip()
                            msg_lower = msg_full.lower()

                            # ================= ADMIN CONTROLS =================
                            if msg_lower == "!gamemodeon":
                                if sender.lower() == ADMIN.lower():
                                    game_mode_active = True
                                    send_msg(irc, CHANNEL, "🎮 GamesHere mode is now ENABLED! Let the games begin! 🚀")
                                else:
                                    send_msg(irc, CHANNEL, f"❌ Access Denied, {sender}.")
                                continue

                            elif msg_lower == "!gamemodeoff":
                                if sender.lower() == ADMIN.lower():
                                    game_mode_active = False
                                    current_active_game = None
                                    send_msg(irc, CHANNEL, "🛑 GamesHere mode is now DISABLED.")
                                else:
                                    send_msg(irc, CHANNEL, f"❌ Access Denied, {sender}.")
                                continue

                            elif msg_lower == "!cancelgame":
                                if sender.lower() == ADMIN.lower():
                                    current_active_game = None
                                    pt_state = "IDLE"
                                    pt_players = []
                                    battle_active = False
                                    battle_players.clear()
                                    send_msg(irc, CHANNEL, "⚠️ Active game session forcefully terminated by admin!")
                                else:
                                    send_msg(irc, CHANNEL, f"❌ Access Denied, {sender}.")
                                continue

                            if not game_mode_active:
                                continue

                            # ================= NAVIGATION =================
                            if msg_lower == "!gamelist":
                                send_msg(irc, CHANNEL, "📋 AVAILABLE GAMES: [1] Cipher Master | [2] Police & Thief | [3] Rock Paper Scissors | [4] Fire & Shield Battle | [5] Number Guessing. Use !ch <number> to launch!")
                                continue

                            elif msg_lower.startswith("!howtoplay "):
                                try:
                                    g_num = int(msg_lower.split()[1])
                                    if g_num == 4:
                                        send_msg(irc, CHANNEL, "📜 Fire & Shield Battle: Type !ch 4 then !join to enter. Use !fire <name> and !shield. (+100pts)")
                                    elif g_num == 1:
                                        send_msg(irc, CHANNEL, "📜 Cipher Master: Unscramble the word using !solve <word>.")
                                    elif g_num == 2:
                                        send_msg(irc, CHANNEL, "📜 Police & Thief: Type !joingame. Police accuses via !thief <user>.")
                                    elif g_num == 3:
                                        send_msg(irc, CHANNEL, "📜 RPS: Type !rps <rock|paper|scissor>.")
                                    elif g_num == 5:
                                        send_msg(irc, CHANNEL, "📜 Number Guessing: Type !guessnum <number>.")
                                except ValueError:
                                    pass
                                continue

                            elif msg_lower == "!ovrank":
                                if not overall_leaderboard:
                                    send_msg(irc, CHANNEL, "🏆 Overall Leaderboard is empty!")
                                else:
                                    sorted_ov = sorted(overall_leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
                                    send_msg(irc, CHANNEL, f"🏆 OVERALL TOP 5: {' | '.join([f'{u}({s}pts)' for u, s in sorted_ov])}")
                                continue

                            # ================= SELECT GAME (!ch <1-5>) =================
                            elif msg_lower.startswith("!ch "):
                                try:
                                    choice = int(msg_lower.split()[1])
                                    if current_active_game is not None:
                                        send_msg(irc, CHANNEL, f"❌ A game is already active! Finish it or type !cancelgame.")
                                        continue

                                    if choice == 1:
                                        current_active_game = "cipher"
                                        cipher_word = random.choice(CIPHER_POOL)
                                        chars = list(cipher_word)
                                        random.shuffle(chars)
                                        cipher_scrambled = "".join(chars)
                                        send_msg(irc, CHANNEL, f"🌀 Cipher Master Started! Scrambled: `{cipher_scrambled}` | Type `!solve <word>`!")
                                    elif choice == 2:
                                        current_active_game = "police"
                                        pt_state = "LOBBY"
                                        pt_players = []
                                        send_msg(irc, CHANNEL, "🚨 Police & Thief Lobby Open! 4 players needed. Type `!joingame`.")
                                    elif choice == 3:
                                        current_active_game = "rps"
                                        send_msg(irc, CHANNEL, "✂️ Rock Paper Scissors Ready! Type `!rps <rock|paper|scissor>`.")
                                    elif choice == 4:
                                        current_active_game = "battle"
                                        battle_active = False
                                        battle_players.clear()
                                        send_msg(irc, CHANNEL, "🔥 Fire & Shield Battle Arena Opened! Type `!join` to enter (Max 2 players).")
                                    elif choice == 5:
                                        current_active_game = "number"
                                        num_target = random.randint(1, 100)
                                        send_msg(irc, CHANNEL, "🔢 Number Guessing Started! Guess 1-100 via `!guessnum <number>`.")
                                except ValueError:
                                    pass
                                continue

                            # ================= GAME ROUTING =================
                            if current_active_game == "cipher" and msg_lower.startswith("!solve "):
                                guess = msg_full.split()[1].upper()
                                if guess == cipher_word:
                                    u = sender.lower()
                                    game_leaderboards[1][u] = game_leaderboards[1].get(u, 0) + 10
                                    overall_leaderboard[u] = overall_leaderboard.get(u, 0) + 10
                                    send_msg(irc, CHANNEL, f"🎉 {sender} solved the cipher! (+10pts)")
                                    current_active_game = None
                                continue

                            elif current_active_game == "battle":
                                if msg_lower == "!gamerules":
                                    send_msg(irc, CHANNEL, "📜 --- FIRE & SHIELD BATTLE RULES ---")
                                    send_msg(irc, CHANNEL, "❤️ HP: 1000. 💥 Attack: !fire <name> (70 dmg, 15% crit for 150 dmg). 🩸 Bleeding: -50 HP/sec. 🛡️ Shield: !shield.")
                                    continue

                                elif msg_lower == "!join":
                                    if sender.lower() in battle_ban_list or battle_active or sender in battle_players:
                                        continue
                                    battle_players[sender] = {"hp": 1000, "shield": False, "bleeding": False, "last_bleed_tick": 0, "last_attack_time": 0}
                                    send_msg(irc, CHANNEL, f"⚔️ **{sender}** entered the arena! ({len(battle_players)}/2)")

                                    if len(battle_players) == 2:
                                        battle_active = True
                                        p_list = list(battle_players.keys())
                                        send_msg(irc, CHANNEL, f"🚀 **BATTLE START!** **{p_list[0]}** vs **{p_list[1]}**! Type `!fire <name>` or `!shield`!")
                                    continue

                                elif msg_lower.startswith("!fire "):
                                    if not battle_active or sender not in battle_players:
                                        continue
                                    target_input = msg_full[6:].strip()
                                    matched_target = next((p for p in battle_players if p.lower() == target_input.lower()), None)
                                    if not matched_target or matched_target == sender:
                                        continue

                                    attacker = battle_players[sender]
                                    victim = battle_players[matched_target]

                                    if current_time - attacker["last_attack_time"] < 4:
                                        continue

                                    attacker["last_attack_time"] = current_time
                                    if attacker["shield"]:
                                        attacker["shield"] = False

                                    send_msg(irc, CHANNEL, f"🔥💥 **{sender} launched an aggressive assault against {matched_target}!**")

                                    if victim["shield"]:
                                        victim["shield"] = False
                                        send_msg(irc, CHANNEL, f"🛡️ ✨ **BLOCKED!** {matched_target}'s shield absorbed the attack!")
                                    else:
                                        is_crit = random.random() < 0.15
                                        base_dmg = 150 if is_crit else 70
                                        victim["hp"] -= base_dmg
                                        victim["bleeding"] = True
                                        victim["last_bleed_tick"] = time.time()
                                        send_msg(irc, CHANNEL, f"💥 {matched_target} takes -{base_dmg} HP! Bleeding started (-50 HP/sec).")

                                    if victim["hp"] <= 0:
                                        send_msg(irc, CHANNEL, f"🏆 **👑 {sender} 👑** emerges victorious!")
                                        u = sender.lower()
                                        game_leaderboards[4][u] = game_leaderboards[4].get(u, 0) + 100
                                        overall_leaderboard[u] = overall_leaderboard.get(u, 0) + 100
                                        battle_active = False
                                        battle_players.clear()
                                        current_active_game = None
                                    continue

                                elif msg_lower == "!shield":
                                    if not battle_active or sender not in battle_players:
                                        continue
                                    player = battle_players[sender]
                                    player["shield"] = True
                                    player["bleeding"] = False 
                                    send_msg(irc, CHANNEL, f"🛡️ ✨ **{sender}** raised a shield and stopped bleeding!")
                                    continue

                except (BlockingIOError, ssl.SSLWantReadError):
                    time.sleep(0.1)
        except Exception as e:
            print(f"[!] GamesHere error: {e}. Reconnecting in 10 seconds...")
            time.sleep(10)


# ==========================================
# FLASK ROUTE
# ==========================================
@app.route("/")
def index():
    return "IRC GamesHere & YUMI143 Bots are running 24/7!"


if __name__ == "__main__":
    t_yumi = threading.Thread(target=run_yumi143_bot, daemon=True)
    t_yumi.start()

    t_games = threading.Thread(target=run_gameshere_bot, daemon=True)
    t_games.start()

    app.run(host="0.0.0.0", port=5000)
