# -*- coding: utf-8 -*-

"""Настройки бота"""

import logging
import time
from random import randint

import psycopg2
from prettytable import from_db_cursor

from .config import tg_token, pg_connect

# Логирование
logging.basicConfig(filename="mexicans_duel.log", level=logging.ERROR,
                    format='%(levelname)s %(filename)s %(module)s.%(funcName)s | %(asctime)s: %(message)s', )


def log_error(func):
    """
    декортатор логирования
    :param func: функция
    :return:
    """

    def inner(*args, **kwargs):
        """
        внутренняя функция декоратора логирования
        """
        try:
            return func(*args, **kwargs)
        except Exception as error:
            print(f'{func.__name__}: {error}'.encode('utf8'))
            logging.error(f'{func.__name__}: {error}'.encode('utf8'))

    return inner


@log_error
def chk_user(func):
    """
    Декоратор для проверки есть ли пользователь в БД
    """

    def inner(*args, **kwargs):
        """
        Проверка пользователя и запись в лог его действия
        :param args:
        :param kwargs:
        :return:
        """
        if args[1].update_id:
            user = args[1].message.from_user.username
            first_name = args[1].message.from_user.first_name
            full_name = args[1].message.from_user.full_name
            chat_id = args[1].message.from_user.id
            w_user = WorkWithUser()
            w_user.chk_users(user, first_name, full_name)
            if '/' in args[1].message.text:
                logging.info(f'Пользователь: {user}, Запустил комаду: {args[1].message.text}, chat_id: {chat_id}')
        return func(*args, **kwargs)

    return inner


class PgConnect:
    def __init__(self, max_try_connect=0):
        self.__pg_connect = None
        self.max_try_connect = max_try_connect if max_try_connect > -1 else 0

    def pg_connection(self):
        """
        Подключение к pg
        """
        conn = psycopg2.connect(dbname=pg_connect['dbname'],
                                user=pg_connect['user'],
                                password=pg_connect['password'],
                                host=pg_connect['host'],
                                port=pg_connect['port'])

        cursor = conn.cursor()
        return {"conn": conn, "cur": cursor}

    @property
    def pg_connect(self):
        if self.__pg_connect:
            return self.__pg_connect
        else:
            self.__reconnect(True)
        return self.__pg_connect

    def connect_pg(self):
        self.__reconnect()

    def close_pg(self, rollback=False):
        if self.__pg_connect:
            try:
                if rollback:
                    self.pg_connect["conn"].rollback()
                else:
                    self.pg_connect["conn"].commit()
                    self.__pg_connect = None
            except Exception:
                pass

    def reconnect_pg(self):
        self.__reconnect(is_new=True)

    def commit_pg(self):
        if self.__pg_connect:
            self.pg_connect["conn"].commit()

    def rollback_pg(self):
        if self.__pg_connect:
            self.pg_connect["conn"].rollback()

    def __reconnect(self, is_new=False):
        try_connect = 0

        if try_connect < self.max_try_connect or is_new:
            while True:
                try:
                    try_connect += 1
                    if not is_new:
                        self.close_pg(rollback=True)

                    if is_new and try_connect > 1 or not is_new:
                        logging.debug(f"Try connect pg: {try_connect}")

                    self.__pg_connect = self.pg_connection()
                    return True
                except Exception:
                    if try_connect >= self.max_try_connect: raise
                    time.sleep(10)
        else:
            return False

    def _pg_execute(self, sql, params=(), commit=False):

        cur = self.pg_connect["cur"]
        con = self.pg_connect["conn"]

        try:
            cur.execute(sql, params)
        except:
            if commit:
                con.rollback()
            logging.error(f"PG error:\nsql:{sql}\nparams:{params if params else None}")
            raise
        finally:
            if commit:
                con.commit()

        return cur


class BotSetting(PgConnect):
    """
    Дополнительный класс для работы бота
    """

    def __init__(self):
        PgConnect.__init__(self)
        self.tg_token = tg_token

    def check_anything(self, query_sql):
        """Проверка всякого в БД.
        :return boll
        """
        query_result = self._pg_execute(query_sql).fetchone()
        if query_result and query_result[0] == True:
            return True
        else:
            return False

    def insert_main_phrase(self, text):
        """
        Добавление фразы для русской рулетки
        :param text: Текст с обязательным наличием @
         для указания в какое место необходимо вставить логин

        """
        text = text.replace('@', '@{user}')
        query_insert = f"""INSERT INTO public.main_words
                        (words)
                        VALUES('{text}')"""
        try:
            self._pg_execute(query_insert, commit=True)
            return True
        except Exception as error:
            logging.error(error)
            return False


class WorkWithUser(BotSetting):
    """
    Класс для работы с пользователями
    """

    def __init__(self):
        BotSetting.__init__(self)

    def chk_users(self, user, chat):
        """
        Проверка наличия пользователя в БД.
        если отсутствует добавляется.
        :param user: объект пользователя из message
        :param chat: объект чата из message
        :param full_name: Если в тг указано полное имя
        :return: id пользователя
        """

        if not self.get_duel_status(chat.id):
            return "Регистрация пользователей на дуэль закрыта."

        sql = f"""
            select u.id from users u 
            join public."userProfile" up on up."userId" = u.id
            where u."userName" = '{user.username}'
              and up."chatId" = {chat.id}"""
        result = self._pg_execute(sql).fetchone()

        if not result:
            self.add_user(user, chat)

        after_reg_msg = u"""
            Вы зарегитсрированы в мексиканской дуэле в данном чате.
            Ожидайте начала.
            """
        return after_reg_msg

    def get_duel_status(self, chat_id):
        query_sql = f"""SELECT duelisrunning FROM public."chatIdList" WHERE id = {chat_id}"""
        return self.check_anything(query_sql)

    def add_user(self, user, chat):
        """Добавление нового пользователя."""

        sql = f""" 
            SELECT insert_new_user('{user.username}',
                                   '{user.first_name}',
                                   '{user.full_name}', 
                                    {chat.id},
                                   '{chat.type}',
                                   '{chat.title}')
        """
        added_user = self._pg_execute(sql, commit=True)
        logging.info(f'В БД добавлен пользователь под ником "{user.username}"')
        return added_user.fetchone()

    # Olds scripts
    def chk_role_user(self, username):
        """
        Проверка ролей пользователя
        :param username: параметр из tg
        :return: bool
        """
        sql = f"""SELECT u.username, r.role_name
                    FROM users u 
                    JOIN roles r on r.id = u.role 
                    WHERE u.username = '{username}' 
                        AND r.role_name = 'user'"""

        result = self._pg_execute(sql).fetchone()
        return True if result else False

    def get_all_users(self):
        """
        Вывевсти всех пользоавтелей
        :return: список пользователей
        """
        sql = "SELECT id, username FROM public.users"
        return self._pg_execute(sql).fetchall()

    def calc_goes_fuck_to_self(self, goes, who_send):
        """
        Записать в БД кого послали нахуй, че тут еще писать-то?
        :param who_send: Кто отправил команду
        :param goes: id пользоавтеля из БД
        """
        sql = f"INSERT INTO public.fuck_your_selfs (user_id, who_send) VALUES({goes}, {who_send})"
        self._pg_execute(sql, commit=True)

    def get_report_fys(self, command_text):
        """
        Формирвоание статистики кого сколько раз послали нахуй
        :command_text -who выведется статистика кто сколько раз отпарвил команду
        :return: текст статисттики
        """

        command_text = command_text.split(" ")[1:]

        if '@' in command_text:
            command_text = command_text.split('@')[0]

        column = "user_id"
        if '-who' in command_text:
            column = "who_send"

        sql = f"""
            SELECT u.username,
                   count(fys.id)
            FROM public.users u
            LEFT JOIN public.fuck_your_selfs fys ON fys.{column} = u.id
            AND extract(YEAR
                        FROM fys.date_fuck_your_self) = extract(YEAR
                                                                FROM now())
            GROUP BY u.username
            ORDER BY count(fys.id) DESC"""
        mytable = from_db_cursor(self._pg_execute(sql))
        text = f"<code>Количество посыланий нахуй:\n{mytable}</code>"
        return text

    def get_user_for_rulet(self):
        """
        Выбрать пользоавтеля который сейчас будет послан нахуй
        :return: Пользователь
        """
        users = self.get_all_users()
        index_random_user = randint(0, len(users) - 1)
        user = users[index_random_user]
        return user

    def get_main_word(self):
        """
        Выбрать фразу которой пользователь будет послан нахуй
        :return: фраза из БД
        """
        sql = u"""SELECT words from public.main_words"""
        main_words = self._pg_execute(sql).fetchall()
        index_main_words = randint(0, len(main_words) - 1)
        main_word = main_words[index_main_words]
        return f'{main_word[0]}\n'


class CommandStart(BotSetting):
    def __init__(self):
        BotSetting.__init__(self)

    def check_exist_chat(self, chat_id):
        query_sql = f"""SELECT c."chatName" from public."chatIdList" c where c.id = {chat_id}"""
        return self.check_anything(query_sql)

    def start_message(self, chat):
        if chat.type == "private":
            msg_txt = """
            Привет, сложно будет устроить мексикансую дуэль с самим собой.
            Бота необходимо добавить в групповой чат и мб дать права админа.
            """
        else:
            first_phrase = "Бот тут впервые."

            if self.check_exist_chat(chat.id):
                first_phrase = "Я вижу ваш чат уже есть в базе, это великолепно."
            msg_txt = f"""
                Привет, {first_phrase}
                Теперь необходимо, что бы все участники чата, кто хочет участвовать должны
                зарегистрироваться, получить оружие, после чего можно будет начать.
                """

        return msg_txt


if __name__ == '__main__':
    BotSetting().pg_connect()
