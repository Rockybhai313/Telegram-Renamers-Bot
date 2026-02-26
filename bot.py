
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# ================= ENV VARIABLES =================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
# =================================================

DOWNLOAD_DIR = "downloads"
THUMB_PATH = "thumbnail.jpg"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Client("advanced_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

queue = asyncio.Queue()
user_data = {}

WORKERS = 3  # Multi-worker count

async def progress(current, total, message, action):
    percent = current * 100 / total
    filled = int(percent // 5)
    bar = "█" * filled + "░" * (20 - filled)
    try:
        await message.edit_text(f"{action}\n[{bar}] {percent:.1f}%")
    except:
        pass

async def worker():
    while True:
        msg, new_name, caption = await queue.get()

        try:
            media = msg.document or msg.video or msg.audio
            original_name = media.file_name or "file.bin"
            final_name = new_name if new_name else original_name

            file_path = os.path.join(DOWNLOAD_DIR, final_name)
            status = await msg.reply_text("Downloading...")

            downloaded = await msg.download(
                file_name=file_path,
                progress=progress,
                progress_args=(status, "Downloading...")
            )

            await status.edit_text("Uploading...")

            await msg.reply_document(
                document=downloaded,
                thumb=THUMB_PATH if os.path.exists(THUMB_PATH) else None,
                caption=caption if caption else "",
                progress=progress,
                progress_args=(status, "Uploading...")
            )

            await status.edit_text("Completed")
            os.remove(downloaded)

        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            await msg.reply_text(f"Error: {e}")

        queue.task_done()

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("Send file 1GB–4GB")

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_panel(client, message):
    await message.reply_text(
        f"Admin Panel\nQueue Size: {queue.qsize()}\nWorkers: {WORKERS}"
    )

@app.on_message(filters.command("setthumb") & filters.user(ADMIN_ID) & filters.photo)
async def set_thumb(client, message):
    await message.download(file_name=THUMB_PATH)
    await message.reply_text("Thumbnail Saved")

@app.on_message(filters.document | filters.video | filters.audio)
async def media_handler(client, message):
    size = (message.document or message.video or message.audio).file_size

    if size < 1 * 1024**3 or size > 4 * 1024**3:
        await message.reply_text("File must be 1GB–4GB")
        return

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Rename", callback_data="rename"),
         InlineKeyboardButton("Skip", callback_data="skip")]
    ])

    user_data[message.from_user.id] = {"message": message}
    await message.reply_text("Choose option", reply_markup=buttons)

@app.on_callback_query()
async def callback_handler(client, query):
    user_id = query.from_user.id

    if user_id not in user_data:
        return

    if query.data == "rename":
        user_data[user_id]["rename"] = True
        await query.message.edit_text("Send new file name")

    elif query.data == "skip":
        await queue.put((user_data[user_id]["message"], None, ""))
        await query.message.edit_text("Added to Queue")
        user_data.pop(user_id)

@app.on_message(filters.text)
async def rename_input(client, message):
    user_id = message.from_user.id

    if user_id in user_data and user_data[user_id].get("rename"):
        user_data[user_id]["new_name"] = message.text
        await message.reply_text("Send caption or type /skipcaption")

@app.on_message(filters.command("skipcaption"))
async def skip_caption(client, message):
    user_id = message.from_user.id

    if user_id in user_data:
        await queue.put((
            user_data[user_id]["message"],
            user_data[user_id].get("new_name"),
            ""
        ))
        await message.reply_text("Added to Queue")
        user_data.pop(user_id)

@app.on_message(filters.text & ~filters.command(["skipcaption"]))
async def caption_input(client, message):
    user_id = message.from_user.id

    if user_id in user_data and "new_name" in user_data[user_id]:
        caption = message.text
        await queue.put((
            user_data[user_id]["message"],
            user_data[user_id]["new_name"],
            caption
        ))
        await message.reply_text("Added to Queue")
        user_data.pop(user_id)

async def main():
    for _ in range(WORKERS):
        asyncio.create_task(worker())
    await app.start()
    print("Bot Running")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
