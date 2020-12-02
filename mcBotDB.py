#!/usr/bin/python3
import sqlite3
from sqlite3 import Error

def sql_connection():
    try:
        con = sqlite3.connect('minecraftTelegramBot.db')
        return con
    except Error:
        print(Error)

def sql_createUserTable(con):
    cursorObj = con.cursor()
    cursorObj.execute(''' SELECT count(name) FROM sqlite_master WHERE type='table' AND name='unixUsers' ''')
    if cursorObj.fetchone()[0] != 1:
        cursorObj.execute("CREATE TABLE unixUsers(id INTEGER PRIMARY KEY, telegramUser text, unixUser text, expiration text, active integer)")
        con.commit()

def sql_insertUnixUser(con, entities):
    cursorObj = con.cursor()
    cursorObj.execute('INSERT INTO unixUsers(telegramUser, unixUser, expiration, active) VALUES(?, ?, ?, ?)', entities)
    con.commit()

def sql_getActiveUnix(con, tgUser):
    cursorObj = con.cursor()
    cursorObj.execute("SELECT * FROM unixUsers WHERE active = 1 AND telegramUser = ?", (tgUser,))
    if cursorObj.fetchone() is None:
        return False
    else:
        return True

def sql_setUnixUserInactive(con, unixUser):
    cursorObj = con.cursor()
    cursorObj.execute('UPDATE unixUsers SET active = 0 WHERE unixUser = ?', (unixUser,))
    con.commit()

def sql_getAllActive(con):
    activeUsers = []
    cursorObj = con.cursor()
    cursorObj.execute('SELECT * FROM unixUsers where active = 1')
    for row in cursorObj.fetchall():
        activeUsers.append(row)
    return activeUsers

con = sql_connection()
sql_createUserTable(con)

