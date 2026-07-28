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
IRC_PORT = 6667
CHANNEL = "#chatwithworld"
ADMIN = "Antonio"

# Word pool for Cipher Master (Game 1)
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
            print(f"[*] YUMI143 connecting to {IRC_HOST}:{IRC_PORT}...")
            irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            irc.connect((IRC_HOST, IRC_PORT))
            irc.send(f"NICK {nick}\r\nUSER {nick} 0 * :YUMI Broadcast Bot\r\n".encode("utf-8"))
            
            irc.setblocking(False)
            buffer = ""
            joined = False
            last_broadcast = time.time()

            while True:
                current_time = time.time()
                # Broadcast every 3 minutes (180 seconds)
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
                        if not joined and (" 001 " in line or "376" in line):
                            print(f"[*] YUMI143 joining {CHANNEL}...")
                            irc.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))
                            joined = True
                except BlockingIOError:
                    time.sleep(0.5)
        except Exception as e:
            print(f"[!] YUMI143 error: {e}. Reconnecting in 10 seconds...")
            time.sleep(10)


# ==========================================
# BOT A: GamesHere (All 5 Games & Core Loop)
# ==========================================
def run_gameshere_bot():
    nick = "GamesHere"
    
    # Global Leaderboards: game_leaderboards[game_num][username] = score
    game_leaderboards = {1: {}, 2: {}, 3: {}, 4: {}, 5: {}}
    overall_leaderboard = {}
    
    # State flags
    game_mode_active = True
    current_active_game = None # Can be: "cipher", "police", "rps", "battle", "number"
    
    # Game 1 State (Cipher)
    cipher_word = None
    cipher_scrambled = None

    # Game 2 State (Police & Thief)
    pt_state = "IDLE"
    pt_players = []
    pt_police = ""
    pt_thief = ""

    # Game 4 State (Fire & Shield Battle Bot Integration)
    battle_ban_list = set()
    battle_players = {}  # {username: {"hp": 1000, "shield": False, "bleeding": False, "last_bleed_tick": 0, "last_attack_time": 0}}
    battle_active = False

    # Game 5 State (Number Guessing)
    num_target = 0

    def send_msg(irc_socket, target, text):
        print(f">> GamesHere to {target}: {text}")
        irc_socket.send(f"PRIVMSG {target} :{text}\r\n".encode("utf-8"))

    while True:
        try:
            print(f"[*] GamesHere connecting to {IRC_HOST}:{IRC_PORT}...")
            irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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

                        if not joined and (" 001 " in line or "376" in line):
                            print(f"[*] GamesHere joining {CHANNEL}...")
                            irc.send(f"JOIN {CHANNEL}\r\n".encode("utf-8"))
                            joined = True

                        if f"PRIVMSG {CHANNEL}" in line:
                            parts = line.split("!")
                            if not parts: continue
                            sender = parts[0][1:]
                            msg_full = line.split(f"PRIVMSG {CHANNEL} :")[-1].strip()
                            msg_lower = msg_full.lower()

                            # ================= ADMIN CONTROLS (Antonio) =================
                            if msg_lower == "!gamemodeon":
                                if sender.lower() == ADMIN.lower():
                                    game_mode_active = True
                                    send_msg(irc, CHANNEL, "🎮 GamesHere mode is now ENABLED! Let the games begin! 🚀")
                                else:
                                    send_msg(irc, CHANNEL, f"❌ Access Denied, {sender}. Only {ADMIN} can use this command.")
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

                            elif msg_lower.startswith("!setrankov "):
                                if sender.lower() == ADMIN.lower():
                                    parts_cmd = msg_full.split()
                                    if len(parts_cmd) == 3:
                                        target_u, val = parts_cmd[1].lower(), int(parts_cmd[2])
                                        overall_leaderboard[target_u] = val
                                        send_msg(irc, CHANNEL, f"🛠️ Overall score for {target_u} set to {val}pts!")
                                else:
                                    send_msg(irc, CHANNEL, f"❌ Access Denied, {sender}.")
                                continue

                            elif msg_lower.startswith("!setrank") and len(msg_lower) > 8 and msg_lower[8].isdigit():
                                if sender.lower() == ADMIN.lower():
                                    g_idx = int(msg_lower[8])
                                    parts_cmd = msg_full.split()
                                    if len(parts_cmd) == 3 and 1 <= g_idx <= 5:
                                        target_u, val = parts_cmd[1].lower(), int(parts_cmd[2])
                                        game_leaderboards[g_idx][target_u] = val
                                        send_msg(irc, CHANNEL, f"🛠️ Game {g_idx} score for {target_u} set to {val}pts!")
                                else:
                                    send_msg(irc, CHANNEL, f"❌ Access Denied, {sender}.")
                                continue

                            if not game_mode_active:
                                continue

                            # ================= GENERAL NAVIGATION =================
                            if msg_lower == "!gamelist":
                                send_msg(irc, CHANNEL, "📋 AVAILABLE GAMES: [1] Cipher Master | [2] Police & Thief | [3] Rock Paper Scissors | [4] Fire & Shield Battle | [5] Number Guessing. Use !ch <number> to launch!")
                                continue

                            elif msg_lower.startswith("!howtoplay "):
                                try:
                                    g_num = int(msg_lower.split()[1])
                                    if g_num == 1:
                                        send_msg(irc, CHANNEL, "📜 Cipher Master: Unscramble the word using !solve <word>. (+10pts)")
                                    elif g_num == 2:
                                        send_msg(irc, CHANNEL, "📜 Police & Thief: 4 players type !joingame. Police accuses using !thief <username>. (+100pts)")
                                    elif g_num == 3:
                                        send_msg(irc, CHANNEL, "📜 RPS: Duel the bot via !rps <rock|paper|scissor>. (+10pts)")
                                    elif g_num == 4:
                                        send_msg(irc, CHANNEL, "📜 Fire & Shield Battle: Type !ch 4 then !join to enter. Use !fire <name> and !shield. (+100pts)")
                                    elif g_num == 5:
                                        send_msg(irc, CHANNEL, "📜 Number Guessing: Guess numbers 1-100 via !guessnum <number>. (+10pts)")
                                    else:
                                        send_msg(irc, CHANNEL, "❌ Invalid game number (choose 1-5).")
                                except ValueError:
                                    send_msg(irc, CHANNEL, "❌ Usage: !howtoplay <1-5>")
                                continue

                            elif msg_lower == "!ovrank":
                                if not overall_leaderboard:
                                    send_msg(irc, CHANNEL, "🏆 Overall Leaderboard is empty!")
                                else:
                                    sorted_ov = sorted(overall_leaderboard.items(), key=lambda x: x[1], reverse=True)[:5]
                                    send_msg(irc, CHANNEL, f"🏆 OVERALL TOP 5: {' | '.join([f'{u}({s}pts)' for u, s in sorted_ov])}")
                                continue

                            elif msg_lower.startswith("!gamerank "):
                                try:
                                    g_num = int(msg_lower.split()[1])
                                    if 1 <= g_num <= 5:
                                        board = game_leaderboards[g_num]
                                        if not board:
                                            send_msg(irc, CHANNEL, f"🏆 Game {g_num} Leaderboard is empty!")
                                        else:
                                            sorted_g = sorted(board.items(), key=lambda x: x[1], reverse=True)[:5]
                                            send_msg(irc, CHANNEL, f"🏆 Game {g_num} TOP 5: {' | '.join([f'{u}({s}pts)' for u, s in sorted_g])}")
                                    else:
                                        send_msg(irc, CHANNEL, "❌ Choose game rank between 1 and 5.")
                                except ValueError:
                                    send_msg(irc, CHANNEL, "❌ Usage: !gamerank <1-5>")
                                continue

                            # ================= SELECT GAME (!ch <1-5>) =================
                            elif msg_lower.startswith("!ch "):
                                try:
                                    choice = int(msg_lower.split()[1])
                                    if current_active_game is not None:
                                        send_msg(irc, CHANNEL, f"❌ A game is already active! Finish it or wait for admin to !cancelgame.")
                                        continue

                                    if choice == 1:
                                        current_active_game = "cipher"
                                        cipher_word = random.choice(CIPHER_POOL)
                                        chars = list(cipher_word)
                                        random.shuffle(chars)
                                        cipher_scrambled = "".join(chars)
                                        send_msg(irc, CHANNEL, f"🌀 Cipher Master Started! Scrambled Word: `{cipher_scrambled}` | Type `!solve <word>`!")
                                    elif choice == 2:
                                        current_active_game = "police"
                                        pt_state = "LOBBY"
                                        pt_players = []
                                        send_msg(irc, CHANNEL, "🚨 Police & Thief Lobby Open! 4 players needed. Type `!joingame` to enter.")
                                    elif choice == 3:
                                        current_active_game = "rps"
                                        send_msg(irc, CHANNEL, "✂️ Rock Paper Scissors Ready! Type `!rps <rock|paper|scissor>` to play.")
                                    elif choice == 4:
                                        current_active_game = "battle"
                                        battle_active = False
                                        battle_players.clear()
                                        send_msg(irc, CHANNEL, "🔥 Fire & Shield Battle Arena Opened! Type `!join` to enter (Max 2 players).")
                                    elif choice == 5:
                                        current_active_game = "number"
                                        num_target = random.randint(1, 100)
                                        send_msg(irc, CHANNEL, "🔢 Number Guessing Started! Guess a number between 1 and 100 using `!guessnum <number>`.")
                                    else:
                                        send_msg(irc, CHANNEL, "❌ Invalid game selection number. Choose 1 to 5.")
                                except ValueError:
                                    send_msg(irc, CHANNEL, "❌ Usage: !ch <1-5>")
                                continue

                            # ================= GAME ROUTING LOGIC =================
                            # GAME 1: Cipher Master
                            if current_active_game == "cipher" and msg_lower.startswith("!solve "):
                                guess = msg_full.split()[1].upper()
                                if guess == cipher_word:
                                    u = sender.lower()
                                    game_leaderboards[1][u] = game_leaderboards[1].get(u, 0) + 10
                                    overall_leaderboard[u] = overall_leaderboard.get(u, 0) + 10
                                    send_msg(irc, CHANNEL, f"🎉 {sender} solved the cipher! Word was {cipher_word}. (+10pts)")
                                    current_active_game = None
                                else:
                                    send_msg(irc, CHANNEL, f"❌ Incorrect cipher guess, {sender}!")
                                continue

                            # GAME 2: Police & Thief
                            elif current_active_game == "police":
                                if msg_lower == "!joingame" and pt_state == "LOBBY":
                                    if sender not in pt_players:
                                        pt_players.append(sender)
                                        send_msg(irc, CHANNEL, f"🎮 {sender} joined Police & Thief! ({len(pt_players)}/4)")
                                        if len(pt_players) == 4:
                                            roles = ["Police", "Thief", "Innocent", "Innocent"]
                                            random.shuffle(roles)
                                            pt_assignments = dict(zip(pt_players, roles))
                                            for p, r in pt_assignments.items():
                                                if r == "Police": pt_police = p
                                                elif r == "Thief": pt_thief = p
                                            send_msg(irc, CHANNEL, f"📢 4 Players gathered! Police is **{pt_police}**. Use !thief <username> to accuse!")
                                            pt_state = "FIRST_GUESS"
                                    continue

                                elif msg_lower == "!giveup" and pt_state == "CHOICE_WINDOW" and sender == pt_police:
                                    send_msg(irc, CHANNEL, f"🏳️ {pt_police} gave up. Thief {pt_thief} wins the round!")
                                    game_leaderboards[2][pt_thief] = game_leaderboards[2].get(pt_thief, 0) + 100
                                    overall_leaderboard[pt_thief] = overall_leaderboard.get(pt_thief, 0) + 100
                                    current_active_game = None
                                    pt_state = "IDLE"
                                    continue

                                elif pt_state in ["FIRST_GUESS", "SECOND_GUESS"] and msg_lower.startswith("!thief "):
                                    if sender != pt_police:
                                        send_msg(irc, CHANNEL, f"❌ Only the assigned Police ({pt_police}) can make an accusation.")
                                        continue
                                    target = msg_full.split()[1]
                                    if pt_state == "FIRST_GUESS":
                                        if target.lower() == pt_thief.lower():
                                            send_msg(irc, CHANNEL, f"🎉 Caught! {pt_thief} was the Thief! Police gets +100pts.")
                                            game_leaderboards[2][pt_police] = game_leaderboards[2].get(pt_police, 0) + 100
                                            overall_leaderboard[pt_police] = overall_leaderboard.get(pt_police, 0) + 100
                                            current_active_game = None
                                            pt_state = "IDLE"
                                        else:
                                            send_msg(irc, CHANNEL, f"❌ Wrong! {target} is innocent. Type !giveup or !reqguess.")
                                            pt_state = "CHOICE_WINDOW"
                                    elif pt_state == "SECOND_GUESS":
                                        if target.lower() == pt_thief.lower():
                                            send_msg(irc, CHANNEL, f"🎉 2nd guess correct! {pt_thief} was caught!")
                                        else:
                                            send_msg(irc, CHANNEL, f"💥 Wrong again! Real thief was {pt_thief}.")
                                            game_leaderboards[2][pt_thief] = game_leaderboards[2].get(pt_thief, 0) + 100
                                            overall_leaderboard[pt_thief] = overall_leaderboard.get(pt_thief, 0) + 100
                                        current_active_game = None
                                        pt_state = "IDLE"
                                    continue

                            # GAME 3: Rock Paper Scissors
                            elif current_active_game == "rps" and msg_lower.startswith("!rps "):
                                choice_arg = msg_lower.split()[1]
                                if choice_arg in ["rock", "paper", "scissor"]:
                                    bot_choice = random.choice(["rock", "paper", "scissor"])
                                    u = sender.lower()
                                    if choice_arg == bot_choice:
                                        send_msg(irc, CHANNEL, f"🤝 RPS Tie! Both chose {bot_choice}.")
                                    elif (choice_arg == "rock" and bot_choice == "scissor") or \
                                         (choice_arg == "paper" and bot_choice == "rock") or \
                                         (choice_arg == "scissor" and bot_choice == "paper"):
                                        game_leaderboards[3][u] = game_leaderboards[3].get(u, 0) + 10
                                        overall_leaderboard[u] = overall_leaderboard.get(u, 0) + 10
                                        send_msg(irc, CHANNEL, f"🎉 {sender} wins! Bot chose {bot_choice}. (+10pts)")
                                        current_active_game = None
                                    else:
                                        send_msg(irc, CHANNEL, f"❌ Bot wins! Bot chose {bot_choice}.")
                                        current_active_game = None
                                continue

                            # GAME 4: Fire & Shield Battle Bot Integration
                            elif current_active_game == "battle":
                                if msg_lower == "!gamerules":
                                    send_msg(irc, CHANNEL, "📜 --- FIRE & SHIELD BATTLE RULES ---")
                                    send_msg(irc, CHANNEL, "❤️ HP: Every player starts with 1000 HP. Max 2 players.")
                                    send_msg(irc, CHANNEL, "💥 Attack: Use `!fire <name>` to inflict 70 DMG (15% crit for 150 DMG).")
                                    send_msg(irc, CHANNEL, "🩸 Bleeding: Getting hit makes you bleed **-50 HP every single second**!")
                                    send_msg(irc, CHANNEL, "🛡️ Shield: Use `!shield` to stop bleeding instantly and block attacks.")
                                    continue

                                elif msg_lower == "!join":
                                    if sender.lower() in battle_ban_list:
                                        send_msg(irc, CHANNEL, "❌ You are banned.")
                                        continue
                                    if battle_active:
                                        send_msg(irc, CHANNEL, "❌ A match is already running. Please wait.")
                                        continue
                                    if sender in battle_players:
                                        send_msg(irc, CHANNEL, f"❌ You already joined ({len(battle_players)}/2).")
                                        continue
                                    
                                    battle_players[sender] = {
                                        "hp": 1000,
                                        "shield": False,
                                        "bleeding": False,
                                        "last_bleed_tick": 0,
                                        "last_attack_time": 0
                                    }
                                    send_msg(irc, CHANNEL, f"⚔️ **{sender}** entered the arena! ({len(battle_players)}/2)")

                                    if len(battle_players) == 2:
                                        battle_active = True
                                        p_list = list(battle_players.keys())
                                        send_msg(irc, CHANNEL, f"🚀 **BATTLE START!** **{p_list[0]}** vs **{p_list[1]}**!")
                                        send_msg(irc, CHANNEL, "🔥 Type `!fire <name>` to strike or `!shield` to block and stop bleeding!")
                                    continue

                                elif msg_lower.startswith("!fire "):
                                    if not battle_active:
                                        continue
                                    if sender not in battle_players:
                                        send_msg(irc, CHANNEL, "❌ You are not a player in this match.")
                                        continue

                                    target_input = msg_full[6:].strip()
                                    matched_target = next((p for p in battle_players if p.lower() == target_input.lower()), None)

                                    if not matched_target:
                                        send_msg(irc, CHANNEL, "❌ Target player not found in this match.")
                                        continue
                                    if matched_target == sender:
                                        send_msg(irc, CHANNEL, "❌ You can't attack yourself!")
                                        continue

                                    attacker = battle_players[sender]
                                    victim = battle_players[matched_target]

                                    if current_time - attacker["last_attack_time"] < 4:
                                        time_left = int(4 - (current_time - attacker["last_attack_time"]))
                                        send_msg(irc, CHANNEL, f"⏳ **{sender}**, you must wait {time_left}s between attacks or have the opponent strike you first!")
                                        continue

                                    attacker["last_attack_time"] = current_time
                                    
                                    if attacker["shield"]:
                                        attacker["shield"] = False
                                        send_msg(irc, CHANNEL, f"⚡ **{sender}** dropped their shield to execute an attack!")

                                    send_msg(irc, CHANNEL, f"🔥💥 **💥 BOOM! {sender} launched an aggressive assault against {matched_target}!** 💥🔥")

                                    if victim["shield"]:
                                        victim["shield"] = False
                                        send_msg(irc, CHANNEL, f"🛡️ ✨ **BLOCKED!** {matched_target}'s shield completely absorbed the attack and shattered!")
                                    else:
                                        is_crit = random.random() < 0.15
                                        base_dmg = 150 if is_crit else 70
                                        
                                        victim["hp"] -= base_dmg
                                        victim["bleeding"] = True
                                        victim["last_bleed_tick"] = time.time()

                                        if is_crit:
                                            send_msg(irc, CHANNEL, f"⚡ **CRITICAL HIT!** {matched_target} takes a massive **-150 HP** blast!")
                                        else:
                                            send_msg(irc, CHANNEL, f"💥 Hit registered! {matched_target} takes **-70 HP** physical damage!")

                                        send_msg(irc, CHANNEL, f"🩸 {matched_target} is now bleeding profusely! Quick, use `!shield` to stop the bleeding!")

                                    if victim["hp"] <= 0:
                                        send_msg(irc, CHANNEL, f"💀 **{matched_target}** has been thoroughly wiped out by {sender}!")
                                        send_msg(irc, CHANNEL, f"🏆 **👑 {sender} 👑** emerges victorious!")
                                        u = sender.lower()
                                        game_leaderboards[4][u] = game_leaderboards[4].get(u, 0) + 100
                                        overall_leaderboard[u] = overall_leaderboard.get(u, 0) + 100
                                        battle_active = False
                                        battle_players.clear()
                                        current_active_game = None
                                    continue

                                elif msg_lower == "!shield":
                                    if not battle_active:
                                        continue
                                    if sender not in battle_players:
                                        continue

                                    player = battle_players[sender]
                                    if player["shield"]:
                                        send_msg(irc, CHANNEL, f"🛡️ **{sender}**, your particle shield is already fully activated!")
                                        continue

                                    player["shield"] = True
                                    was_bleeding = player["bleeding"]
                                    player["bleeding"] = False 
                                    
                                    if was_bleeding:
                                        send_msg(irc, CHANNEL, f"🛡️ ✅ **{sender}** deployed their shield! Bleeding stopped safely. (HP: {player['hp']}/1000)")
                                    else:
                                        send_msg(irc, CHANNEL, f"🛡️ ✨ **{sender}** raises an emergency shield to block the next attack!")
                                    continue

                            # GAME 5: Number Guessing
                            elif current_active_game == "number" and msg_lower.startswith("!guessnum "):
                                try:
                                    val = int(msg_full.split()[1])
                                    if val == num_target:
                                        u = sender.lower()
                                        game_leaderboards[5][u] = game_leaderboards[5].get(u, 0) + 10
                                        overall_leaderboard[u] = overall_leaderboard.get(u, 0) + 10
                                        send_msg(irc, CHANNEL, f"🎉 {sender} guessed the correct number {num_target}! (+10pts)")
                                        current_active_game = None
                                    elif val < num_target:
                                        send_msg(irc, CHANNEL, f"📈 Higher than {val}!")
                                    else:
                                        send_msg(irc, CHANNEL, f"📉 Lower than {val}!")
                                except ValueError:
                                    pass
                                continue

                except BlockingIOError:
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
