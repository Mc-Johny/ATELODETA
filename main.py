import asyncio
import string
import requests
import comments
import config
import random
import messages
import aiosqlite
import transactions
from vkbottle import Bot, Message, User
from vkbottle.api.keyboard import keyboard_gen
from vkbottle.keyboard import Text, Keyboard

bot = Bot(config.token)
user = User(config.acces_token)
qiwi = transactions.Qiwi()


def random_gen():
    string = random.randint(0, 1000000)
    return string


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
        await cursor.execute(f'UPDATE Users SET balance=balance-{amount} WHERE user_id = {user_id}')
        await conn.commit()
        await cursor.close()


async def checkTable(tableName):
    conn = await aiosqlite.connect('Database/database.db')
    cursor = await conn.cursor()
    await cursor.execute(f'SELECT count(*) FROM sqlite_master WHERE type=\'table\' AND name=\'{tableName}\'')
    res = await cursor.fetchone()
    await cursor.close()
    return bool(res[0])


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
        _, nickname, _, qiwi_number, _ = await get_profile(user_id)
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
    await check_or_register_user(ans.from_id)
    await ans(
        'Я тебя не понял.\nВозвращайся лучше в меню.',
        keyboard=await create_keyboard('to_menu')
    )


@bot.on.message_handler(text='помощь', lower=True)
async def help_hendler(ans: Message):
    await ans(
        random.choice(messages.helping),
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
        str_qiwi += '\n\nТак как у вас не задан номер QIWI кошелька,' \
                    ' то в случае вашей победы деньги не будут переведены.\n' \
                    'Если у вас еще нет кошелька, то обязательно заведите на сайте qiwi.com и ' \
                    'Получите статус «Основной»\nПосле этого нажмите на' \
                    ' соответсвующую кнопку ниже.'
    if nickname == 'не задан':
        nickname += ' ✘'
    name = await bot.api.users.get(user_ids=ans.from_id)
    await ans(
        'Имя и фамилия: ' + str(name[0].first_name) + ' ' + str(name[0].last_name) +
        '\nБаланс: ' + str(balance) + ' руб.' +
        '\nНикнейм: ' + nickname +
        '\nКуплено тикетов за все время: ' + str(buy_ticket) +
        '\n Номер кошелька QIWI: +' + str(qiwi_number) +
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
        await menu()
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
        # TODO: Стоит это место исправить.
        await ans(
            'Главное меню.\nВыбери интересующий тебя раздел.',
            keyboard=keyboard_gen(
                [
                    [{'text': 'Активные розыгрыши', 'color': 'primary'}],
                    [{'text': 'Прошедшие розыгрыши', 'color': 'primary'}],
                    [{'text': 'Профиль', 'color': 'secondary'}],
                    [{'text': 'Связаться', 'color': 'secondary'}],
                    [{'text': 'Помощь', 'color': 'negative'}]
                ],
                one_time=True,
                inline=False
            )
        )
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
        shortUrl = requests.get('https://clck.ru/--?url=' + payUrl).text
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

    else:
        await ans(
            'Номер невалидный!\nНомер должен:\n•Содержать только цифры и начинаться на 7(без +)\n•Длина 11 цифр.',
            keyboard=await create_keyboard('edit')
        )

    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu()

    if ans.text.lower() == 'профиль':
        await bot.branch.exit(ans.peer_id)
        await profile(ans)


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
    await editProfile(ans.from_id, ans.text, 'nickname')
    await ans(
        'Ваш никнейм успешно сменен!\nТеперь можешь обратно вернуться в свой профиль.',
        keyboard=await create_keyboard('edit')
    )
    await bot.branch.exit(ans.peer_id)
    if ans.text.lower() == 'меню':
        await bot.branch.exit(ans.peer_id)
        await menu()

    if ans.text.lower() == 'профиль':
        await bot.branch.exit(ans.peer_id)
        await profile(ans)


@bot.on.message_handler(text='связаться', lower=True)
async def contact(ans: Message):
    await ans(
        'Если у тебя что-то случилось, то ты всегда можешь обратиться за помощью к моему разработчику.\n'
        'Вот ссылка на него: https://vk.cc/avIrel\n'
        'Думаю, что ответ быстро придет.\n'
        'Но на некоторые вопросы уже есть ответ в документации, которая доступна по ссылке: https://vk.cc/avIrbJ',
        keyboard=await create_keyboard('to_menu')
    )


bot.run_polling(skip_updates=False)
