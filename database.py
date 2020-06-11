import aiosqlite


class Sqlite:
    def __init__(self, bdFile):
        self.connection = await aiosqlite.connect(bdFile)
        self.cursor = await self.connection.cursor()
