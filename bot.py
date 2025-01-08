from aiogram import Bot, types
from aiogram.utils import executor
from aiogram.utils import exceptions as aiogram_exceptions
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import StatesGroup, State
import json
import speech_recognition as sr
import os
import subprocess
from datetime import datetime
from imageio_ffmpeg import get_ffmpeg_exe
from dotenv import load_dotenv
import data_base.utils as db
from gpt_util import chat_gpt_query

if os.path.isfile(".env"):
    load_dotenv()
    TOKEN = os.getenv("TOKEN")
else:
    with open(".env", "w") as file:
        file.write("TOKEN='bot_token'\nOPENAI_TOKEN='openai_token'\n"
                   "gpt_model='gpt_model'\nOPENAI_API_BASE='openai_api_base'")
    print("insert bot token in .env file")
    exit(0)

prompts = {}
with open("prompts.json", "r", encoding="utf-8") as file:
    prompts = json.load(file)

nl = "\n"


class States(StatesGroup):
    add_marker = State()
    add_note = State()
    search = State()
    del_note = State()
    edit_note = State()
    edit_note_text = State()
    choose_note_to_edit = State()
    add_marker_voice = State()
    add_note_voice = State()


bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())


@dp.message_handler(content_types=[types.ContentType.VOICE],
                    state=[States.search, States.add_marker, States.add_note, States.add_marker_voice,
                           States.add_note_voice])
async def voice_message_handler(message: types.Message, state: FSMContext):
    voice = await message.voice.get_file()
    file = await bot.download_file(voice.file_path)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    voice_filename = f"voice_{timestamp}.ogg"
    wav_filename = f"voice_{timestamp}.wav"

    with open(voice_filename, "wb") as f:
        f.write(file.getvalue())

    ffmpeg_exe = get_ffmpeg_exe()
    subprocess.run([ffmpeg_exe, '-i', voice_filename, wav_filename])

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_filename) as source:
        audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language="ru-RU")

    os.remove(voice_filename)
    os.remove(wav_filename)

    current_state = await state.get_state()
    if current_state == States.search.state:
        await bot.send_message(message.from_user.id, f"Распознанный текст: {text}\nИщу...")

        try:
            tree = db.get_tree(message.from_user.id)
            location = chat_gpt_query(prompts["ask_file_location"].format(text, tree))

            notes = db.get_notes_from_location(message.from_user.id, location) if location else None
            has_data = notes and isinstance(notes, list) and len(notes) > 0

            if has_data:
                answer = chat_gpt_query(prompts["read_file"].format(text, notes))
                await bot.send_message(
                    message.from_user.id,
                    f"📚 Ответ из базы знаний:\n\n{answer}",
                    parse_mode=None
                )
            else:
                prompt = prompts["generate_answer"].format(text)
                ai_response = chat_gpt_query(prompt)

                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("💾 Сохранить ответ в базу", callback_data="save_ai_response"))

                await state.update_data(ai_response=ai_response, user_query=text)

                await bot.send_message(
                    message.from_user.id,
                    f"🤖 Вот что я знаю:\n\n{ai_response}",
                    reply_markup=kb,
                    parse_mode=None
                )

        except Exception as err:
            print(f"От: {message.from_user.id}, Запрос: {text}\nОшибка: {err}")
            await bot.send_message(message.from_user.id, "🔄 Давайте попробуем переформулировать вопрос")
        finally:
            await state.finish()

    else:
        await bot.send_message(message.from_user.id, f"Распознанный текст: {text}")

        user_data = await state.get_data()

        head_catalog_id = user_data.get("head_marker_id")

        if current_state in ["States:add_catalog", "States:add_catalog_voice"]:
            if head_catalog_id:
                db.create_marker(message.from_user.id, text, head_catalog_id)
            else:
                db.create_marker(message.from_user.id, text)
            success_message = f"✅ | Каталог '{text}' добавлен!"
        elif current_state in ["States:add_note", "States:add_note_voice"]:
            if head_catalog_id:
                db.create_note(message.from_user.id, head_catalog_id, text)
                success_message = f"✅ | Знание '{text}' добавлено!"
            else:
                await bot.send_message(message.from_user.id,
                                       f"🗄 | Знание '{text}' не может быть создано тут(\n"
                                       f"🗄 | Выберите Каталог и создайте знание в нем")
                await state.finish()
                return

        exit_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️", callback_data=user_data.get("last_menu", "")))
        await bot.send_message(message.from_user.id, success_message, reply_markup=exit_kb)
        await state.finish()


@dp.callback_query_handler(lambda c: c.data.startswith('edit_note_'), state='*')
async def process_edit_note(callback_query: types.CallbackQuery, state: FSMContext):
    marker_id = callback_query.data.split('_')[-1]
    await state.update_data(editing_marker_id=marker_id)

    notes = db.get_notes(callback_query.from_user.id, marker_id)

    text = "Выберите номер знания для редактирования:\n"
    for i, note in enumerate(notes):
        text += f"{i}: {note['value'][:30]}...\n"

    await bot.edit_message_text(text, callback_query.from_user.id, callback_query.message.message_id)
    await States.choose_note_to_edit.set()


@dp.message_handler(state=States.choose_note_to_edit)
async def choose_note_to_edit(message: types.Message, state: FSMContext):
    try:
        note_index = int(message.text)
        user_data = await state.get_data()
        marker_id = user_data['editing_marker_id']
        notes = db.get_notes(message.from_user.id, marker_id)

        if 0 <= note_index < len(notes):
            note = notes[note_index]
            await state.update_data(editing_note_id=note['id'])
            await bot.send_message(
                message.from_user.id,
                f"Текущий текст:\n`{note['value']}`\nВведите новый текст:",
                parse_mode='Markdown'
            )
            await States.edit_note_text.set()
        else:
            await bot.send_message(message.from_user.id, "Неверный номер знания. Попробуйте еще раз.")
    except ValueError:
        await bot.send_message(message.from_user.id, "Пожалуйста, введите число.")


@dp.message_handler(state=States.edit_note_text)
async def save_edited_note(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    note_id = user_data['editing_note_id']
    new_text = message.text
    db.update_note(message.from_user.id, note_id, new_text)
    exit_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️", callback_data=user_data.get("last_menu", "")))
    await bot.send_message(message.from_user.id, "Знание успешно отредактировано!", reply_markup=exit_kb)
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == 'save_ai_response', state='*')
async def save_ai_response(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    ai_response = user_data.get('ai_response')

    # Check if "Ответы ИИ" folder exists, create if not
    ai_folder = None
    root_markers = db.get_root_markers(callback_query.from_user.id)

    for marker in root_markers:
        if marker.value == "Ответы ИИ":
            ai_folder = marker
            break

    if not ai_folder:
        ai_folder = db.create_marker(callback_query.from_user.id, "Ответы ИИ")

    # Save response in AI folder
    db.create_note(callback_query.from_user.id, ai_folder.id, ai_response)

    await bot.edit_message_text(
        "✅ Ответ сохранен в папке 'Ответы ИИ'!",
        callback_query.from_user.id,
        callback_query.message.message_id,
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("📁 Перейти к папке", callback_data=f"list_marker_{ai_folder.id}"),
            InlineKeyboardButton("⬅️ К списку", callback_data="list_marker_")
        )
    )
    await state.finish()


@dp.message_handler(commands=["start", "search"], state='*')
async def commands(message: types.Message, state: FSMContext):
    com = message.get_command()

    if com == '/start':
        try:
            await state.finish()
        except:
            pass

        start_kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("📕 Открыть хранилище данных", callback_data='list_marker_'))

        image_path = os.path.join('images', 'welcome.jpg')

        if os.path.exists(image_path):
            with open(image_path, 'rb') as photo:
                await bot.send_photo(
                    message.from_user.id,
                    photo=photo,
                    caption="🚀 Привет, я Знаниум, ваша умная система хранения и управления персональными знаниями на основе искусственного интеллекта прямо в Telegram! Какие планы на сегодня?",
                    reply_markup=start_kb
                )
        else:
            await bot.send_message(
                message.from_user.id,
                "🚀 Привет, я Знаниум, ваша умная система хранения и управления персональными знаниями на основе искусственного интеллекта прямо в Telegram! Какие планы на сегодня?",
                reply_markup=start_kb
            )

    if com == '/search':
        try:
            await state.finish
        except:
            pass
        await bot.send_message(message.from_user.id, "Что будем искать сегодня❓")
        await States.search.set()


@dp.message_handler(state=States.search)
async def state_case_met(message: types.Message, state: FSMContext):
    await bot.send_message(message.from_user.id, "Ищу...")
    try:
        tree = db.get_tree(message.from_user.id)
        location = chat_gpt_query(prompts["ask_file_location"].format(message.text, tree))
        data = None

        if location:
            data = db.get_notes_from_location(message.from_user.id, location)

        if data:
            # Database response - plain text
            answer = chat_gpt_query(prompts["read_file"].format(message.text, data))
            await bot.send_message(
                message.from_user.id,
                f"📚 Ответ из базы знаний:\n\n{answer}",
                parse_mode=None
            )
        else:
            # AI response with formatting and save button
            prompt = prompts["generate_answer"].format(message.text)
            ai_response = chat_gpt_query(prompt)

            # Create save button
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("💾 Сохранить ответ в базу", callback_data="save_ai_response"))

            # Save response for later use
            await state.update_data(ai_response=ai_response, user_query=message.text)

            # Send formatted response with button
            await bot.send_message(
                message.from_user.id,
                f"🤖 Сгенерированный ответ:\n\n{ai_response}",
                reply_markup=kb,
                parse_mode=None
            )

    except Exception as err:
        print(f"Ошибка: {err}")
        await bot.send_message(message.from_user.id, "🔄 Давайте попробуем переформулировать вопрос")
    finally:
        await state.finish()


@dp.message_handler(state=States.add_marker)
async def state_case_met(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if head_marker_id := user_data["head_marker_id"]:
        db.create_marker(message.from_user.id, message.text, head_marker_id)
    else:
        db.create_marker(message.from_user.id, message.text)

    exit_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️", callback_data=user_data["last_menu"]))
    await bot.send_message(message.from_user.id,
                           f"✅ | Каталог '{message.text}' добавлен!",
                           reply_markup=exit_kb)
    await state.finish()


@dp.message_handler(state=States.add_note)
async def state_case_met(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    if not (head_marker_id := user_data["head_marker_id"]):
        await bot.send_message(message.from_user.id,
                               f"🗄 | Знание '{message.text}' не может быть создано тут(\n"
                               f"🗄 | Выберите Каталог и создай знание в нем", )
    else:
        db.create_note(message.from_user.id, head_marker_id, message.text)
        exit_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️", callback_data=user_data["last_menu"]))
        await bot.send_message(message.from_user.id,
                               f"✅ | Знание '{message.text}' добавлено!",
                               reply_markup=exit_kb)
    await state.finish()


@dp.message_handler(state=States.del_note)
async def state_case_met(message: types.Message, state: FSMContext):
    await bot.send_message(message.from_user.id, f"Удаляю...", )
    user_data = await state.get_data()
    if not (marker_id := user_data["in_marker"]):
        await bot.send_message(message.from_user.id,
                               f"🚫 | Ошибка! Знание не удалено!", )
    else:
        kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️", callback_data=f"list_notes_{marker_id}"))
        try:
            db.delete_note_pos(user_id=message.from_user.id, marker_id=marker_id, note_pos=message.text)
            await bot.send_message(message.from_user.id,
                                   "✅ | Знание удалено!",
                                   reply_markup=kb)
        except Exception as err:
            print(f"From: {message.from_user.id}, {message.text}\n{err}")
            await bot.send_message(message.from_user.id,
                                   "🚫 | Не получилось далить знание!",
                                   reply_markup=kb)
    await state.finish()


@dp.callback_query_handler(lambda callback_query: True, state='*')
async def callback_inline(callback_query: types.CallbackQuery, state: FSMContext):
    if str(callback_query.data).startswith('list_marker_'):
        await state.update_data(last_menu=str(callback_query.data))
        markers_kb = InlineKeyboardMarkup()
        head_marker = str(callback_query.data).split("_")[-1]
        markers = db.get_child_markers(callback_query.from_user.id,
                                       head_marker) if head_marker else db.get_root_markers(callback_query.from_user.id)

        for marker in markers:
            markers_kb.add(InlineKeyboardButton(f"🗂 {marker.value}", callback_data=f"list_marker_{marker.id}"))

        if head_marker:
            markers_kb.row(InlineKeyboardButton("+🗄 Каталог", callback_data=f"add_marker_{head_marker}"),
                           InlineKeyboardButton("+🗒 Знание", callback_data=f"add_note_{head_marker}"))
            exit_marker = db.get_parent_marker(callback_query.from_user.id, head_marker)
            markers_kb.add(InlineKeyboardButton("📖 Моя база знаний", callback_data=f"list_notes_{head_marker}"))
            markers_kb.add(InlineKeyboardButton("❌ Удалить этот Каталог", callback_data=f"del_marker_{head_marker}"))
            markers_kb.add(InlineKeyboardButton("⬅️", callback_data=f"list_marker_{exit_marker or ''}"))
            marker_path = "/" + "/".join(db.get_path(callback_query.from_user.id, head_marker))
        else:
            markers_kb.add(InlineKeyboardButton("+🗄 Каталог", callback_data="add_marker_"))
            marker_path = "/"

        new_text = f"📚 Cписок Каталогов\nСейчас в {marker_path}"

        try:
            await bot.edit_message_text(new_text,
                                        callback_query.from_user.id,
                                        callback_query.message.message_id,
                                        reply_markup=markers_kb)
        except aiogram_exceptions.MessageNotModified:
            pass
        except aiogram_exceptions.BadRequest as e:
            if "There is no text in the message to edit" in str(e):
                await bot.send_message(callback_query.from_user.id, new_text, reply_markup=markers_kb)
            else:
                print(f"Unexpected BadRequest: {e}")

    if str(callback_query.data).startswith('list_notes_'):
        await state.update_data(last_menu=str(callback_query.data))
        notes_kb = InlineKeyboardMarkup()
        head_marker = str(callback_query.data).split("_")[-1]

        notes = db.get_notes(callback_query.from_user.id, head_marker)

        notes_kb.add(InlineKeyboardButton("+🗒 Добавить знание", callback_data=f"add_note_{head_marker}"))
        notes_kb.add(InlineKeyboardButton("✏️ Редактировать знание", callback_data=f"edit_note_{head_marker}"))
        notes_kb.add(InlineKeyboardButton("❌ Удалить знание", callback_data=f"del_note_{head_marker}"))
        exit_marker = db.get_parent_marker(callback_query.from_user.id, head_marker)
        notes_kb.add(InlineKeyboardButton("⬅️", callback_data=f"list_marker_{exit_marker}".replace("None", "")))
        marker_path = "/" + "/".join(db.get_path(callback_query.from_user.id, head_marker))
        await bot.edit_message_text(f"📚 Cписок знаний в {marker_path}:\n"
                                    f"{nl.join([i['value'] for i in notes])}",
                                    callback_query.from_user.id,
                                    callback_query.message.message_id,
                                    reply_markup=notes_kb)

    if str(callback_query.data).startswith('add_marker_'):
        await States.add_marker.set()
        if head_marker_id := str(callback_query.data).split("_")[-1]:
            await state.update_data(head_marker_id=head_marker_id)
        else:
            await state.update_data(head_marker_id="")

        await bot.edit_message_text("✏️ Введите название Каталога.\nℹ️ Для отмены действия - /start",
                                    callback_query.from_user.id,
                                    callback_query.message.message_id)

    if str(callback_query.data).startswith('add_note_'):
        await States.add_note.set()
        if head_marker_id := str(callback_query.data).split("_")[-1]:
            await state.update_data(head_marker_id=head_marker_id)
        else:
            await state.update_data(head_marker_id="")

        await bot.edit_message_text("✏️ Введите текст знания.\nℹ️ Для отмены действия - /start",
                                    callback_query.from_user.id,
                                    callback_query.message.message_id)

    if str(callback_query.data).startswith('del_marker_'):
        await state.update_data(last_menu=str(callback_query.data))
        if marker_id := str(callback_query.data).split("_")[-1]:
            kb = InlineKeyboardMarkup().add(InlineKeyboardButton("⬅️", callback_data=f"list_marker_"))
            try:
                db.delete_marker(user_id=callback_query.from_user.id, marker_id=marker_id)
                await bot.edit_message_text("✅ | Каталог удалён.",
                                            callback_query.from_user.id,
                                            callback_query.message.message_id,
                                            reply_markup=kb)
            except Exception as err:
                print(f"From: {callback_query.from_user.id}, {callback_query.data}\n{err}")
                await bot.edit_message_text("🚫 | Не получилось удалить Каталог!",
                                            callback_query.from_user.id,
                                            callback_query.message.message_id,
                                            reply_markup=kb)

    if str(callback_query.data).startswith('del_note_'):
        await States.del_note.set()
        await state.update_data(last_menu=str(callback_query.data))
        head_marker = str(callback_query.data).split("_")[-1]

        notes = db.get_notes(callback_query.from_user.id, head_marker)

        marker_path = "/" + "/".join(db.get_path(callback_query.from_user.id, head_marker))
        text = f"🗄 | Cписок знаний в {marker_path}:\n"
        for i in range(len(notes)):
            text += nl + f"{i}: {notes[i]['value']}"

        text += "\n❓ Какое знание вы хотите удалить, введите номер\nℹ️ Для отмены действия - /start"
        await bot.edit_message_text(text,
                                    callback_query.from_user.id,
                                    callback_query.message.message_id)

        await state.update_data(in_marker=head_marker)

    await bot.answer_callback_query(callback_query.id)


if __name__ == '__main__':
    executor.start_polling(dp)
