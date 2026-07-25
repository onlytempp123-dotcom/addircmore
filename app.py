import socket
import threading
import time
import os
import re
from flask import Flask

# --- Configuration ---
SERVER = "irc.hybridirc.com"
PORT = 6667
CHANNEL = "#Chatwithworld"
MASTER_OWNER = "Antonio"

# Shared Data
qa_data = {
    "questions": [
        "What's everyone working on today?",
        "Quick question: what's something new you learned this week?",
        "If you could instantly master one skill, what would it be?",
        "What's your favorite app that most people don't know about?",
        "Coffee ☕ or tea 🍵?",
        "What's one goal you're trying to hit this month?",
        "Anyone watching or reading something good lately?",
        "Drop an emoji that matches your mood right now.",
        "What's one productivity tip that actually works for you?",
        "If you could travel anywhere this weekend, where would you go?",
        "What's the last song you added to your playlist?",
        "Would you rather have unlimited free coffee or unlimited free Wi-Fi?",
        "Share one random fact you know.",
        "What's your go-to comfort food?",
        "Morning people or night owls?"
    ],
    "answers": [
        "I'm currently busy chatting and keeping the vibes high!",
        "I learned that some penguins propose with pebbles. So cute!",
        "I'd love to master the art of perfect coding without bugs.",
        "Obsidian is great for taking notes, definitely underrated.",
        "Always coffee for me! ☕",
        "My goal is to make 100 new friends in this channel.",
        "I've been re-watching some classic sci-fi movies lately.",
        "Staying positive! ✨",
        "The 2-minute rule: if it takes less than 2 mins, do it now.",
        "I'd love to visit the digital clouds of Tokyo.",
        "A bit of Lo-fi beats to keep the focus up.",
        "Unlimited Wi-Fi, hands down. I need my connection!",
        "Did you know honey never spoils? Archaeologists found edible honey in ancient tombs.",
        "Nothing beats a warm bowl of Ramen.",
        "Definitely a night owl, the server is quieter then!"
    ]
}

automation_enabled = True
verified_admins = set()
lock = threading.Lock()

# --- Flask Server (For Render Keep-Alive) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "IRC Bots are running. Check the logs for activity."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- IRC Bot Class ---
class IRCBot:
    def __init__(self, nickname, realname):
        self.nickname = nickname
        self.realname = realname
        self.sock = None
        self.running = True

    def send_raw(self, msg):
        if self.sock:
            self.sock.send((msg + "\r\n").encode('utf-8'))

    def send_msg(self, target, msg):
        self.send_raw(f"PRIVMSG {target} :{msg}")

    def connect(self):
        print(f"[{self.nickname}] Connecting to {SERVER}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((SERVER, PORT))
        self.send_raw(f"NICK {self.nickname}")
        self.send_raw(f"USER {self.nickname} 0 * :{self.realname}")
        
        # Registration and Joining
        while True:
            line = self.sock.recv(2048).decode('utf-8', errors='ignore')
            if not line: break
            if "001" in line: # Success code
                print(f"[{self.nickname}] Registered successfully.")
                self.send_raw(f"JOIN {CHANNEL}")
                break
            if "PING" in line:
                self.send_raw("PONG " + line.split()[1])

    def handle_commands(self, sender, message):
        global automation_enabled
        sender_nick = sender.split('!')[0]
        
        # Verify Admin
        if message == "!xlr8powerup":
            verified_admins.add(sender_nick)
            self.send_msg(sender_nick, "You are now a verified admin.")
            return

        is_admin = (sender_nick == MASTER_OWNER or sender_nick in verified_admins)
        if not is_admin:
            return

        # Toggle Automation
        if message == "!offqa":
            automation_enabled = False
            self.send_msg(sender_nick, "Q&A Automation turned OFF.")
        elif message == "!onqa":
            automation_enabled = True
            self.send_msg(sender_nick, "Q&A Automation turned ON.")

        # List Content
        elif message == "!qlist" and self.nickname == "Yumi143":
            for i, q in enumerate(qa_data["questions"]):
                self.send_msg(sender_nick, f"{i+1}: {q}")
        
        elif message == "!alist" and self.nickname == "IamSonia":
            for i, a in enumerate(qa_data["answers"]):
                self.send_msg(sender_nick, f"{i+1}: {a}")

        # Add/Delete logic
        add_q_match = re.match(r"!addq(\d+) (.+)", message)
        add_a_match = re.match(r"!adda(\d+) (.+)", message)
        del_q_match = re.match(r"!delq(\d+)", message)
        del_a_match = re.match(r"!dela(\d+)", message)

        with lock:
            if add_q_match:
                idx, content = int(add_q_match.group(1)) - 1, add_q_match.group(2)
                if idx >= len(qa_data["questions"]):
                    qa_data["questions"].append(content)
                    self.send_msg(sender_nick, f"Added to end (Index {len(qa_data['questions'])})")
                else:
                    qa_data["questions"][idx] = content
                    self.send_msg(sender_nick, f"Updated Question {idx+1}")

            elif add_a_match:
                idx, content = int(add_a_match.group(1)) - 1, add_a_match.group(2)
                if idx >= len(qa_data["answers"]):
                    qa_data["answers"].append(content)
                    self.send_msg(sender_nick, f"Added to end (Index {len(qa_data['answers'])})")
                else:
                    qa_data["answers"][idx] = content
                    self.send_msg(sender_nick, f"Updated Answer {idx+1}")

            elif del_q_match:
                idx = int(del_q_match.group(1)) - 1
                if 0 <= idx < len(qa_data["questions"]):
                    qa_data["questions"].pop(idx)
                    self.send_msg(sender_nick, f"Deleted Question {idx+1}")

            elif del_a_match:
                idx = int(del_a_match.group(1)) - 1
                if 0 <= idx < len(qa_data["answers"]):
                    qa_data["answers"].pop(idx)
                    self.send_msg(sender_nick, f"Deleted Answer {idx+1}")

    def listen(self):
        while self.running:
            try:
                data = self.sock.recv(2048).decode('utf-8', errors='ignore')
                if not data: break
                
                for line in data.split("\r\n"):
                    if not line: continue
                    
                    # Heartbeat
                    if line.startswith("PING"):
                        self.send_raw("PONG " + line.split()[1])
                    
                    # Parse Messages
                    if "PRIVMSG" in line:
                        parts = line.split(" ", 3)
                        sender = parts[0][1:]
                        target = parts[2]
                        message = parts[3][1:] if len(parts) > 3 else ""
                        
                        # Only respond to commands in Private Messages (PM)
                        if target == self.nickname:
                            self.handle_commands(sender, message)
            except Exception as e:
                print(f"[{self.nickname}] Error: {e}")
                time.sleep(5)
                self.connect()

# --- Automation Logic ---
def qa_loop(bot1, bot2):
    current_index = 0
    while True:
        if automation_enabled:
            with lock:
                q_count = len(qa_data["questions"])
                a_count = len(qa_data["answers"])
                
                if q_count > 0 and a_count > 0:
                    if current_index >= q_count:
                        current_index = 0
                    
                    # Bot 1 asks
                    question = qa_data["questions"][current_index]
                    bot1.send_msg(CHANNEL, question)
                    
                    # Wait 30 seconds for Bot 2 to answer
                    time.sleep(30)
                    
                    # Double check if index is still valid for Bot 2
                    if current_index < len(qa_data["answers"]):
                        answer = qa_data["answers"][current_index]
                        bot2.send_msg(CHANNEL, answer)
                    
                    current_index += 1
            
            # 4 minutes total interval (minus the 30s already waited)
            time.sleep(210)
        else:
            time.sleep(10)

# --- Execution ---
if __name__ == "__main__":
    # Initialize Bots
    bot_yumi = IRCBot("Yumi143", "Yumi143")
    bot_sonia = IRCBot("IamSonia", "IamSonia")

    # Start Flask in a thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Start Bots
    def start_bot(bot_obj):
        bot_obj.connect()
        bot_obj.listen()

    t1 = threading.Thread(target=start_bot, args=(bot_yumi,), daemon=True)
    t2 = threading.Thread(target=start_bot, args=(bot_sonia,), daemon=True)
    t1.start()
    t2.start()

    # Give bots a moment to join channel
    time.sleep(10)

    # Start Automation Loop
    qa_thread = threading.Thread(target=qa_loop, args=(bot_yumi, bot_sonia), daemon=True)
    qa_thread.start()

    # Keep main thread alive
    while True:
        time.sleep(1)
