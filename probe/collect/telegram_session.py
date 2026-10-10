"""Create the Telegram session for WarWatch and store it as GitHub secrets.

Run once on the laptop, in a terminal (it is interactive). Telegram sends a login
code to the Telegram app; type it here. Nothing is printed or left on disk: the
values go straight into khourix/warwatch-collect secrets through `gh`.
"""
import getpass
import subprocess

from telethon.sessions import StringSession
from telethon.sync import TelegramClient

REPO = "khourix/warwatch-collect"


def set_secret(name, value):
    subprocess.run(["gh", "secret", "set", name, "-R", REPO], input=value.encode(), check=True)
    print(f"  saved {name}")


api_id = input("api_id (number from my.telegram.org, API development tools): ").strip()
api_hash = getpass.getpass("api_hash (hidden while you type): ").strip()

with TelegramClient(StringSession(), int(api_id), api_hash, device_model="WarWatch collector") as client:
    me = client.get_me()
    print(f"\nLogged in as {me.first_name} (@{me.username or 'no username'}). Saving secrets to {REPO}:")
    set_secret("TELEGRAM_API_ID", api_id)
    set_secret("TELEGRAM_API_HASH", api_hash)
    set_secret("TELEGRAM_SESSION", client.session.save())
print("Done. You can close this terminal.")
