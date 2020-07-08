import asyncio
import re
import string

import comments
import config
import random
import messages
import aiosqlite
import transactions
from vkbottle import Bot, Message, User
from vkbottle.api.keyboard import keyboard_gen
from vkbottle.keyboard import Text, Keyboard
from vkbottle.branch import ExitBranch

bot = Bot(config.token)
user = User(config.acces_token)
qiwi = transactions.Qiwi()


async def check_or_register_user(user_id: int):
    """
    Регистрирует пользователя, если его еще нет в базе данных.
    :param user_id: id пользователя, кого надо зарегистрировать
    """
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT user_id FROM Users WHERE user_id = {user_id}')
    res = await cursor.fetchone()
    if res is None:
        cursor = await conn.cursor()
        await cursor.execute('INSERT INTO Users(user_id)'
                             'VALUES (?)', (user_id,))
        await conn.commit()
        await cursor.close()
    await cursor.close()


async def get_profile(user_id: int):
    """
    :param user_id: id пользователя, у кого надо вернуть данные.
    :return: Данные о пользователе. А именно: его баланс,
                                                  никнейм,
                                                  кол-во купленных билетов,
                                                  номер киви кошелька,
                                                  кол-во выигрышей

    """
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(
        f'SELECT balance, nickname, buy_ticket, qiwi_number, wins FROM Users WHERE user_id = {user_id}'
    )
    res = await cursor.fetchone()
    await cursor.close()
    return res


async def editProfile(user_id, value, column):
    """
    Изменяет значение строки на value в колонке column
    :param user_id: id пользователя, у кого надо поменять значение
    :param value: Значение на которое нужно поменят
    :param column: Название колонки, где нужно поменять значение
    """
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'UPDATE Users SET \'{column}\' = \'{value}\' WHERE user_id = {user_id}')
    await conn.commit()
    await cursor.close()


async def balanceManipulation(user_id, act, amount):
    """
    :param user_id
    :param act
    :param amount
    :type user_id: int
    :type act: str
    :type amount: int
    """
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    if act == 'pay':
        await cursor.execute(f'UPDATE Users SET balance=balance+{amount} WHERE user_id = {user_id}')
        await conn.commit()
        await cursor.close()
    elif act == 'withdraw':
        await cursor.execute(f'SELECT balance FROM Users WHERE user_id = {user_id}')
        balance = await cursor.fetchone()
        if balance[0] > amount:
            await cursor.execute(f'UPDATE Users SET balance=balance-{amount} WHERE user_id = {user_id}')
            await conn.commit()
            await cursor.close()
            return True
        return False


async def checkTable(tableName):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT count(*) FROM sqlite_master WHERE type=\'table\' AND name=\'{tableName}\'')
    res = await cursor.fetchone()
    await cursor.close()
    return bool(res[0])


async def pullRaffles(status: str, limitStart: int = 0) -> list:
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT * FROM Raffles WHERE status = \'{status}\' LIMIT {limitStart}, 5')
    res = await cursor.fetchall()
    await cursor.close()
    return res


async def createTable(tableName):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'CREATE TABLE IF NOT EXISTS {tableName} '
                         f'(billId	TEXT,'
                         f' amount INTEGER)')
    await cursor.close()


async def forTransaction(tableName, act, billId=None, amount=None):
    """
    Добавляет значение billId, чтобы в дальнейшем пользователь смог проверять состояние своего платежа,
    а так же отменять счет.
    :param amount: На сколько рублей хочет пополнить свой баланс пользователь
    :param act: Что нужно сделать с помощью этой функции. Доступные аргументы: insert, pull
    :param tableName: Название таблицы с транзакцией
    :param billId: id счета
    :return Может вернуть последний billId, если в act указано pull
    """
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    if act == 'insert':
        await cursor.execute(f'INSERT INTO \'{tableName}\'(billId, amount) VALUES (?, ?)', (billId, amount,))
        await conn.commit()
    elif act == 'pull':
        await cursor.execute(f'SELECT * FROM \'{tableName}\'')
        res = await cursor.fetchall()
        await cursor.close()
        return res[-1]


async def boughtTicket(raffleId):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT user_id FROM Raffle_{raffleId}')
    bought: list = await cursor.fetchall()
    return len(bought)


async def countTicket(raffleId):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT count_tickets FROM Raffles WHERE id = {raffleId}')
    count = await cursor.fetchone()
    return count[0]


async def addTicket(user_id, raffleId, ticketCount):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    for ticket in range(ticketCount):
        await cursor.executescript(f"""
           UPDATE Users SET buy_ticket=buy_ticket+1 WHERE user_id = {user_id};
            
           INSERT INTO Raffle_{raffleId} (user_id) VALUES ({user_id});
        """)
    await cursor.close()


async def getWinner(raffleId):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT * FROM Raffle_{raffleId}')
    res = await cursor.fetchall()
    random.shuffle(res)
    listUsers = random.choices(res, k=3)
    winner = random.choice(listUsers)
    await cursor.execute(f'UPDATE Raffles SET \'status\' = \'pass\', '
                         f'winner = {winner[1]} WHERE id = 1')
    await conn.commit()
    await cursor.close()
    return winner


async def winnerNickname(winnerId):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT nickname FROM Users WHERE user_id = {winnerId}')
    winner = await cursor.fetchone()
    return winner


async def usersWinRaffle(raffleId, winnerId):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT user_id FROM Raffle_{raffleId}')
    res = await cursor.fetchall()
    return [participant[0] for participant in list(set(res)) if participant[0] != winnerId]


async def checkBalance(user_id):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT balance FROM Users WHERE user_id = {user_id}')
    res = await cursor.fetchone()
    return res[0]


async def create_keyboard(text=None, user_id=None):
    keyboard = Keyboard(one_time=True, inline=False)
    if text == 'help':
        keyboard.add_row()
        keyboard.add_button(Text('Помощь'), color='negative')
        return keyboard.generate()
    elif text == 'to_menu':
        keyboard.add_row()
        keyboard.add_button(Text('Меню'), color='negative')
        return keyboard.generate()
    elif text == 'меню':
        keyboard.add_row()
        keyboard.add_button(Text('Активные розыгрыши'), color='primary')
        keyboard.add_row()
        keyboard.add_button(Text('Прошедшие розыгрыши'), color='primary')
        keyboard.add_row()
        keyboard.add_button(Text('Профиль'), color='secondary')
        keyboard.add_row()
        keyboard.add_button(Text('Связаться'), color='secondary')
        keyboard.add_row()
        keyboard.add_button(Text('Помощь'), color='negative')
        if user_id in config.admins:
            keyboard.add_row()
            keyboard.add_button(Text('Admin panel🔒'), color='primary')
        return keyboard.generate()
    elif text == 'профиль':
        # _, nickname, _, qiwi_number, _ = await get_profile(user_id)
        keyboard.add_row()
        keyboard.add_button(Text('Пополнить баланс'), color='positive')
        keyboard.add_row()
        keyboard.add_button(Text('Вывод средств'), color='positive')
        keyboard.add_row()
        keyboard.add_button(Text('Добавить/изменить никнейм'), color='primary')
        keyboard.add_row()
        keyboard.add_button(Text('Добавить/изменить номер'), color='primary')
        keyboard.add_row()
        keyboard.add_button(Text('Меню'), color='negative')
        return keyboard.generate()
    elif text == 'cancel_transaction':
        keyboard.add_row()
        keyboard.add_button(Text('Проверить'), color='positive')
        keyboard.add_button(Text('Отменить'), color='negative')
        return keyboard.generate()
    elif text == 'edit':
        keyboard = Keyboard(one_time=False, inline=True)
        keyboard.add_row()
        keyboard.add_button(Text('Профиль'), color='secondary')
        keyboard.add_row()
        keyboard.add_button(Text('Меню'), color='negative')
        return keyboard.generate()
    elif text == 'admin panel🔒' and user_id in config.admins:
        keyboard.add_row()
        keyboard.add_button(Text('Добавить розыгрыш', payload='add_raffle'), color='primary')
        keyboard.add_row()
        keyboard.add_button(Text('Рассылка'), color='primary')
        keyboard.add_row()
        keyboard.add_button(Text('Информация о пользователях'), color='primary')
        keyboard.add_row()


@bot.on.message()
async def message(ans: Message):
    if ans.payload == '{\"command\":\"start\"}':
        await ans(
            random.choice(messages.greeting),
            keyboard=await create_keyboard('help')
        )
    if ans.payload is None:
        await ans(
            'Я тебя не понял.\nВозвращайся лучше в меню.',
            keyboard=await create_keyboard('to_menu')
        )
    try:
        if 'nextpass' in ans.payload:
            payloadNum = int(re.sub(r'[nextpass{:"}]', '', ans.payload))
            passList: list = await pullRaffles('pass', payloadNum)
            if len(passList) > 4:
                for raffle in passList[:-1]:
                    raffleId, prize, _, _, winnerId = raffle
                    conn = await aiosqlite.connect('Database/database.db')
                    cursor = await conn.cursor()
                    await cursor.execute(f'SELECT nickname FROM Users WHERE user_id = {winnerId}')
                    winnerNick = await cursor.fetchone()
                    if winnerNick[0] == 'не задан':
                        name = await bot.api.users.get(user_ids=winnerId)
                        winnerNick = str(name[0].first_name) + ' ' + str(name[0].last_name)
                    else:
                        winnerNick = winnerNick[0]
                    await ans(
                        f'--Розыгрыш №{raffleId}--\n'
                        f'Призовой фонд: {prize} руб\n'
                        f'Победитель: [id{winnerId}|{winnerNick}]'
                    )
                payload = f'[_nextpass_:_{payloadNum + 4}_]'
                payload = payload.replace('_', '\"').replace('[', '{').replace(']', '}')
                await ans(
                    'Это еще не целый список.\n'
                    'Жми далее, чтобы увидеть больше!',
                    keyboard=keyboard_gen(
                        [
                            [
                                {'text': 'Меню', 'color': 'negative'},
                                {'text': 'Далее', 'color': 'primary', 'payload': payload}]
                        ],
                        inline=True
                    )
                )
            else:
                for raffle in passList:
                    raffleId, prize, _, _, winnerId = raffle
                    conn = await aiosqlite.connect('Database/database.db')
                    cursor = await conn.cursor()
                    await cursor.execute(f'SELECT nickname FROM Users WHERE user_id = {winnerId}')
                    winnerNick = await cursor.fetchone()
                    if winnerNick[0] == 'не задан':
                        name = await bot.api.users.get(user_ids=winnerId)
                        winnerNick = str(name[0].first_name) + ' ' + str(name[0].last_name)
                    else:
                        winnerNick = winnerNick[0]
                    await ans(
                        f'--Розыгрыш №{raffleId}--\n'
                        f'Призовой фонд: {prize} руб\n'
                        f'Победитель: [id{winnerId}|{winnerNick}]'
                    )
                await ans(
                    'На этом все.\n'
                    'Больше нет прошедших розыгрышей.',
                    keyboard=await create_keyboard('to_menu')
                )
        elif 'nextactive' in ans.payload:
            payloadNum = int(re.sub(r'[nextactive{:"}]', '', ans.payload))
            activeList: list = await pullRaffles('active', payloadNum)
            if len(activeList) > 4:
                for raffle in activeList[:-1]:
                    raffleId, prize, count, _, _ = raffle
                    bought = await boughtTicket(raffleId)
                    payload = f'[_active_:_{raffleId}_]'
                    payload = payload.replace('_', '\"').replace('[', '{').replace(']', '}')
                    await ans(
                        f'--Розыгрыш №{raffleId}--\n'
                        f'Призовой фонд: {prize}\n'
                        f'Стоимость 1 тикета: {int(prize / count)} руб\n'
                        f'Куплено тикетов {bought} из {count}.',
                        keyboard=keyboard_gen(
                            [
                                [{'text': 'Участвовать', 'color': 'positive', 'payload': payload}]
                            ],
                            inline=True
                        )
                    )
                payload = f'[_nextactive_:_{payloadNum + 4}_]'
                payload = payload.replace('_', '\"').replace('[', '{').replace(']', '}')
                await ans(
                    'Это еще не целый список.\n'
                    'Жми далее, чтобы увидеть больше!',
                    keyboard=keyboard_gen(
                        [
                            [
                                {'text': 'Меню', 'color': 'negative'},
                                {'text': 'Далее', 'color': 'primary', 'payload': payload}]
                        ],
                        inline=True
                    )
                )
            else:
                for raffle in activeList:
                    raffleId, prize, count, _, _ = raffle
                    bought = await boughtTicket(raffleId)
                    payload = f'[_active_:_{raffleId}_]'
                    payload = payload.replace('_', '\"').replace('[', '{').replace(']', '}')
                    await ans(
                        f'--Розыгрыш №{raffleId}--\n'
                        f'Призовой фонд: {prize}\n'
                        f'Стоимость 1 тикета: {int(prize / count)} руб\n'
                        f'Куплено тикетов {bought} из {count}.',
                        keyboard=keyboard_gen(
                            [
                                [{'text': 'Участвовать', 'color': 'positive', 'payload': payload}]
                            ],
                            inline=True
                        )
                    )
                await ans(
                    'Увы.\n'
                    'Список активных розыгрышей закончился.',
                    keyboard=await create_keyboard('to_menu')
                )
    except TypeError:
        pass
    await check_or_register_user(ans.from_id)


@bot.on.message_handler(text='помощь', lower=True)
async def help_hendler(ans: Message):
    await ans(
        random.choice(messages.helping)
    )
    await ans(
        'https://vk.cc/avIrbJ',
        keyboard=await create_keyboard('to_menu')
    )


@bot.on.message_handler(text='меню', lower=True)
async def menu(ans: Message):
    await ans(
        'Главное меню.\nВыбери интересующий тебя раздел.',
        keyboard=await create_keyboard(ans.text.lower(), ans.from_id)
    )


@bot.on.message_handler(text='профиль', lower=True)
async def profile(ans: Message):
    balance, nickname, buy_ticket, qiwi_number, wins = await get_profile(ans.from_id)
    str_qiwi = ''
    if qiwi_number == 'не задан':
        qiwi_number += ' ✘'
        str_qiwi += '\n\nТак как у тебя не задан номер QIWI кошелька,' \
                    ' то ты не сможешь вывести деньги со своего баланса. Имей ввиду.\n' \
                    'Если у тебя еще нет кошелька, то обязательно заведи на сайте qiwi.com и ' \
                    'Получи статус «Основной»\nПосле этого добавь свой номер' \
                    ' с помощью соответсвующей кнопки ниже.'
    if nickname == 'не задан':
        nickname += ' ✘'
    name = await bot.api.users.get(user_ids=ans.from_id)
    await ans(
        'Имя и фамилия: ' + str(name[0].first_name) + ' ' + str(name[0].last_name) +
        '\nБаланс: ' + str(balance) + ' руб.' +
        '\nНикнейм: ' + nickname +
        '\nКуплено тикетов за все время: ' + str(buy_ticket) +
        '\nНомер кошелька QIWI: ' + str(qiwi_number) +
        '\nПобед за все время: ' + str(wins) + str_qiwi,
        keyboard=await create_keyboard(ans.text.lower(), ans.from_id)
    )


@bot.on.message_handler(text='Пополнить баланс', lower=True)
async def payBalance1(ans: Message):
    await ans(
        'Введи сумму пополнения(целое число).'
        '\nМинимальная сумма пополнения 10 руб.',
        keyboard=await create_keyboard('to_menu')
    )
    await bot.branch.add(ans.peer_id, 'Balance')


@bot.branch.simple_branch('Balance')
async def payBalance2(ans: Message):
    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu(ans)
        return
    if ans.text.isdigit() and int(ans.text) >= 10:
        await ans(
            f'Ты хочешь пополнить свой баланс на {ans.text} руб?\n'
            f'Если ты передумал, то введи число заново.',
            keyboard=keyboard_gen(
                [
                    [{'text': 'Меню', 'color': 'negative'}, {'text': 'Далее', 'color': 'positive'}]
                ],
                inline=True
            )
        )
        await bot.branch.exit(ans.peer_id)
        await bot.branch.add(ans.peer_id, 'payBalance', amount=int(ans.text))
    else:
        await ans(
            f'Неверный формат ввода данных.\n'
            f'Вот тебе совет:\n'
            f'  •Ты должен ввести число\n'
            f'  •Число должно быть целым и без всяких знаков\n'
            f'  •Число должно быть больше 10\n'
            f'Надеюсь, что ты сейчас введешь правильное число.',
            keyboard=await create_keyboard('to_menu')
        )


@bot.branch.simple_branch('payBalance')
async def payBalance3(ans: Message, amount):
    tableName = f'transaction_{ans.peer_id}'
    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu(ans)
        return
    elif ans.text.lower() == 'отменить':
        billId, _ = await forTransaction(tableName, 'pull')
        await qiwi.reject(billId)
        await ans(
            'Счет отменен.\n'
            'Предыдущая ссылка теперь больше недоступна.'
        )
        await ans('Произвожу выход в меню.')
        await bot.branch.exit(ans.peer_id)
        await asyncio.sleep(1)
        await menu()
        return
    elif ans.text.lower() == 'проверить':
        billId, _ = await forTransaction(tableName, 'pull')
        status = await qiwi.status(billId)
        if status == 'WAITING':
            await ans(
                'Ты еще не заплатил мне свои деньги.\nВозвращайся сюда,'
                ' когда ты оплатишь по ссылке, которую я тебе уже скидывал.',
                keyboard=keyboard_gen(
                    [
                        [{'text': 'Отменить', 'color': 'negative'}, {'text': 'Проверить', 'color': 'positive'}]
                    ],
                    inline=True
                )
            ),
        elif status == 'PAID':
            _, count = await forTransaction(tableName, 'pull')
            await balanceManipulation(ans.from_id, 'pay', count)
            await ans(
                'Отлично!\n'
                'Я получил твои деньги, теперь у тебя баланс пополнен и ты можешь покупать тикеты.',
                keyboard=await create_keyboard('to_menu')
            )
    elif ans.text.lower() == 'далее':
        await createTable(tableName)
        billId = lambda: ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
        billId = str(billId())
        amount = amount
        comment = comments.random_comment()
        await forTransaction(tableName, 'insert', billId, amount)
        payUrl = await qiwi.payBalance(
            billId,
            amount,
            f'Счет для пополнения баланса.\n'
            f'Комментарий к оплате: {comment}'
        )
        await ans(
            f'Составлен счет для пополнения баланса.\nПерейди по ссылке {payUrl}'
            f' и пополни счет, потом возвращайся сюда, чтобы нажать на кнопку «Проверить».'
            f'\nИ да. Не забудь сверить комментарий к оплате. Для тебя он вот: {comment}.',
            keyboard=keyboard_gen(
                [
                    [{'text': 'Отменить', 'color': 'negative'}, {'text': 'Проверить', 'color': 'positive'}]
                ],
                inline=True
            )
        )
    else:
        if not await checkTable(tableName):
            await payBalance2(ans)
        if await checkTable(tableName):
            await ans(
                f'Что такое этот ваш {ans.text}?\n'
                f'Я тебя не понял.\nНиже я прикрепил кнопки, на которые я точно тебе отвечу.',
                keyboard=keyboard_gen(
                    [
                        [{'text': 'Отменить', 'color': 'negative'}, {'text': 'Проверить', 'color': 'positive'}]
                    ],
                    inline=True
                )
            )


@bot.on.message_handler(text='вывод средств', lower=True)
async def payOut(ans: Message):
    balance, _, _, number, _ = await get_profile(ans.from_id)
    if number == 'не задан':
        await ans(
            'Ты не можешь вывести средства с баланса, так как у тебя не указан номер QIWI кошелька.\n'
            'Возвращайся сюда, когда добавишь свой номер, куда намереваешься перевести деньги со своего баланса.',
            keyboard=await create_keyboard('edit')
        )
    else:
        await ans(
            'Введи сумму для снятия средств с баланса.\n'
            'Требования для успешного перевода на твой QIWI кошелек:\n'
            '•У тебя на балансе больше 10 руб\n'
            '•Вводить только целое число, без каких либо символов\n'
            '•Введеная цифра не должна быть больше баланса и равной(из-за 2% комиссии)',
            keyboard=await create_keyboard('edit')
        )
        await bot.branch.add(ans.peer_id, 'payOut', balance=balance, number=number)


@bot.branch.simple_branch('payOut')
async def branchPayOut(ans: Message, balance, number):
    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu(ans)
        return ExitBranch()
    if ans.text.lower() == 'профиль':
        await bot.branch.exit(ans.peer_id)
        await profile(ans)
        return ExitBranch()
    if ans.text.isdigit():
        if int(ans.text) > 10:
            if balance >= 10:
                if int(ans.text) + (int(ans.text) * 0.02) <= balance:
                    res = await qiwi.moneyTransfer(int(ans.text), f'+{number}', 'Перевод средств с баланса профиля'
                                                                                ' на счет QIWI')
                    try:
                        if res['transaction']['state']['code'] == 'Accepted':
                            await ans(
                                'Средства с баланса успешно переведены на твой QIWI кошелек!\n',
                                keyboard=await create_keyboard('to_menu')
                            )
                        else:
                            await ans(
                                'Средства не переведены. \nУвы..',
                                keyboard=await create_keyboard('to_menu')
                            )
                    except KeyError:
                        await ans(
                            f'У [id{ans.from_id}|пользователя] случилась проблемка.\n'
                            f'Вот ответ сервера:\n{res}',
                            user_ids=config.admins,
                            keyboard=await create_keyboard('to_menu')
                        )
                        await ans(
                            'Что-то пошло не так.\n'
                            'Попробуй повторить тоже самое через некоторое время, либо свяжись с администратором.',
                            keyboard=await create_keyboard('to_menu')
                        )
                else:
                    await ans(
                        'Почему-то ты ввел значение отличающееся от баланса.\n'
                        'Введи, пожалуйста, цифру, которая меньше, либо равна твоему балансу.',
                        keyboard=await create_keyboard('edit')
                    )
            else:
                await ans(
                    'Твой баланс меньше 10 руб.\n'
                    'Так что сори. Как нибудь в другой раз(На самом деле тогда, когда у тебя баланс будет больше'
                    ' 10 руб.)',
                    keyboard=await create_keyboard('edit')
                )
        else:
            await ans(
                'Ты ввел число меньше 10.\n'
                'Введи число больше 10.',
                keyboard=await create_keyboard('edit')
            )
    else:
        await ans(
            f'Введи, пожалуйста, целое число, а не «{ans.text}».\n'
            f'Спасибо за понимание.',
            keyboard=await create_keyboard('edit')
        )


@bot.on.message_handler(text='добавить/изменить номер', lower=True)
async def editNumber(ans: Message):
    await ans(
        'Напиши свой номер из QIWI кошелька(номер телефона, зарегистрированный в QIWI), куда придут '
        'деньги в случае твоей победы.\nНомер должен начинаться с 7, не должен иметь никаких знаков, '
        'длина 11 цифр.\nПример: 7900500333123',
        keyboard=await create_keyboard('edit')
    )
    await bot.branch.add(ans.peer_id, 'editNumber')


@bot.branch.simple_branch('editNumber')
async def branchEditNumber(ans: Message):
    if ans.text.isdigit() and len(ans.text) == 11 and ans.text.startswith('7'):
        await editProfile(ans.from_id, ans.text, 'qiwi_number')
        await ans(
            'Номер успешно привязан!\nТеперь можешь обратно вернуться в свой профиль.',
            keyboard=await create_keyboard('edit')
        )
        await bot.branch.exit(ans.peer_id)
        return
    else:
        await ans(
            'Номер невалидный!\nНомер должен:\n•Содержать только цифры и начинаться на 7(без +)\n•Длина 11 цифр.',
            keyboard=await create_keyboard('edit')
        )

    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu(ans)
        return
    if ans.text.lower() == 'профиль':
        await bot.branch.exit(ans.peer_id)
        await profile(ans)
        return


@bot.on.message_handler(text='добавить/изменить никнейм', lower=True)
async def editNickname(ans: Message):
    await ans(
        'Напиши никнейм, который будет высвечиваться в профиле.\nНикнейм будет виден всем, в случае твоей победы.\n'
        'Не стоит выпендриваться со всяческими символами и шрифтами(𝑒𝓍𝒶𝓂𝓅𝓁𝑒 - плохой пример).\nНе у всех есть поддержка'
        ' подобных шрифтов и символов. Чем проще, тем лучше.\nЕсли не можешь придумать себе ник, то воспользуйся'
        ' сайтом https://nick-name.ru/ru/generate\nДействуй!',
        keyboard=await create_keyboard('edit')
    )
    await bot.branch.add(ans.peer_id, 'editNickname')


@bot.branch.simple_branch('editNickname')
async def branchEditNickname(ans: Message):
    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu(ans)
        return
    if ans.text.lower() == 'профиль':
        await bot.branch.exit(ans.peer_id)
        await profile(ans)
        return
    await editProfile(ans.from_id, ans.text, 'nickname')
    await ans(
        'Ваш никнейм успешно сменен!\nТеперь можешь обратно вернуться в свой профиль.',
        keyboard=await create_keyboard('edit')
    )
    await bot.branch.exit(ans.peer_id)


@bot.on.message_handler(text='связаться', lower=True)
async def contact(ans: Message):
    await ans(
        'Если у тебя что-то случилось, то ты всегда можешь обратиться за помощью к моему разработчику.\n'
        'Вот ссылка на него: https://vk.cc/avIrel\n'
        'Думаю, что ответ быстро придет.\n'
        'Но на некоторые вопросы уже есть ответ в документации, которая доступна по ссылке: https://vk.cc/avIrbJ',
        keyboard=await create_keyboard('to_menu')
    )


@bot.on.message_handler(text='активные розыгрыши', lower=True)
async def activeRaffles(ans: Message):
    activeList: list = await pullRaffles('active')
    if len(activeList) == 0:
        await ans(
            'На данный момент пока нет активных розыгрышей..\n'
            'Жди уведомление о появлении нового розыгрыша.',
            keyboard=await create_keyboard('to_menu')
        )
    elif len(activeList) > 4:
        for raffle in activeList[:-1]:
            raffleId, prize, count, _, _ = raffle
            bought = await boughtTicket(raffleId)
            payload = f'[_active_:_{raffleId}_]'
            payload = payload.replace('_', '\"').replace('[', '{').replace(']', '}')
            await ans(
                f'--Розыгрыш №{raffleId}--\n'
                f'Призовой фонд: {prize}\n'
                f'Стоимость 1 тикета: {int(prize / count)} руб\n'
                f'Куплено тикетов {bought} из {count}.',
                keyboard=keyboard_gen(
                    [
                        [{'text': 'Участвовать', 'color': 'positive', 'payload': payload}]
                    ],
                    inline=True
                )
            )
        await ans(
            'Это еще не целый список.\n'
            'Жми далее, чтобы увидеть больше!',
            keyboard=keyboard_gen(
                [
                    [
                        {'text': 'Меню', 'color': 'negative'},
                        {'text': 'Далее', 'color': 'primary', 'payload': "{\"nextactive\":\"4\"}"}]
                ],
                inline=True
            )
        )


@bot.on.message_handler(text='участвовать', lower=True)
async def takePart(ans: Message):
    if ans.payload is None:
        await ans(
            'Я шото не понял.\n'
            'Почему ты ввел с клавиатуры слово «Участвовать»?\n'
            'Я пойму тебя, если ты выберешь нужный для тебя розыгрыш и нажмешь на кнопку ниже.\n'
            '(Она если что подписана «Участвовать»)\n'
            'Надеюсь ты меня понял.',
            keyboard=await create_keyboard('to_menu')
        )
    else:
        payloadNum = int(re.sub(r'[active{:"}]', '', ans.payload))
        bought = await countTicket(payloadNum) - await boughtTicket(payloadNum)
        await ans(
            f'Если ты хочешь купить тикет(ы) для участия в розыгрыше №{payloadNum}, '
            f'то ты просто должен ввести их кол-во.\n\n'
            f'Доступное кол-во тикетов для покупки: {bought}',
            keyboard=await create_keyboard('to_menu')
        )
        await bot.branch.add(ans.peer_id, 'buyTickets', raffleId=payloadNum)


@bot.branch.simple_branch('buyTickets')
async def buyTickets(ans: Message, raffleId):
    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu(ans)
        return
    bought = await countTicket(raffleId) - await boughtTicket(raffleId)
    if ans.text.isdigit():
        if bought >= int(ans.text) > 0:
            conn = await aiosqlite.connect('Database/database.db')
            cursor = await conn.cursor()
            await cursor.execute(f'SELECT prize, count_tickets FROM Raffles WHERE id = {raffleId}')
            res = await cursor.fetchone()
            prize, count_ticket = res
            if await balanceManipulation(ans.from_id, 'withdraw', int((prize / count_ticket) * int(ans.text))):
                await addTicket(ans.from_id, raffleId, int(ans.text))
                await ans(
                    f'Ты успешно купил тикеты!\n'
                    f'С твоего баланса списано {int((prize / count_ticket) * int(ans.text))} руб.\n'
                    f'Теперь жди оглашения результатов.\n'
                    f'Good luck🤑',
                    keyboard=await create_keyboard('to_menu')
                )
                if int(ans.text) == bought:
                    ticketId, winner = await getWinner(raffleId)
                    await balanceManipulation(winner, 'pay', prize)
                    winnernickname = await winnerNickname(winner)
                    if winnernickname[0] == 'не задан':
                        name = await bot.api.users.get(user_ids=winner)
                        winnernickname = str(name[0].first_name) + ' ' + str(name[0].last_name)
                    else:
                        winnernickname = winnernickname[0]
                    await ans(
                        f'Розыгрыш №{raffleId} завершен!\n'
                        f'Победителем стал {winnernickname}. Его тикет под номером {ticketId}'
                        f' стал выигрышным.\n'
                        f'💸💸💸💸💸💸💸💸',
                        user_ids=await usersWinRaffle(raffleId, winner)
                    )
                    await ans(
                        'Прими мои поздравления!\n'
                        'Ты выиграл в розыгрыше №{raffleId}🥳\n'
                        'Денюжки уже прилетели на твой баланс.\n'
                        '💸💸💸💸💸💸💸💸',
                        user_id=winner
                    )
                    user.api.wall.post(
                        owner_id=config.group_id,
                        from_group=1,
                        message=f'Только что {winnernickname} стал победителем розыгрыша!\n'
                                f''
                    )
            else:
                await ans(
                    'Твой баланс не позволяет приобрести такое кол-во тикетов.',
                    keyboard=await create_keyboard('to_menu')
                )
        else:
            await ans(
                f'Увы. Ты накосячил.😶\n'
                f'Ты ввел несуществующее кол-во тикетов.\n\n'
                f'Доступное кол-во тикетов: {bought}',
                keyboard=await create_keyboard('to_menu')
            )
    else:
        await ans(
            f'Введи, пожалуйста, кол-во тикетов, которые собираешься приобретать(Целое число. Ок?).\n\n'
            f'Доступно тикетов: {bought}',
            keyboard=await create_keyboard('to_menu')
        )


@bot.on.message_handler(text='прошедшие розыгрыши', lower=True)
async def passRaffles(ans: Message):
    passList: list = await pullRaffles('pass')
    if len(passList) == 0:
        await ans(
            'Увы..\nПрошедших розыгрышей еще нет, но зато есть активные розыгрыши💸',
            keyboard=keyboard_gen(
                [
                    [{'text': 'Активные розыгрыши', 'color': 'primary'}],
                    [{'text': 'Меню', 'color': 'negative'}]
                ],
                inline=False,
                one_time=True
            )
        )
    elif len(passList) > 4:
        for raffle in passList[:-1]:
            raffleId, prize, _, _, winnerId = raffle
            winnernickname = await winnerNickname(winnerId)
            if winnernickname[0] == 'не задан':
                name = await bot.api.users.get(user_ids=winnerId)
                winnernickname = str(name[0].first_name) + ' ' + str(name[0].last_name)
            else:
                winnernickname = winnernickname[0]
            await ans(
                f'--Розыгрыш №{raffleId}--\n'
                f'Призовой фонд: {prize} руб\n'
                f'Победитель: [id{winnerId}|{winnernickname}]'
            )
        await ans(
            'Это еще не целый список.\n'
            'Жми далее, чтобы увидеть больше!',
            keyboard=keyboard_gen(
                [
                    [
                        {'text': 'Меню', 'color': 'negative'},
                        {'text': 'Далее', 'color': 'primary', 'payload': "{\"nextpass\":\"4\"}"}]
                ],
                inline=True
            )
        )
    else:
        for raffle in passList:
            raffleId, prize, _, _, winnerId = raffle
            winnernickname = await winnerNickname(winnerId)
            if winnernickname[0] == 'не задан':
                name = await bot.api.users.get(user_ids=winnerId)
                winnernickname = str(name[0].first_name) + ' ' + str(name[0].last_name)
            else:
                winnernickname = winnernickname[0]
            await ans(
                f'--Розыгрыш №{raffleId}--\n'
                f'Призовой фонд: {prize} руб\n'
                f'Победитель: [id{winnerId}|{winnernickname}]'
            )
        await ans(
            'На этом все.\n'
            'Больше нет прошедших розыгрышей.',
            keyboard=await create_keyboard('to_menu')
        )


@bot.on.message_handler(text='admin panel🔒', lower=True)
async def adminPanel(ans: Message):
    await ans(
        'Ведется разработка🛠',
        keyboard=await create_keyboard('to_menu')
    )


bot.run_polling(skip_updates=False)
