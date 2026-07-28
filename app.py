import socket
import time
import random
import threading
import ssl
from flask import Flask

# === CONFIGURATION ===
HOST = "irc.hybridirc.com"
PORT = 6667
CHAN = "#chatwithworld"
ADMIN = "Antonio"

# Bot Names
NICK_A = "GamesHere"
NICK_B = "YUMI143"

app = Flask(__name__)

@app.route('/')
def home():
    return "Bots are running 24/7."

# === SHARED DATA & GAME STATE ===
class GameSystem:
    def __init__(self):
        self.game_mode_enabled = True
        self.current_game_id = 0  # 0 = None, 1-5 = Active Game
        self.active_player = None # For single player games like RPS
        self.players = []         # For multiplayer games like Police/Thief
        self.game_data = {}       # Storage for specific game logic
        self.leaderboards = {
            "1": {}, "2": {}, "3": {}, "4": {}, "5": {}, "overall": {}
        }
        self.ban_list = set()

    def set_score(self, game_id, user, score):
        self.leaderboards[str(game_id)][user.lower()] = score
        self.update_overall(user.lower())

    def update_overall(self, user):
        total = 0
        for i in range(1, 6):
            total += self.leaderboards[str(i)].get(user.lower(), 0)
        self.leaderboards["overall"][user.lower()] = total

gs = GameSystem()

# === GAME LIBRARIES ===
WORD_POOL = [
    "APPLE", "BANANA", "CHERRY", "DOG", "CAT", "MOUSE", "HOUSE", "PLANE", "TRAIN", "BOAT",
    "CAR", "TRUCK", "BIKE", "BUS", "SHIP", "HELICOPTER", "SUBWAY", "BRIDGE", "ROAD", "STREET",
    "RIVER", "LAKE", "OCEAN", "MOUNTAIN", "HILL", "FOREST", "TREE", "FLOWER", "GRASS", "LEAF",
    "SUN", "MOON", "STAR", "CLOUD", "RAIN", "SNOW", "WIND", "STORM", "THUNDER", "LIGHTNING",
    "FIRE", "WATER", "EARTH", "STONE", "SAND", "METAL", "GOLD", "SILVER", "COPPER", "IRON",
    "BOOK", "PENCIL", "PEN", "PAPER", "NOTEBOOK", "ERASER", "RULER", "MARKER", "CRAYON", "SCISSORS",
    "TABLE", "CHAIR", "SOFA", "BED", "PILLOW", "BLANKET", "LAMP", "CLOCK", "WINDOW", "DOOR",
    "KITCHEN", "BATHROOM", "BEDROOM", "GARAGE", "GARDEN", "FENCE", "ROOF", "FLOOR", "WALL", "CEILING",
    "PHONE", "COMPUTER", "LAPTOP", "KEYBOARD", "MOUSEPAD", "SCREEN", "MONITOR", "PRINTER", "CAMERA", "SPEAKER",
    "HEADPHONE", "MICROPHONE", "WATCH", "GLASSES", "BAG", "BACKPACK", "SUITCASE", "UMBRELLA", "BOTTLE", "CUP",
    "PLATE", "BOWL", "SPOON", "FORK", "KNIFE", "PIZZA", "BURGER", "SANDWICH", "BREAD", "CHEESE",
    "MILK", "BUTTER", "EGG", "RICE", "PASTA", "SOUP", "SALAD", "ORANGE", "PEACH", "PEAR",
    "GRAPE", "LEMON", "LIME", "MANGO", "PINEAPPLE", "COCONUT", "STRAWBERRY", "BLUEBERRY", "WATERMELON", "KIWI",
    "HORSE", "COW", "PIG", "SHEEP", "GOAT", "CHICKEN", "DUCK", "GOOSE", "RABBIT", "FOX",
    "WOLF", "BEAR", "LION", "TIGER", "ELEPHANT", "GIRAFFE", "ZEBRA", "MONKEY", "PANDA", "KOALA",
    "DOLPHIN", "SHARK", "WHALE", "OCTOPUS", "SQUID", "FROG", "SNAKE", "LIZARD", "TURTLE", "EAGLE",
    "HAWK", "OWL", "PARROT", "SPARROW", "PENGUIN", "PEACOCK", "BUTTERFLY", "BEE", "ANT", "SPIDER",
    "DOCTOR", "NURSE", "TEACHER", "STUDENT", "ENGINEER", "LAWYER", "CHEF", "BAKER", "FARMER", "PILOT",
    "POLICE", "FIREFIGHTER", "ARTIST", "MUSICIAN", "WRITER", "ACTOR", "DANCER", "SCIENTIST", "JUDGE", "DRIVER",
    "SCHOOL", "COLLEGE", "LIBRARY", "HOSPITAL", "OFFICE", "STORE", "MARKET", "PARK", "MUSEUM", "THEATER",
    "HOTEL", "RESTAURANT", "AIRPORT", "STATION", "CASTLE", "TOWER", "CHURCH", "TEMPLE", "MOSQUE", "PALACE",
    "BALL", "BAT", "RACKET", "GOAL", "NET", "HELMET", "GLOVE", "SHOE", "SOCK", "JACKET",
    "SHIRT", "PANTS", "DRESS", "SKIRT", "HAT", "SCARF", "BELT", "BUTTON", "ZIPPER", "POCKET",
    "HAPPY", "SAD", "ANGRY", "EXCITED", "CALM", "BRAVE", "SMART", "KIND", "FUNNY", "LOUD",
    "QUIET", "FAST", "SLOW", "STRONG", "WEAK", "SMALL", "LARGE", "TALL", "SHORT", "ROUND",
    "SQUARE", "TRIANGLE", "CIRCLE", "HEART", "DIAMOND", "ARROW", "CROWN", "SWORD", "SHIELD", "KEY",
    "LOCK", "CHEST", "MAP", "COMPASS", "TORCH", "ROPE", "LADDER", "HAMMER", "NAIL", "SAW",
    "PAINT", "BRUSH", "CANVAS", "GUITAR", "PIANO", "DRUM", "VIOLIN", "FLUTE", "TRUMPET", "SONG",
    "MOVIE", "GAME", "PUZZLE", "TOY", "DOLL", "ROBOT", "TEDDY", "KITE", "BALLOON", "CANDLE",
    "BIRTHDAY", "HOLIDAY", "FESTIVAL", "PARTY", "GIFT", "LETTER", "PACKAGE", "TICKET", "PASSPORT", "COIN",
    "MONEY", "BANK", "CREDIT", "MARKET", "FACTORY", "WORKSHOP", "LABORATORY", "MACHINE", "ENGINE", "GEAR",
    "BUTTON", "SWITCH", "WIRE", "BATTERY", "MAGNET", "LASER", "ROCKET", "SATELLITE", "PLANET", "GALAXY",
    "UNIVERSE", "ISLAND", "DESERT", "VALLEY", "VOLCANO", "CAVE", "CLIFF", "BEACH", "HARBOR", "PORT",
    "FISH", "CRAB", "LOBSTER", "SEAHORSE", "JELLYFISH", "CORAL", "SHELL", "PEBBLE", "ICE", "STEAM",
    "SMOKE", "SHADOW", "MIRROR", "PHOTO", "PICTURE", "FRAME", "ALBUM", "NEWSPAPER", "MAGAZINE", "STORY",
    "POEM", "LANGUAGE", "LETTER", "NUMBER", "SYMBOL", "SECRET", "CODE", "CIPHER", "MESSAGE", "SIGNAL",
    "ENERGY", "POWER", "LIGHT", "SOUND", "VOICE", "MUSIC", "RHYTHM", "MELODY", "COLOR", "PAINTING",
    "BLACK", "WHITE", "RED", "BLUE", "GREEN", "YELLOW", "PURPLE", "ORANGE", "PINK", "BROWN",
    "SILK", "COTTON", "WOOL", "LEATHER", "GLASS", "PLASTIC", "RUBBER", "PAPERCLIP", "ENVELOPE", "STAMP",
    "BREAD", "COOKIE", "CAKE", "PIE", "DONUT", "CANDY", "CHOCOLATE", "HONEY", "JAM", "TEA",
    "COFFEE", "JUICE", "SODA", "SMOOTHIE", "COOKIE", "NOODLES", "CURRY", "TOMATO", "POTATO", "ONION",
    "CARROT", "BROCCOLI", "CABBAGE", "CUCUMBER", "PEPPER", "BEANS", "CORN", "GARLIC", "GINGER", "SPINACH",
    "CLOCK", "CALENDAR", "SEASON", "SPRING", "SUMMER", "AUTUMN", "WINTER", "MORNING", "EVENING", "NIGHT",
    "TODAY", "TOMORROW", "YESTERDAY", "MINUTE", "HOUR", "SECOND", "MONTH", "YEAR", "DECADE", "CENTURY",
    "FRIEND", "FAMILY", "PARENT", "CHILD", "BROTHER", "SISTER", "UNCLE", "AUNT", "COUSIN", "NEIGHBOR"
] # truncated for brevity, add more

# === BOT B: YUMI143 (The Greeter) ===
def run_bot_b():
    def send_msg(s, msg):
        s.send(f"PRIVMSG {CHAN} :{msg}\r\n".encode())

    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((HOST, PORT))
            s.send(f"NICK {NICK_B}\r\nUSER {NICK_B} 0 * :Yumi\r\n".encode())
            
            last_wish = time.time()
            
            while True:
                s.settimeout(10)
                try:
                    data = s.recv(2048).decode("utf-8", errors="ignore")
                    if data.startswith("PING"):
                        s.send(f"PONG {data.split()[1]}\r\n".encode())
                    if " 001 " in data:
                        s.send(f"JOIN {CHAN}\r\n".encode())
                except socket.timeout:
                    pass

                if time.time() - last_wish >= 180: # 3 minutes
                    send_msg(s, "Wishing everyone all the best. May everything continue to go smoothly.")
                    last_wish = time.time()
        except Exception as e:
            print(f"Bot B Error: {e}")
            time.sleep(10)

# === BOT A: GamesHere (The Game Master) ===
def run_bot_a():
    irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    def send_msg(msg):
        print(f">> {msg}")
        irc.send(f"PRIVMSG {CHAN} :{msg}\r\n".encode("utf-8"))

    def connect():
        irc.connect((HOST, PORT))
        irc.send(f"NICK {NICK_A}\r\nUSER {NICK_A} 0 * :GameBot\r\n".encode("utf-8"))

    connect()
    
    buffer = ""
    while True:
        try:
            data = irc.recv(2048).decode("utf-8", errors="ignore")
            if not data: break
            buffer += data
            lines = buffer.split("\r\n")
            buffer = lines.pop()

            for line in lines:
                if line.startswith("PING"):
                    irc.send(f"PONG {line.split()[1]}\r\n".encode())
                
                if " 001 " in line:
                    irc.send(f"JOIN {CHAN}\r\n".encode())

                if "PRIVMSG" in line:
                    parts = line.split("!")
                    sender = parts[0][1:]
                    msg_part = line.split(f"PRIVMSG {CHAN} :")
                    if len(msg_part) < 2: continue
                    msg = msg_part[1].strip()
                    lmsg = msg.lower()

                    # --- ADMIN COMMANDS ---
                    if sender.lower() == ADMIN.lower():
                        if lmsg == "!gamemodeon":
                            gs.game_mode_enabled = True
                            send_msg("🎮 Game Mode: ENABLED.")
                        elif lmsg == "!gamemodeoff":
                            gs.game_mode_enabled = False
                            gs.current_game_id = 0
                            send_msg("🚫 Game Mode: DISABLED.")
                        elif lmsg == "!cancelgame":
                            gs.current_game_id = 0
                            send_msg("🛑 Current game cancelled.")
                        elif lmsg.startswith("!setrank"):
                            # !setrank<num> user score
                            try:
                                cmd_part = lmsg.split()[0]
                                g_id = cmd_part.replace("!setrank", "")
                                target_user = lmsg.split()[1]
                                new_score = int(lmsg.split()[2])
                                gs.set_score(g_id, target_user, new_score)
                                send_msg(f"✅ {target_user}'s rank for Game {g_id} set to {new_score}.")
                            except: send_msg("Usage: !setrank<1-5> username score")
                        elif lmsg.startswith("!setrankov"):
                            try:
                                target_user = lmsg.split()[1]
                                new_score = int(lmsg.split()[2])
                                gs.leaderboards["overall"][target_user.lower()] = new_score
                                send_msg(f"✅ Overall rank for {target_user} set to {new_score}.")
                            except: send_msg("Usage: !setrankov username score")

                    # --- PUBLIC COMMANDS ---
                    if not gs.game_mode_enabled: continue

                    if lmsg == "!gamelist":
                        send_msg("📜 1: Cipher | 2: Police/Thief | 3: RPS | 4: Math | 5: GuessNum")
                    
                    elif lmsg.startswith("!howtoplay "):
                        gid = lmsg.split()[-1]
                        if gid == "1": send_msg("Game 1 (Cipher): Solve the scrambled word using !solve <word>")
                        elif gid == "2": send_msg("Game 2 (Police/Thief): 4 players join via !joingame. Police guesses the thief via !thief <name>")
                        elif gid == "3": send_msg("Game 3 (RPS): Play Rock Paper Scissors via !rps <rock/paper/scissor>")
                        elif gid == "4": send_msg("Game 4 (Math): Solve the math problem via !ans <number>")
                        elif gid == "5": send_msg("Game 5 (GuessNum): Guess the number 1-100 via !guess <number>")

                    elif lmsg.startswith("!ch "):
                        if gs.current_game_id != 0:
                            send_msg(f"❌ Game {gs.current_game_id} is already in progress! Use !cancelgame first (Admin).")
                            continue
                        choice = lmsg.split()[-1]
                        if choice in ["1", "2", "3", "4", "5"]:
                            gs.current_game_id = int(choice)
                            # Initialize specific game logic
                            if choice == "1":
                                word = random.choice(WORD_POOL)
                                scrambled = "".join(random.sample(word, len(word)))
                                gs.game_data = {"word": word}
                                send_msg(f"🌀 [CIPHER] Scrambled: {scrambled} | Solve: !solve <word>")
                            elif choice == "2":
                                gs.players = []
                                send_msg("🕵️‍♂️ [POLICE/THIEF] 4 players needed! Type !joingame to enter.")
                            elif choice == "3":
                                send_msg("👊 [RPS] Challenge me! Type !rps <rock|paper|scissor>")
                            elif choice == "4":
                                a, b = random.randint(1, 50), random.randint(1, 50)
                                gs.game_data = {"ans": a + b}
                                send_msg(f"➕ [MATH] What is {a} + {b}? Answer: !ans <val>")
                            elif choice == "5":
                                gs.game_data = {"num": random.randint(1, 100)}
                                send_msg("🔢 [GUESS] I'm thinking of 1-100. Guess: !guess <num>")

                    elif lmsg == "!ovrank":
                        top = sorted(gs.leaderboards["overall"].items(), key=lambda x: x[1], reverse=True)[:5]
                        rank_str = " | ".join([f"{u}({s})" for u, s in top])
                        send_msg(f"🏆 OVERALL RANKING: {rank_str if rank_str else 'Empty'}")

                    # --- GAME LOGIC HANDLERS ---
                    if gs.current_game_id == 1 and lmsg.startswith("!solve "):
                        guess = lmsg.split()[-1].upper()
                        if guess == gs.game_data["word"]:
                            gs.set_score("1", sender, gs.leaderboards["1"].get(sender.lower(), 0) + 10)
                            send_msg(f"🎉 {sender} solved it! (+10pts). Game Over.")
                            gs.current_game_id = 0
                    
                    elif gs.current_game_id == 2:
                        if lmsg == "!joingame" and sender not in gs.players and len(gs.players) < 4:
                            gs.players.append(sender)
                            send_msg(f"🎮 {sender} joined! ({len(gs.players)}/4)")
                            if len(gs.players) == 4:
                                roles = ["Police", "Thief", "Innocent", "Innocent"]
                                random.shuffle(roles)
                                gs.game_data = dict(zip(gs.players, roles))
                                police = [p for p, r in gs.game_data.items() if r == "Police"][0]
                                send_msg(f"📢 Roles assigned! 👮 Police is {police}. Suspects: {', '.join([p for p in gs.players if p != police])}")
                                send_msg("Police, use !thief <name>")
                        elif lmsg.startswith("!thief "):
                            police = [p for p, r in gs.game_data.items() if r == "Police"][0]
                            if sender == police:
                                target = lmsg.split()[-1]
                                thief = [p for p, r in gs.game_data.items() if r == "Thief"][0]
                                if target.lower() == thief.lower():
                                    send_msg(f"🎉 CAUGHT! {thief} was the thief! Police wins +100pts.")
                                    gs.set_score("2", police, gs.leaderboards["2"].get(police.lower(), 0) + 100)
                                else:
                                    send_msg(f"❌ Wrong! {target} was innocent. Thief {thief} escaped! (+100pts to thief)")
                                    gs.set_score("2", thief, gs.leaderboards["2"].get(thief.lower(), 0) + 100)
                                gs.current_game_id = 0

                    elif gs.current_game_id == 3 and lmsg.startswith("!rps "):
                        user_choice = lmsg.split()[-1]
                        bot_choice = random.choice(["rock", "paper", "scissor"])
                        if user_choice in ["rock", "paper", "scissor"]:
                            if user_choice == bot_choice: result = "Tie!"
                            elif (user_choice == "rock" and bot_choice == "scissor") or \
                                 (user_choice == "paper" and bot_choice == "rock") or \
                                 (user_choice == "scissor" and bot_choice == "paper"):
                                result = "You win! (+10pts)"
                                gs.set_score("3", sender, gs.leaderboards["3"].get(sender.lower(), 0) + 10)
                            else:
                                result = "Bot wins! (-5pts)"
                                gs.set_score("3", sender, gs.leaderboards["3"].get(sender.lower(), 0) - 5)
                            send_msg(f"🤖 I chose {bot_choice}. {result}")
                            gs.current_game_id = 0

                    elif gs.current_game_id == 4 and lmsg.startswith("!ans "):
                        try:
                            if int(lmsg.split()[-1]) == gs.game_data["ans"]:
                                send_msg(f"🎯 Correct {sender}! (+10pts)")
                                gs.set_score("4", sender, gs.leaderboards["4"].get(sender.lower(), 0) + 10)
                                gs.current_game_id = 0
                        except: pass

                    elif gs.current_game_id == 5 and lmsg.startswith("!guess "):
                        try:
                            g = int(lmsg.split()[-1])
                            target = gs.game_data["num"]
                            if g == target:
                                send_msg(f"🎊 Boom! {sender} guessed {target}! (+20pts)")
                                gs.set_score("5", sender, gs.leaderboards["5"].get(sender.lower(), 0) + 20)
                                gs.current_game_id = 0
                            elif g < target: send_msg("Higher!")
                            else: send_msg("Lower!")
                        except: pass

        except Exception as e:
            print(f"Bot A Error: {e}")
            time.sleep(10)
            connect()

if __name__ == "__main__":
    # Start Bot threads
    threading.Thread(target=run_bot_a, daemon=True).start()
    threading.Thread(target=run_bot_b, daemon=True).start()
    # Start Flask server
    app.run(host='0.0.0.0', port=8080)
