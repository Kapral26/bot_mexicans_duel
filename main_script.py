# -*- coding: utf-8 -*-
from aiogram import Bot, Dispatcher, executor, types

from setting.bot_setting import BotSetting, WorkWithUser, CommandStart, tg_token

bot = Bot(token=tg_token, )
dp = Dispatcher(bot=bot, )

bot_setting = BotSetting()
work_with_user = WorkWithUser()
start_commands = CommandStart()


# TODO
# Необходимо ограничить декаратором список возможных команд.

@dp.message_handler(commands=['help', 'help2'])
async def send_menu(message: types.Message):
    """ Отправить список команд бота."""

    await message.reply(
            text='''
                    Бот для мексиканской дуэли имеет след. команды:
                    /start_duel - Запуск бота
                    /help -- увидеть это сообщение
                    /reg_usr - Зарегистрироваться в боте 
                    /lets_dance - Закрываем регистрацию на дуэль в текущем чате.
                    Запускать может только админимтраторы группы.
                    /stop_duel
                    
                    бла бла
                    ''',
            reply=False,
    )


@dp.message_handler(commands=['start_duel'])
async def start_duel(message: types.Message):
    # Поприветствовать
    msg_text = start_commands.start_message(message.chat)
    await message.reply(msg_text)


@dp.message_handler(commands=['reg_usr'])
async def register_user(message: types.Message):
    msg = work_with_user.chk_users(user=message.from_user, chat=message.chat)
    await message.reply(msg)


@dp.message_handler(commands=['lets_dance'])
async def register_user(message: types.Message):
    chat_admins = await bot.get_chat_administrators(message.chat.id)
    msg = "Lets dance every body."
    if message.from_user.username not in [x.user.username for x in chat_admins]:
        msg = f"Эта команда не для тебя, собака ты сутулая, да я тебе {message.from_user.username}"
    await message.reply(msg)


@dp.message_handler(content_types=types.ContentType.TEXT)
async def do_echo(message: types.Message):
    text = message.text
    if text and not text.startswith('/'):
        await message.reply(text=text)


def run():
    executor.start_polling(dispatcher=dp, )


if __name__ == '__main__':
    run()
