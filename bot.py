import discord
import os, json, pickle
from dotenv import load_dotenv
from google import generativeai as genai  

# ---------------- SETUP ----------------
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("GEMINI_API_KEY")
CONTEXT = ""
genai.configure(api_key=API_KEY)
MODEL = genai.GenerativeModel("gemini-2.5-flash")

client = discord.Client(intents=discord.Intents.default())


PICKLE_PATH = "memory.pkl"
JSON_PATH = "memory.json"
MAX_CHARS = 2000
# ---------------- LOAD MEMORY ----------------
def load_memory():
    if os.path.exists(PICKLE_PATH):
        try:
            with open(PICKLE_PATH, "rb") as f:
                return pickle.load(f)
        except:
            pass

    return {}

memory = load_memory()


# ---------------- SAVE MEMORY (BOTH FORMATS) ----------------
def save_memory():
    # 1. Pickle (fast runtime state)
    with open(PICKLE_PATH, "wb") as f:
        pickle.dump(memory, f)

    # 2. JSON (backup / human-readable)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2)


# ---------------- MEMORY OPERATIONS ----------------
def get_history(user_id):
    return memory.get(user_id, "")


def add_message(user_id, role, content):
    if user_id not in memory:
        memory[user_id] = []

    memory[user_id].append({
        "role": role,
        "content": content
    })

    # keep memory lightweight
    memory[user_id] = memory[user_id][-MAX_CHARS:]

    save_memory()

# ---------------- LOAD CONTEXT ----------------
context_path = os.path.abspath("details.txt")

with open(context_path, "r", encoding="utf-8") as f:
    CONTEXT = f.read()

# ---------------- MEMORY SYSTEM ----------------
memory = {}

def get_history(user_id):
    return memory.get(user_id, [])

def save_message(user_id, role, content):
    if user_id not in memory:
        memory[user_id] = []
    memory[user_id].append((role, content))
    memory[user_id] = memory[user_id][-10:]  # limit memory

def format_history(history):
    if not history:
        return "No previous conversation."

    return "\n".join(
        [f"{m['role']}: {m['content']}" for m in history]
    )

# ---------------- FRUSTRATION DETECTION ----------------
FRUSTRATION_KEYWORDS = ["just give", "i don't get", "answer me", "confused", "help"]

def is_frustrated(history):
    count = 0
    for _, msg in history:
        for word in FRUSTRATION_KEYWORDS:
            if word in msg.lower():
                count += 1
    return count >= 2


# ---------------- GEMINI CALL ----------------
def ask_gemini(prompt):
    response = MODEL.generate_content(prompt)
    return response.text


# ---------------- PROMPT ENGINE ----------------
def build_prompt(user_prompt, history, mode):
    history_text = format_history(history)
    frustrated = is_frustrated(history)

    if mode == "!biz":
        return f"""
You are a formal assistant for CodeCraft.

Use this official context:
{CONTEXT}

Conversation history:
{history_text}

User question:
{user_prompt}
"""

    elif mode == "!code":
        extra = ""

        if frustrated:
            extra = "The student is frustrated. You may give clearer explanations but still avoid full direct solutions."

        return f"""
You are a coding tutor inspired by CS50.

RULES:
- Do NOT immediately give full answers
- Start with guiding questions
- Provide hints and small examples
- Be structured and educational

{extra}

Conversation history:
{history_text}

User question:
{user_prompt}
"""

    elif mode == "!start":
        return f"""
You are introducing CodeCraft to a new student.

Context:
{CONTEXT}
"""

    else:
        return user_prompt


# ---------------- DISCORD EVENTS ----------------
VALID_COMMANDS = ["!biz", "!code", "!start"]

@client.event
async def on_ready():
    print(f"Bot is online as {client.user}")

@client.event
async def on_member_join(member):
    channel = member.guild.system_channel
    if channel:
        prompt = build_prompt("", [], "!start")
        reply = ask_gemini(prompt)
        await channel.send(reply[:1900])


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content
    user_id = str(message.author.id)

    # detect command
    cmd = None
    for c in VALID_COMMANDS:
        if content.startswith(c):
            cmd = c
            break

    if not cmd:
        return

    user_prompt = content[len(cmd):].strip()
    history = get_history(user_id)

    prompt = build_prompt(user_prompt, history, cmd)
    reply = ask_gemini(prompt)

    # save memory
    add_message(user_id, "user", user_prompt)
    add_message(user_id, "assistant", reply)

    await message.channel.send(reply[:1900])


# ---------------- RUN BOT ----------------
client.run(TOKEN)