"""
GamesHere - Unified IRC Games Bot
==================================
Combines 4 games under one bot with a shared, uniform meta-layer:
  1. Cipher Scramble
  2. Police & Thief
  3. Fire & Shield Battle
  4. Hide & Seek (LukaMari)

Core game mechanics are preserved exactly as originally designed.
Only bot-wide/meta systems (points, bans, admin tools, help) are unified.
"""

import socket
import time
import random
import string
import sys

# ============================================================
# CONFIG
# ============================================================
HOST = "irc.hybridirc.com"
PORT = 6667  # Plaintext, matches server compatibility requirements
NICK = "GamesHere"
CHANNEL = "#chatwithworld"
ADMIN = "Antonio"

RANK_DISPLAY_COUNT = 5
LOBBY_TIME_DEFAULT = 30
HIDING_TIME = 15
DUEL_REVEAL_DELAY = 2
DUEL_TIMEOUT = 7
PT_REVEAL_DELAY = 1.5  # non-blocking delay before Police & Thief roles are revealed

WORD_POOL = [
    "APPLE", "BANANA", "CHERRY", "DOG", "CAT", "MOUSE", "HOUSE", "PLANE", "TRAIN", "BOAT",
    "SUN", "MOON", "STAR", "CLOUD", "RAIN", "SNOW", "WIND", "FIRE", "WATER", "EARTH",
    "PHONE", "TABLE", "CHAIR", "DESK", "LAMP", "BOOK", "PEN", "PAPER", "KEY", "LOCK",
    "DOOR", "WINDOW", "WALL", "ROOF", "FLOOR", "BED", "SOFA", "RUG", "PILLOW", "BLANKET",
    "SHIRT", "PANTS", "SHOES", "HAT", "GLOVE", "SOCKS", "COAT", "DRESS", "SKIRT", "BELT",
    "BREAD", "MILK", "EGG", "MEAT", "FISH", "RICE", "SOUP", "TEA", "COFFEE", "JUICE",
    "HAPPY", "SAD", "ANGRY", "CALM", "BRAVE", "LUCKY", "FAST", "SLOW", "BIG", "SMALL",
    "RED", "BLUE", "GREEN", "YELLOW", "BLACK", "WHITE", "GOLD", "SILVER", "BROWN", "GRAY",
    "DANCE", "SING", "JUMP", "RUN", "WALK", "SLEEP", "EAT", "DRINK", "READ", "WRITE",
    "STORY", "SONG", "GAME", "PLAY", "WORK", "REST", "TIME", "LIFE", "LOVE", "PEACE"
]

LOCATIONS = {f"loc{i}": name for i, name in enumerate([
    "Bathroom", "Under Dining Table", "Terraced Balcony", "Store Room",
    "Rooftop Water Tank", "Basement Garage", "Under the Staircase", "Attic Hatch",
    "Behind the long Curtains", "Inside the Wardrobe", "Kitchen Pantry",
    "Under the Master Bed", "Library Bookshelf", "Guest Room Closet", "Home Theater Setup"
], 1)}

GAME_KEYS = {1: "cipher", 2: "police_thief", 3: "fire_shield", 4: "hide_seek"}
GAME_NAMES = {
    1: "Cipher Scramble",
    2: "Police & Thief",
    3: "Fire & Shield Battle",
    4: "Hide & Seek (LukaMari)"
}

GAME_TRIGGER_COMMANDS = {
    "!cipher", "!solve", "!cq", "!giveup",
    "!joingame", "!thief", "!reqguess",
    "!join", "!fire", "!shield",
    "!play", "!check", "!aaspas", "!dhyapp", "!hide"
}

ADMIN_ONLY_META_CMDS = {
    "!gmon", "!gmoff", "!cancelgame", "!freeze", "!unfreeze",
    "!banforever", "!forgive", ".passmsg", "!superhowtoplay"
}


# ============================================================
# SHARED BOT STATE
# ============================================================
class BotState:
    def __init__(self):
        self.current_game = None       # None | "cipher" | "police_thief" | "fire_shield" | "hide_seek"
        self.frozen = False
        self.games_enabled = True
        self.ban_list = set()
        self.scores = {}               # name_lower -> {"cipher":0,"police_thief":0,"fire_shield":0,"hide_seek":0,"total":0}
        self.selected_game = None      # set via !ch


bot = BotState()


def ensure_player(name):
    key = name.lower()
    if key not in bot.scores:
        bot.scores[key] = {"cipher": 0, "police_thief": 0, "fire_shield": 0, "hide_seek": 0, "total": 0, "display": name}
    return bot.scores[key]


def add_points(name, game_key, pts):
    rec = ensure_player(name)
    rec["display"] = name
    if pts:
        rec[game_key] += pts
        rec["total"] = rec["cipher"] + rec["police_thief"] + rec["fire_shield"] + rec["hide_seek"]


def set_points(name, game_key, pts):
    rec = ensure_player(name)
    rec["display"] = name
    rec[game_key] = pts
    rec["total"] = rec["cipher"] + rec["police_thief"] + rec["fire_shield"] + rec["hide_seek"]


def is_banned(name):
    return name.lower() in bot.ban_list


def is_game_command(msg_lower):
    parts = msg_lower.split()
    if not parts:
        return False
    return parts[0] in GAME_TRIGGER_COMMANDS


# ============================================================
# IRC SEND HELPERS
# ============================================================
def send_raw(irc, msg):
    try:
        irc.send(f"{msg}\r\n".encode("utf-8"))
    except Exception as e:
        print(f"[!] Send error: {e}")


def send_msg(irc, target, msg):
    send_raw(irc, f"PRIVMSG {target} :{msg}")


def send_notice(irc, target, msg):
    send_raw(irc, f"NOTICE {target} :{msg}")


def send_lines(irc, target, lines):
    for line in lines:
        send_msg(irc, target, line if line else "\u200b")


# ============================================================
# GAME STATE: CIPHER SCRAMBLE
# ============================================================
cipher_state = {"active_word": None, "scrambled": None, "autogame": False}


def scramble_word(word):
    chars = list(word)
    random.shuffle(chars)
    return "".join(chars)


def reset_cipher():
    cipher_state["active_word"] = None
    cipher_state["scrambled"] = None


def start_cipher_round(irc):
    word = random.choice(WORD_POOL)
    cipher_state["active_word"] = word
    cipher_state["scrambled"] = scramble_word(word)
    send_msg(irc, CHANNEL, f"🌀 Cipher: `{cipher_state['scrambled']}` | Type `!solve <word>`!")


def handle_cipher_action(irc, sender, cmd, args):
    if cmd == "!solve":
        if not cipher_state["active_word"]:
            send_msg(irc, CHANNEL, "⚠️ Type `!cipher` first. 🏁")
            return
        if not args:
            send_msg(irc, CHANNEL, "❌ Usage: !solve <word>")
            return
        guess = args[0].lower()
        if guess == cipher_state["active_word"].lower():
            add_points(sender, "cipher", 10)
            rec = ensure_player(sender)
            send_msg(irc, CHANNEL, f"🎉 {sender} got it! Word: {cipher_state['active_word']} | Cipher Score: {rec['cipher']}pts 🏆")
            reset_cipher()
            if cipher_state["autogame"]:
                new_word = random.choice(WORD_POOL)
                cipher_state["active_word"] = new_word
                cipher_state["scrambled"] = scramble_word(new_word)
                send_msg(irc, CHANNEL, f"🤖 Next round: `{cipher_state['scrambled']}`")
            else:
                bot.current_game = None
        else:
            send_msg(irc, CHANNEL, "❌ Wrong! Focus. 🕵️‍♂️")
    elif cmd == "!cq":
        if cipher_state["active_word"]:
            send_msg(irc, CHANNEL, f"🔍 Current: `{cipher_state['scrambled']}`")
        else:
            send_msg(irc, CHANNEL, "⚠️ No active cipher. Type `!cipher` to start.")
    elif cmd == "!giveup":
        if cipher_state["active_word"]:
            send_msg(irc, CHANNEL, f"🏳️ Revealed: {cipher_state['active_word']}. No points awarded.")
            reset_cipher()
            bot.current_game = None
        else:
            send_msg(irc, CHANNEL, "⚠️ No active cipher to give up on.")


# ============================================================
# GAME STATE: POLICE & THIEF
# ============================================================
pt_state = {
    "phase": "IDLE",  # IDLE, PENDING_REVEAL, FIRST_GUESS, CHOICE_WINDOW, SECOND_GUESS
    "players": [], "police": None, "thief": None, "innocents": [],
    "first_wrong": None, "reveal_at": None
}


def reset_pt():
    pt_state.update({
        "phase": "IDLE", "players": [], "police": None, "thief": None, "innocents": [],
        "first_wrong": None, "reveal_at": None
    })


def handle_pt_joingame(irc, sender):
    if pt_state["phase"] != "IDLE":
        send_msg(irc, CHANNEL, "❌ A round is currently active.")
        return
    if sender in pt_state["players"]:
        send_msg(irc, CHANNEL, f"❌ You are already in the lobby ({len(pt_state['players'])}/4).")
        return
    pt_state["players"].append(sender)
    send_msg(irc, CHANNEL, f"🎮 {sender} joined! ({len(pt_state['players'])}/4 players)")
    if len(pt_state["players"]) == 4:
        send_msg(irc, CHANNEL, "🚀 4 Players gathered! Distributing roles...")
        pt_state["phase"] = "PENDING_REVEAL"
        pt_state["reveal_at"] = time.time() + PT_REVEAL_DELAY


def reveal_pt_roles(irc):
    roles = ["Police", "Thief", "Innocent", "Innocent"]
    random.shuffle(roles)
    assignments = dict(zip(pt_state["players"], roles))
    innocents, police, thief = [], None, None
    for p, r in assignments.items():
        if r == "Police":
            police = p
        elif r == "Thief":
            thief = p
        else:
            innocents.append(p)
    pt_state["police"] = police
    pt_state["thief"] = thief
    pt_state["innocents"] = innocents
    pt_state["reveal_at"] = None

    send_notice(irc, thief, "🥷 You are the THIEF! Blend in.")
    for inc in innocents:
        send_notice(irc, inc, "👤 You are a Normal Innocent Person. (Worth 50 points)")

    send_msg(irc, CHANNEL, f"📢 Roles sent via NOTICE! 👮 The POLICE is **{police}**!")
    suspects = [p for p in pt_state["players"] if p != police]
    send_msg(irc, CHANNEL, f"🕵️‍♂️ {police}, guess the Thief! Suspects: {', '.join(suspects)}")
    send_msg(irc, CHANNEL, "👉 Take your 1st guess with: !thief <username>")
    pt_state["phase"] = "FIRST_GUESS"


def end_pt_round(irc, awards):
    for player, pts in awards.items():
        add_points(player, "police_thief", pts)
    reset_pt()
    bot.current_game = None


def handle_pt_action(irc, sender, cmd, args):
    phase = pt_state["phase"]

    if cmd == "!thief":
        if phase not in ("FIRST_GUESS", "SECOND_GUESS"):
            return
        if sender != pt_state["police"]:
            send_msg(irc, CHANNEL, f"❌ Only the Police ({pt_state['police']}) can make an accusation.")
            return
        if not args:
            send_msg(irc, CHANNEL, "❌ Usage: !thief <username>")
            return
        target_guess = args[0]
        matched = next((p for p in pt_state["players"] if p.lower() == target_guess.lower()), None)
        if not matched or matched == pt_state["police"] or matched == pt_state["first_wrong"]:
            send_msg(irc, CHANNEL, "❌ Invalid target selection.")
            return

        if phase == "FIRST_GUESS":
            if matched == pt_state["thief"]:
                send_msg(irc, CHANNEL, f"🎉 PERFECT! **{pt_state['thief']}** was the Thief! Perfect capture on the 1st try.")
                awards = {pt_state["police"]: 100, pt_state["thief"]: 0}
                for inc in pt_state["innocents"]:
                    awards[inc] = 50
                send_msg(irc, CHANNEL, "💰 Round Over Scores: Police (+100) | Innocents (+50) | Thief (0)")
                end_pt_round(irc, awards)
            else:
                pt_state["first_wrong"] = matched
                send_msg(irc, CHANNEL, f"❌ WRONG! **{matched}** is Innocent!")
                send_msg(irc, CHANNEL, f"⚖️ {pt_state['police']}, choose your fate:")
                send_msg(irc, CHANNEL, "🔹 Type **!giveup** to accept -100 and end the round (Thief gets +100).")
                send_msg(irc, CHANNEL, "🔹 Type **!reqguess** to gamble a 2nd guess (Correct = 0 | Wrong = -200!).")
                pt_state["phase"] = "CHOICE_WINDOW"
            return

        if phase == "SECOND_GUESS":
            awards = {}
            for inc in pt_state["innocents"]:
                awards[inc] = 50
            if matched == pt_state["thief"]:
                send_msg(irc, CHANNEL, f"🎉 CAUGHT! **{pt_state['thief']}** was the Thief! 2nd guess was correct.")
                send_msg(irc, CHANNEL, "⚖️ Police cleared their record! Net result: 0 points.")
                awards[pt_state["police"]] = 0
                awards[pt_state["thief"]] = 0
            else:
                send_msg(irc, CHANNEL, f"💥 DISASTER! **{matched}** was also innocent! The real Thief was **{pt_state['thief']}**!")
                send_msg(irc, CHANNEL, f"💀 Double Penalty! {pt_state['police']} drops to -200pts for this round.")
                awards[pt_state["police"]] = -200
                awards[pt_state["thief"]] = 100
            send_msg(irc, CHANNEL, "🔄 Game over! Use !joingame for a new round.")
            end_pt_round(irc, awards)
            return

    elif cmd == "!giveup":
        if phase != "CHOICE_WINDOW" or sender != pt_state["police"]:
            return
        send_msg(irc, CHANNEL, f"🏳️ {pt_state['police']} gives up. The Thief **{pt_state['thief']}** wins!")
        awards = {pt_state["police"]: -100, pt_state["thief"]: 100}
        for inc in pt_state["innocents"]:
            awards[inc] = 50
        end_pt_round(irc, awards)

    elif cmd == "!reqguess":
        if phase != "CHOICE_WINDOW" or sender != pt_state["police"]:
            return
        send_msg(irc, CHANNEL, f"🎲 {pt_state['police']} gambles a 2nd guess! (Win = 0 | Lose = -200!)")
        rem_suspects = [p for p in pt_state["players"] if p != pt_state["police"] and p != pt_state["first_wrong"]]
        send_msg(irc, CHANNEL, f"🕵️‍♂️ Final suspects remaining: {', '.join(rem_suspects)}")
        send_msg(irc, CHANNEL, "👉 Use: !thief <username>")
        pt_state["phase"] = "SECOND_GUESS"


def tick_police_thief(irc, now):
    if pt_state["phase"] == "PENDING_REVEAL" and pt_state["reveal_at"] and now >= pt_state["reveal_at"]:
        reveal_pt_roles(irc)


# ============================================================
# GAME STATE: FIRE & SHIELD BATTLE
# ============================================================
fs_state = {"active": False, "players": {}}


def reset_fs():
    fs_state["active"] = False
    fs_state["players"] = {}


def handle_fs_join(irc, sender):
    if fs_state["active"]:
        send_msg(irc, CHANNEL, "❌ A match is already running. Please wait.")
        return
    if sender in fs_state["players"]:
        send_msg(irc, CHANNEL, f"❌ You already joined ({len(fs_state['players'])}/2).")
        return
    fs_state["players"][sender] = {"hp": 1000, "shield": False, "bleeding": False, "last_bleed_tick": 0, "last_attack_time": 0}
    send_msg(irc, CHANNEL, f"⚔️ **{sender}** entered the arena! ({len(fs_state['players'])}/2)")
    if len(fs_state["players"]) == 2:
        fs_state["active"] = True
        p_list = list(fs_state["players"].keys())
        send_msg(irc, CHANNEL, f"🚀 **BATTLE START!** **{p_list[0]}** vs **{p_list[1]}**!")
        send_msg(irc, CHANNEL, "🔥 Type `!fire <name>` to strike or `!shield` to block and stop bleeding!")


def end_fs_battle(irc, winner, loser):
    add_points(winner, "fire_shield", 100)
    add_points(loser, "fire_shield", -50)
    reset_fs()
    bot.current_game = None


def handle_fs_action(irc, sender, cmd, args):
    if not fs_state["active"]:
        return

    if cmd == "!fire":
        if sender not in fs_state["players"]:
            send_msg(irc, CHANNEL, "❌ You are not a player in this match.")
            return
        if not args:
            send_msg(irc, CHANNEL, "❌ Usage: !fire <username>")
            return
        target_input = args[0]
        matched_target = next((p for p in fs_state["players"] if p.lower() == target_input.lower()), None)
        if not matched_target:
            send_msg(irc, CHANNEL, "❌ Target player not found in this match.")
            return
        if matched_target == sender:
            send_msg(irc, CHANNEL, "❌ You can't attack yourself!")
            return

        attacker = fs_state["players"][sender]
        victim = fs_state["players"][matched_target]
        now = time.time()
        if now - attacker["last_attack_time"] < 4:
            time_left = int(4 - (now - attacker["last_attack_time"]))
            send_msg(irc, CHANNEL, f"⏳ **{sender}**, wait {time_left}s or let the opponent hit you first!")
            return

        attacker["last_attack_time"] = now
        if attacker["shield"]:
            attacker["shield"] = False
            send_msg(irc, CHANNEL, f"⚡ **{sender}** dropped their shield to attack!")

        send_msg(irc, CHANNEL, f"🔥💥 **{sender} launched an assault against {matched_target}!** 💥🔥")

        if victim["shield"]:
            victim["shield"] = False
            send_msg(irc, CHANNEL, f"🛡️ **BLOCKED!** {matched_target}'s shield absorbed the attack and shattered!")
        else:
            is_crit = random.random() < 0.15
            dmg = 150 if is_crit else 70
            victim["hp"] -= dmg
            victim["bleeding"] = True
            victim["last_bleed_tick"] = time.time()
            if is_crit:
                send_msg(irc, CHANNEL, f"⚡ **CRITICAL HIT!** {matched_target} takes -150 HP!")
            else:
                send_msg(irc, CHANNEL, f"💥 Hit! {matched_target} takes -70 HP!")
            send_msg(irc, CHANNEL, f"🩸 {matched_target} is bleeding! Use `!shield` to stop it!")

        if victim["hp"] <= 0:
            send_msg(irc, CHANNEL, f"💀 **{matched_target}** has been wiped out by {sender}!")
            send_msg(irc, CHANNEL, f"🏆 **👑 {sender} 👑** wins! (+100pts) | {matched_target} loses. (-50pts)")
            end_fs_battle(irc, sender, matched_target)

    elif cmd == "!shield":
        if sender not in fs_state["players"]:
            return
        player = fs_state["players"][sender]
        if player["shield"]:
            send_msg(irc, CHANNEL, f"🛡️ **{sender}**, shield already active!")
            return
        player["shield"] = True
        was_bleeding = player["bleeding"]
        player["bleeding"] = False
        if was_bleeding:
            send_msg(irc, CHANNEL, f"🛡️ **{sender}** raised shield! Bleeding stopped. (HP: {player['hp']}/1000)")
        else:
            send_msg(irc, CHANNEL, f"🛡️ **{sender}** raises an emergency shield!")


def tick_fire_shield(irc, now):
    if not fs_state["active"]:
        return
    dead = []
    for name, p in list(fs_state["players"].items()):
        if p["bleeding"]:
            elapsed = now - p["last_bleed_tick"]
            if elapsed >= 1.0:
                ticks = int(elapsed)
                dmg = ticks * 50
                p["hp"] -= dmg
                p["last_bleed_tick"] += ticks
                send_msg(irc, CHANNEL, f"🩸 **{name}** is bleeding! -{dmg} HP. ({p['hp']}/1000)")
                if p["hp"] <= 0:
                    dead.append(name)
    for dead_p in dead:
        survivor = [n for n in fs_state["players"] if n != dead_p]
        send_msg(irc, CHANNEL, f"💀 **{dead_p}** bled out!")
        if survivor:
            winner = survivor[0]
            send_msg(irc, CHANNEL, f"🏆 **👑 {winner} 👑** wins by bleedout! (+100pts) | {dead_p} loses. (-50pts)")
            end_fs_battle(irc, winner, dead_p)
        else:
            reset_fs()
            bot.current_game = None


# ============================================================
# GAME STATE: HIDE & SEEK (LUKAMARI)
# ============================================================
hs_state = {
    "phase": "IDLE", "players": [], "seeker": None,
    "hider_spots": {}, "room_occupants": {}, "eliminated": [],
    "catches": 0, "turns_since_last_find": 0,
    "lobby_start": None, "hiding_start": None, "duel": {},
    "player_limit": 4, "lobby_time": LOBBY_TIME_DEFAULT, "forced_seeker": None
}


def reset_hs(keep_settings=True):
    keep = {}
    if keep_settings:
        keep = {
            "player_limit": hs_state.get("player_limit", 4),
            "lobby_time": hs_state.get("lobby_time", LOBBY_TIME_DEFAULT),
            "forced_seeker": hs_state.get("forced_seeker")
        }
    hs_state.clear()
    hs_state.update({
        "phase": "IDLE", "players": [], "seeker": None,
        "hider_spots": {}, "room_occupants": {}, "eliminated": [],
        "catches": 0, "turns_since_last_find": 0,
        "lobby_start": None, "hiding_start": None, "duel": {},
        "player_limit": keep.get("player_limit", 4),
        "lobby_time": keep.get("lobby_time", LOBBY_TIME_DEFAULT),
        "forced_seeker": keep.get("forced_seeker")
    })


def start_hs_lobby(irc):
    reset_hs(keep_settings=True)
    hs_state["phase"] = "LOBBY"
    hs_state["lobby_start"] = time.time()
    send_msg(irc, CHANNEL, f"📢 Lobby OPEN! Use !play to join. Limit: {hs_state['player_limit']} players. Setup Window: {hs_state['lobby_time']}s.")


def handle_hs_join_lobby(irc, sender):
    if sender in hs_state["players"]:
        send_msg(irc, CHANNEL, f"❌ You are already in the lobby ({len(hs_state['players'])}/{hs_state['player_limit']}).")
        return
    if len(hs_state["players"]) >= hs_state["player_limit"]:
        send_msg(irc, CHANNEL, "❌ Lobby is full.")
        return
    hs_state["players"].append(sender)
    send_msg(irc, CHANNEL, f"✅ Player **{sender}** registered! [{len(hs_state['players'])}/{hs_state['player_limit']}]")


def finalize_lobby(irc):
    if len(hs_state["players"]) < 2:
        send_msg(irc, CHANNEL, "❌ Match Aborted: Not enough players gathered.")
        reset_hs()
        bot.current_game = None
        return
    seeker = hs_state["forced_seeker"] if (hs_state["forced_seeker"] and hs_state["forced_seeker"] in hs_state["players"]) else random.choice(hs_state["players"])
    hs_state["forced_seeker"] = None
    hs_state["players"].remove(seeker)
    hs_state["seeker"] = seeker
    send_msg(irc, CHANNEL, f"👹 Assigned Seeker: **{seeker}**! 15s Hiding phase active. Hiders, PM the bot: !hide loc<1-15>")
    hs_state["phase"] = "HIDING"
    hs_state["hiding_start"] = time.time()


def finalize_hiding(irc):
    idlers = [p for p in hs_state["players"] if p not in hs_state["hider_spots"]]
    for idler in idlers:
        hs_state["players"].remove(idler)
        hs_state["eliminated"].append(idler)
        send_msg(irc, CHANNEL, f"💀 {idler} never hid! ELIMINATED!")
    if not hs_state["players"]:
        send_msg(irc, CHANNEL, f"🏆 Game Over! No one hid. Seeker **{hs_state['seeker']}** wins by default!")
        end_hs_round(irc, sweep=False)
        return
    hs_state["phase"] = "SEEKING"
    send_msg(irc, CHANNEL, f"🔎 The Hunt Begins! **{hs_state['seeker']}**, use !check loc<1-15> to scan rooms.")


def handle_hs_hide(irc, sender, args):
    if hs_state["phase"] != "HIDING":
        return
    if not args or args[0] not in LOCATIONS:
        send_msg(irc, sender, "❌ Usage: !hide loc<1-15>")
        return
    loc = args[0]
    if loc in hs_state["room_occupants"]:
        send_msg(irc, sender, "🔒 That sector is already occupied.")
        return
    if sender in hs_state["players"] and sender not in hs_state["hider_spots"]:
        hs_state["hider_spots"][sender] = loc
        hs_state["room_occupants"][loc] = sender
        send_msg(irc, sender, f"🤫 Hidden inside the **{LOCATIONS[loc]}**.")


def handle_hs_check(irc, sender, args):
    if hs_state["phase"] != "SEEKING" or sender != hs_state["seeker"]:
        return
    if not args or args[0] not in LOCATIONS:
        send_msg(irc, CHANNEL, "❌ Usage: !check loc<1-15>")
        return
    loc = args[0]
    hs_state["turns_since_last_find"] += 1
    send_msg(irc, CHANNEL, f"🔎 Seeker scanning **{LOCATIONS[loc]}**...")

    if loc in hs_state["room_occupants"]:
        hider = hs_state["room_occupants"][loc]
        scramble = "".join(random.choices(string.ascii_letters + string.digits, k=5))
        duel_id = random.randint(1000, 9999)

        is_final_person = (len(hs_state["players"]) == 1)
        has_headstart = False
        if not is_final_person:
            if hs_state["catches"] == 0 or hs_state["turns_since_last_find"] <= 3:
                has_headstart = True

        hs_state["duel"] = {
            "id": duel_id, "seeker": sender, "hider": hider, "code": scramble, "loc": loc,
            "announce_time": time.time(), "revealed": False
        }
        hs_state["phase"] = "DUEL"
        send_msg(irc, CHANNEL, f"👁️ **{sender}** sees **{hider}**! Both freeze for 2 seconds...")

        if has_headstart:
            send_notice(irc, sender, f"🤫 [HEADSTART ENGAGED] Act fast! Use: !aaspas {scramble}")
    else:
        send_msg(irc, CHANNEL, "💨 Empty! No trace of anyone hiding here.")


def handle_hs_duel_action(irc, sender, cmd, args):
    duel = hs_state["duel"]
    if not duel or not duel.get("revealed"):
        return
    if not args or args[0] != duel["code"]:
        return

    if cmd == "!aaspas" and sender == duel["seeker"]:
        send_msg(irc, CHANNEL, f"💥 **TAGGED!!!** Seeker **{duel['seeker']}** caught **{duel['hider']}**!")
        hs_state["players"].remove(duel["hider"])
        hs_state["eliminated"].append(duel["hider"])
        del hs_state["room_occupants"][duel["loc"]]
        del hs_state["hider_spots"][duel["hider"]]
        hs_state["catches"] += 1
        hs_state["turns_since_last_find"] = 0
        hs_state["duel"] = {}

        if not hs_state["players"]:
            send_msg(irc, CHANNEL, f"🏆 Clean Sweep! Seeker **{duel['seeker']}** caught everyone!")
            end_hs_round(irc, sweep=True)
        else:
            hs_state["phase"] = "SEEKING"
            send_msg(irc, CHANNEL, f"🔎 Hiders left: {len(hs_state['players'])}. Resume hunting.")

    elif cmd == "!dhyapp" and sender == duel["hider"]:
        send_msg(irc, CHANNEL, f"⚡ **DHYAPP!!!** **{duel['hider']}** escaped! HIDERS WIN THE MATCH!")
        hs_state["forced_seeker"] = duel["seeker"]
        end_hs_round(irc, sweep=False)


def end_hs_round(irc, sweep):
    seeker = hs_state["seeker"]
    survivors = list(hs_state["players"])
    caught = list(hs_state["eliminated"])
    forced_seeker = hs_state.get("forced_seeker")
    catches = hs_state["catches"]

    for h in survivors:
        add_points(h, "hide_seek", 50)
    for h in caught:
        add_points(h, "hide_seek", -20)
    if seeker:
        if catches > 0:
            add_points(seeker, "hide_seek", catches * 20)
        if sweep:
            add_points(seeker, "hide_seek", 100)

    send_msg(irc, CHANNEL, "🔄 Round over! Use !play to start a new lobby.")
    reset_hs(keep_settings=True)
    hs_state["forced_seeker"] = forced_seeker
    bot.current_game = None


def handle_hs_admin_tuning(irc, cmd, args):
    if cmd == "!limit" and args:
        try:
            val = int(args[0])
            if val >= 2:
                hs_state["player_limit"] = val
                send_msg(irc, CHANNEL, f"⚙️ Player limit set to {val}.")
            else:
                send_msg(irc, CHANNEL, "❌ Minimum limit is 2.")
        except ValueError:
            send_msg(irc, CHANNEL, "❌ Integer required.")
    elif cmd == "!lobbytime" and args:
        try:
            hs_state["lobby_time"] = int(args[0])
            send_msg(irc, CHANNEL, f"⚙️ Lobby time set to {hs_state['lobby_time']}s.")
        except ValueError:
            send_msg(irc, CHANNEL, "❌ Integer required.")
    elif cmd == "!setdum" and args:
        hs_state["forced_seeker"] = args[0]
        send_msg(irc, CHANNEL, f"⚙️ {args[0]} marked for seeker duty next round.")
    elif cmd == "!limitdum":
        send_msg(irc, CHANNEL, "ℹ️ Only 1 seeker per round is currently supported.")
    elif cmd == "!resetdum":
        if hs_state["phase"] == "SEEKING" and hs_state["players"]:
            old_seeker = hs_state["seeker"]
            new_seeker = random.choice(hs_state["players"])
            hs_state["players"].remove(new_seeker)
            hs_state["players"].append(old_seeker)
            hs_state["seeker"] = new_seeker
            send_msg(irc, CHANNEL, f"🔄 Seeker Shift! **{old_seeker}** swapped. New Seeker: **{new_seeker}**!")


def tick_hide_seek(irc, now):
    if hs_state["phase"] == "LOBBY" and hs_state["lobby_start"] and now - hs_state["lobby_start"] >= hs_state["lobby_time"]:
        finalize_lobby(irc)
    elif hs_state["phase"] == "HIDING" and hs_state["hiding_start"] and now - hs_state["hiding_start"] >= HIDING_TIME:
        finalize_hiding(irc)
    elif hs_state["phase"] == "DUEL":
        duel = hs_state["duel"]
        if duel and not duel.get("revealed") and now - duel["announce_time"] >= DUEL_REVEAL_DELAY:
            send_msg(irc, CHANNEL, "🚨 ─── FACE-OFF ACTIVE ─── 🚨")
            send_msg(irc, CHANNEL, f"👹 Seeker Tag: **!aaspas {duel['code']}** | 🏃 Hider Dodge: **!dhyapp {duel['code']}**")
            duel["revealed"] = True
            duel["duel_start"] = now
        elif duel and duel.get("revealed") and now - duel["duel_start"] >= DUEL_TIMEOUT:
            send_msg(irc, CHANNEL, "⏰ Duel Timeout! Stalemate... Search resumes.")
            hs_state["phase"] = "SEEKING"
            hs_state["duel"] = {}


# ============================================================
# CANCEL / TICK DISPATCH
# ============================================================
def cancel_current_game(irc):
    g = bot.current_game
    if not g:
        return False
    if g == "cipher":
        reset_cipher()
    elif g == "police_thief":
        reset_pt()
    elif g == "fire_shield":
        reset_fs()
    elif g == "hide_seek":
        reset_hs()
    bot.current_game = None
    send_msg(irc, CHANNEL, f"⚠️ Game cancelled by {ADMIN}. No points awarded for the incomplete round.")
    return True


def game_tick(irc):
    now = time.time()
    if bot.current_game == "fire_shield":
        tick_fire_shield(irc, now)
    elif bot.current_game == "hide_seek":
        tick_hide_seek(irc, now)
    elif bot.current_game == "police_thief":
        tick_police_thief(irc, now)


# ============================================================
# HELP / TEXT CONTENT
# ============================================================
def gamelist_text():
    return "🎮 GAMES: 1) Cipher Scramble | 2) Police & Thief | 3) Fire & Shield Battle | 4) Hide & Seek (LukaMari) — use !howtoplay<num> or !ch <num> for details."


def howtoplay_overview_lines():
    return [
        "📖 --- GAMESHERE OVERVIEW ---",
        "1) Cipher Scramble — unscramble the word first with !solve. Use !howtoplay1 for details.",
        "2) Police & Thief — 4 players, Police must catch the Thief. Use !howtoplay2 for details.",
        "3) Fire & Shield Battle — 1v1 duel, HP + bleeding + shields. Use !howtoplay3 for details.",
        "4) Hide & Seek (LukaMari) — Seeker hunts hiders across 15 rooms. Use !howtoplay4 for details.",
        "💡 Use !gamelist, !ch <num>, or !pointsystem<num> anytime."
    ]


def howtoplay_detail_lines(gnum):
    if gnum == 1:
        return [
            "📋 --- CIPHER SCRAMBLE ---",
            "1. Type !cipher to get a scrambled word.",
            "2. Type !solve <word> to guess.",
            "3. !cq shows the current scramble again. !giveup reveals the answer.",
            "4. Admin only: !autogame toggles auto-next-round after each solve.",
            "🏆 Use !pointsystem1 to see scoring."
        ]
    if gnum == 2:
        return [
            "📋 --- POLICE & THIEF ---",
            "1. Type !joingame — needs exactly 4 players to start.",
            "2. Roles are assigned secretly: 1 Police, 1 Thief, 2 Innocents.",
            "3. Police accuses with !thief <username>.",
            "4. Wrong 1st guess → choose !giveup or !reqguess (gamble a 2nd guess).",
            "🏆 Use !pointsystem2 to see scoring."
        ]
    if gnum == 3:
        return [
            "📋 --- FIRE & SHIELD BATTLE ---",
            "1. Type !join — needs exactly 2 players to start.",
            "2. !fire <name> attacks (70 dmg, 15% crit for 150).",
            "3. Hit players bleed -50 HP/sec until they use !shield.",
            "4. !shield stops bleeding instantly and blocks the next hit.",
            "5. 4s cooldown between your own attacks.",
            "🏆 Use !pointsystem3 to see scoring."
        ]
    if gnum == 4:
        return [
            "📋 --- HIDE & SEEK (LUKAMARI) ---",
            "1. Type !play to open/join the lobby (default limit 4, admin-tunable via !limit).",
            "2. One random player becomes Seeker. Hiders PM the bot: !hide loc<1-15>.",
            "3. Seeker uses !check loc<1-15> to scan rooms.",
            "4. Found hiders face a typing duel: Seeker types !aaspas <code>, Hider types !dhyapp <code>.",
            "5. Seeker wins by catching everyone (clean sweep). Hiders win if one escapes a duel.",
            "🏆 Use !pointsystem4 to see scoring."
        ]
    return []


def pointsystem_lines(gnum):
    if gnum == 1:
        return ["🏆 CIPHER POINTS: Solve = +10pts. Wrong guess = 0 (no penalty)."]
    if gnum == 2:
        return ["🏆 POLICE & THIEF POINTS: Police correct 1st = +100 | Police gives up after wrong 1st = -100 | "
                 "Police wrong 2nd = -200 | Police correct 2nd = 0 | Innocents = +50 | Thief caught = 0 | Thief escapes = +100."]
    if gnum == 3:
        return ["🏆 FIRE & SHIELD POINTS: Winner = +100 | Loser = -50."]
    if gnum == 4:
        return ["🏆 HIDE & SEEK POINTS: Surviving/winning Hider = +50 | Caught Hider = -20 | "
                 "Seeker per catch = +20 | Seeker clean sweep bonus = +100 | Seeker loses (hider escapes) = 0."]
    return []


def send_super_howtoplay(irc, admin_sender):
    lines = [
        "📚 --- SUPER HOWTOPLAY (ADMIN REFERENCE) ---",
        "== USER COMMANDS ==",
        "!gamelist | !howtoplay | !howtoplay<1-4> | !pointsystem<1-4> | !ch <1-4> | !ovrank | !gamerank<1-4>",
        "Cipher: !cipher | !solve <word> | !cq | !giveup",
        "Police&Thief: !joingame | !thief <name> | !giveup | !reqguess",
        "Fire&Shield: !join | !fire <name> | !shield",
        "Hide&Seek: !play | !check loc<1-15> | !aaspas <code> | !dhyapp <code> | (PM only) !hide loc<1-15>",
        "== ADMIN COMMANDS ==",
        "!gmon / !gmoff — enable/disable the whole game system (default ON)",
        "!cancelgame — cancels whichever game is currently active, no points awarded",
        "!freeze / !unfreeze — freezes/unfreezes the active game for players",
        "!banforever <user> / !forgive <user> — bans/unbans from ALL games",
        "!setrank<1-4> <user> <points> — manually set a player's score for that game (updates !ovrank too)",
        ".passmsg <text> — broadcast a message to the channel as the bot",
        "!autogame — Cipher only, toggles auto-next-round after each solve",
        "!limit <n> / !lobbytime <s> / !setdum <user> / !resetdum — Hide & Seek tuning",
        "!superhowtoplay — this command (admin only, sent via PM)"
    ]
    send_lines(irc, admin_sender, lines)


# ============================================================
# RANK COMMANDS
# ============================================================
def send_ovrank(irc):
    ranked = [(v["display"], v["total"]) for v in bot.scores.values() if v["total"] != 0]
    ranked.sort(key=lambda kv: kv[1], reverse=True)
    ranked = ranked[:RANK_DISPLAY_COUNT]
    if not ranked:
        send_msg(irc, CHANNEL, "🏆 Overall ranking is empty!")
        return
    text = " | ".join([f"{name}({score})" for name, score in ranked])
    send_msg(irc, CHANNEL, f"🏆 OVERALL RANK: {text}")


def send_gamerank(irc, gnum):
    key = GAME_KEYS[gnum]
    ranked = [(v["display"], v[key]) for v in bot.scores.values() if v[key] != 0]
    ranked.sort(key=lambda kv: kv[1], reverse=True)
    ranked = ranked[:RANK_DISPLAY_COUNT]
    if not ranked:
        send_msg(irc, CHANNEL, f"🏆 {GAME_NAMES[gnum]} ranking is empty!")
        return
    text = " | ".join([f"{name}({score})" for name, score in ranked])
    send_msg(irc, CHANNEL, f"🏆 {GAME_NAMES[gnum].upper()} RANK: {text}")


# ============================================================
# COMMAND ROUTER
# ============================================================
def handle_admin_meta(irc, sender, target, msg, msg_lower, is_admin, is_pm):
    parts = msg.split()
    cmd = parts[0].lower() if parts else ""
    args = parts[1:]

    if cmd.startswith("!setrank") and cmd[8:].isdigit():
        if not is_admin:
            send_msg(irc, CHANNEL, f"⚠️ {sender}, this command is admin-only. Access denied! 🚫")
            return True
        gnum = int(cmd[8:])
        if gnum not in GAME_KEYS or len(args) != 2:
            send_msg(irc, CHANNEL, "❌ Usage: !setrank<gamenum> username points")
            return True
        target_user, pts_str = args
        try:
            pts = int(pts_str)
        except ValueError:
            send_msg(irc, CHANNEL, "❌ Points must be an integer.")
            return True
        set_points(target_user, GAME_KEYS[gnum], pts)
        send_msg(irc, CHANNEL, f"🛠️ {target_user}'s {GAME_NAMES[gnum]} score set to {pts}. Overall rank updated. 📈")
        return True

    if cmd not in ADMIN_ONLY_META_CMDS:
        return False

    if not is_admin:
        send_msg(irc, CHANNEL, f"⚠️ {sender}, this command is admin-only. Access denied! 🚫")
        return True

    if cmd == "!gmon":
        bot.games_enabled = True
        send_msg(irc, CHANNEL, f"✅ Games are now ENABLED by {ADMIN}. 🎮")
    elif cmd == "!gmoff":
        was_active = bot.current_game is not None
        bot.games_enabled = False
        if was_active:
            cancel_current_game(irc)
        send_msg(irc, CHANNEL, f"🚫 Games are now DISABLED by {ADMIN}.")
    elif cmd == "!cancelgame":
        if not cancel_current_game(irc):
            send_msg(irc, CHANNEL, "ℹ️ No game is currently active.")
    elif cmd == "!freeze":
        bot.frozen = True
        send_msg(irc, CHANNEL, "❄️ Game system frozen by admin!")
    elif cmd == "!unfreeze":
        bot.frozen = False
        send_msg(irc, CHANNEL, "🔥 Game system unfrozen by admin!")
    elif cmd == "!banforever":
        if args:
            bot.ban_list.add(args[0].lower())
            send_msg(irc, CHANNEL, f"🚫 {args[0]} has been permanently banned from all games. 💀")
        else:
            send_msg(irc, CHANNEL, "❌ Usage: !banforever <username>")
    elif cmd == "!forgive":
        if args:
            bot.ban_list.discard(args[0].lower())
            send_msg(irc, CHANNEL, f"✨ {args[0]} has been forgiven and may play again. 🌟")
        else:
            send_msg(irc, CHANNEL, "❌ Usage: !forgive <username>")
    elif cmd == ".passmsg":
        content = msg.split(" ", 1)[1] if " " in msg else ""
        if content:
            send_msg(irc, CHANNEL, content)
    elif cmd == "!superhowtoplay":
        send_super_howtoplay(irc, sender)

    return True


def handle_public_meta(irc, sender, target, msg, msg_lower, is_pm):
    parts = msg.split()
    cmd = parts[0].lower() if parts else ""
    args = parts[1:]
    reply_target = sender if is_pm else CHANNEL

    if cmd == "!gamelist":
        send_msg(irc, reply_target, gamelist_text())
        return True

    if cmd == "!howtoplay":
        send_lines(irc, reply_target, howtoplay_overview_lines())
        return True

    if cmd.startswith("!howtoplay") and cmd[10:].isdigit():
        gnum = int(cmd[10:])
        if gnum in GAME_KEYS:
            send_lines(irc, reply_target, howtoplay_detail_lines(gnum))
        else:
            send_msg(irc, reply_target, "❌ Unknown game number. Use !gamelist to see options.")
        return True

    if cmd.startswith("!pointsystem") and cmd[12:].isdigit():
        gnum = int(cmd[12:])
        if gnum in GAME_KEYS:
            send_lines(irc, reply_target, pointsystem_lines(gnum))
        else:
            send_msg(irc, reply_target, "❌ Unknown game number.")
        return True

    if cmd == "!ch":
        if not args or not args[0].isdigit() or int(args[0]) not in GAME_KEYS:
            send_msg(irc, CHANNEL, "❌ Usage: !ch <1-4>. Use !gamelist to see options.")
            return True
        gnum = int(args[0])
        if bot.current_game is not None:
            send_msg(irc, CHANNEL, "❌ A game is already active. Ask admin to !cancelgame first.")
            return True
        bot.selected_game = GAME_KEYS[gnum]
        send_msg(irc, CHANNEL, f"🎮 {GAME_NAMES[gnum]} selected!")
        send_lines(irc, CHANNEL, howtoplay_detail_lines(gnum))
        return True

    if cmd == "!ovrank":
        send_ovrank(irc)
        return True

    if cmd.startswith("!gamerank") and cmd[9:].isdigit():
        gnum = int(cmd[9:])
        if gnum in GAME_KEYS:
            send_gamerank(irc, gnum)
        else:
            send_msg(irc, CHANNEL, "❌ Unknown game number.")
        return True

    return False


def route_to_game(irc, sender, target, msg, msg_lower, is_pm, is_admin):
    parts = msg.split()
    cmd = parts[0].lower() if parts else ""
    args = parts[1:]

    if is_banned(sender):
        return

    if is_pm:
        if cmd == "!hide" and bot.current_game == "hide_seek":
            handle_hs_hide(irc, sender, args)
        return

    def blocked_by_other_game():
        send_msg(irc, CHANNEL, "❌ Another game is currently active. Please wait or ask admin to !cancelgame.")

    def frozen_notice():
        send_msg(irc, CHANNEL, "❄️ Games are frozen right now. Please wait for admin to !unfreeze.")

    # ---- CIPHER ----
    if cmd == "!cipher":
        if bot.current_game not in (None, "cipher"):
            blocked_by_other_game()
            return
        if bot.frozen:
            frozen_notice()
            return
        bot.current_game = "cipher"
        bot.selected_game = None
        start_cipher_round(irc)
        return

    if cmd in {"!solve", "!cq", "!giveup"} and bot.current_game == "cipher":
        if bot.frozen:
            frozen_notice()
            return
        handle_cipher_action(irc, sender, cmd, args)
        return

    if cmd == "!autogame":
        if not is_admin:
            send_msg(irc, CHANNEL, f"⚠️ {sender}, this command is admin-only. Access denied! 🚫")
            return
        cipher_state["autogame"] = not cipher_state["autogame"]
        send_msg(irc, CHANNEL, f"🔄 Auto-game is {'ON' if cipher_state['autogame'] else 'OFF'}. 🤖")
        return

    # ---- POLICE & THIEF ----
    if cmd == "!joingame":
        if bot.current_game not in (None, "police_thief"):
            blocked_by_other_game()
            return
        if bot.frozen:
            frozen_notice()
            return
        bot.current_game = "police_thief"
        bot.selected_game = None
        handle_pt_joingame(irc, sender)
        return

    if cmd in {"!thief", "!giveup", "!reqguess"} and bot.current_game == "police_thief":
        if bot.frozen:
            frozen_notice()
            return
        handle_pt_action(irc, sender, cmd, args)
        return

    # ---- FIRE & SHIELD ----
    if cmd == "!join":
        if bot.current_game not in (None, "fire_shield"):
            blocked_by_other_game()
            return
        if bot.frozen:
            frozen_notice()
            return
        bot.current_game = "fire_shield"
        bot.selected_game = None
        handle_fs_join(irc, sender)
        return

    if cmd in {"!fire", "!shield"} and bot.current_game == "fire_shield":
        if bot.frozen:
            frozen_notice()
            return
        handle_fs_action(irc, sender, cmd, args)
        return

    # ---- HIDE & SEEK ----
    if cmd == "!play":
        if bot.current_game not in (None, "hide_seek"):
            blocked_by_other_game()
            return
        if bot.frozen:
            frozen_notice()
            return
        if hs_state["phase"] == "IDLE":
            bot.current_game = "hide_seek"
            bot.selected_game = None
            start_hs_lobby(irc)
        elif hs_state["phase"] == "LOBBY":
            handle_hs_join_lobby(irc, sender)
        return

    if cmd == "!check" and bot.current_game == "hide_seek":
        if bot.frozen:
            frozen_notice()
            return
        handle_hs_check(irc, sender, args)
        return

    if cmd in {"!aaspas", "!dhyapp"} and bot.current_game == "hide_seek":
        if bot.frozen:
            frozen_notice()
            return
        handle_hs_duel_action(irc, sender, cmd, args)
        return

    if cmd in {"!limit", "!limitdum", "!lobbytime", "!setdum", "!resetdum"}:
        if not is_admin:
            send_msg(irc, CHANNEL, f"⚠️ {sender}, this command is admin-only. Access denied! 🚫")
            return
        handle_hs_admin_tuning(irc, cmd, args)
        return


def handle_privmsg(irc, sender, target, msg):
    if not msg:
        return
    msg_lower = msg.lower()
    is_admin = sender.lower() == ADMIN.lower()
    is_pm = target.lower() == NICK.lower()

    if is_banned(sender) and not is_admin:
        return

    if handle_admin_meta(irc, sender, target, msg, msg_lower, is_admin, is_pm):
        return

    if handle_public_meta(irc, sender, target, msg, msg_lower, is_pm):
        return

    if not bot.games_enabled:
        if is_game_command(msg_lower):
            send_msg(irc, CHANNEL, "🚫 Games are currently disabled.")
        return

    route_to_game(irc, sender, target, msg, msg_lower, is_pm, is_admin)


# ============================================================
# IRC NETWORKING / MAIN LOOP
# ============================================================
def connect_socket():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect((HOST, PORT))
    s.settimeout(0.1)
    return s


def process_line(irc, line, joined_flag):
    if line.startswith("PING"):
        try:
            challenge = line.split()[1]
        except IndexError:
            challenge = ""
        send_raw(irc, f"PONG {challenge}")
        return joined_flag

    if not joined_flag and (" 001 " in line or " 376 " in line):
        send_raw(irc, f"JOIN {CHANNEL}")
        send_msg(irc, CHANNEL, "⚡ GamesHere Online! Type !gamelist or !howtoplay to get started.")
        return True

    if "PRIVMSG" in line and line.startswith(":"):
        try:
            sender = line.split("!")[0][1:]
            after = line.split("PRIVMSG", 1)[1].strip()
            target, sep, rest = after.partition(" :")
            msg = rest.strip()
            if sep:
                handle_privmsg(irc, sender, target.strip(), msg)
        except Exception as e:
            print(f"[!] Parse error on line: {line} -> {e}")

    return joined_flag


def run_bot():
    while True:
        irc = None
        try:
            print(f"[*] Connecting to {HOST}:{PORT}...")
            irc = connect_socket()
            print("[*] Connected. Registering nick...")
            send_raw(irc, f"NICK {NICK}")
            send_raw(irc, f"USER {NICK} 0 * :GamesHere Bot")

            buffer = ""
            joined = False

            while True:
                game_tick(irc)

                try:
                    data = irc.recv(2048).decode("utf-8", errors="ignore")
                    if not data:
                        print("[!] Server closed the connection.")
                        break
                    buffer += data
                    lines = buffer.split("\r\n")
                    buffer = lines.pop()
                    for line in lines:
                        print(f"<< {line}")
                        joined = process_line(irc, line, joined)
                except socket.timeout:
                    pass
                except (BlockingIOError,):
                    pass
                except ConnectionResetError:
                    print("[!] Connection reset by server.")
                    break

                time.sleep(0.05)

        except KeyboardInterrupt:
            print("\n[*] Shutting down.")
            if irc:
                try:
                    send_raw(irc, "QUIT :Shutdown")
                    irc.close()
                except Exception:
                    pass
            sys.exit(0)
        except Exception as e:
            print(f"[!] Connection error: {e}")

        print("[*] Reconnecting in 5 seconds...")
        time.sleep(5)


if __name__ == "__main__":
    run_bot()
