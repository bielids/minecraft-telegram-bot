#!/usr/bin/python3

import telegram
import logging
import yaml
import io
import os
import time
import requests
import subprocess
import sched
import SecureString
import sys
import re
from mcstatus import MinecraftServer
from threading import Thread
from watchdog.events import RegexMatchingEventHandler
from watchdog.observers import Observer
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# Setting variables
TOKEN = 'TOKEN_GOES_HERE'
bot = telegram.Bot(token=TOKEN) #should not be here
s = sched.scheduler(time.time, time.sleep)
valuesLoaded = False
configFile = "config.yml"
DATE=datetime.today().strftime('%Y-%m-%d')
users = {}
cmdPerms = {}
path = os.path.dirname(os.path.realpath(__file__))
logDir = "logs"
logName = "debug.log"
debug = True

# styling codes
class colour:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

##################################################################################
#                                     Logging                                    #
##################################################################################

# set logging options
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(path + '/' + logDir + '/' + logName),
        logging.StreamHandler(),
        logging.handlers.TimedRotatingFileHandler(logName, when="midnight", interval=1)
    ]
)

# check if log directory exists
if not os.path.exists('logs'):
	logging.info('Creating log directory.')
	os.makedirs(path + '/' + 'logs', mode=0o755)

##################################################################################
#                             Config Management                                  #
##################################################################################

### Load config file
def loadConfig():
        global config
        global valuesLoaded
        if valuesLoaded:
                logging.info('Backing up current config...')
                with open(r'config.yml.bak', 'w') as file:
                                paramsBackup = yaml.dump(config, file)
        try:
                with open(path + '/' + configFile) as conf:
                        config = yaml.load(conf, Loader=yaml.Loader)
                        if os.path.exists(path + '/' + configFile + '.bak'):
                                os.remove(path + '/' + configFile + '.bak')
        except FileNotFoundError:
                logging.error("ERROR: Config file " + path + '/' + configFile + " not found")
                exit(1)
        except yaml.parser.ParserError:
                badConfigBackup()
        except yaml.scanner.ScannerError:
                badConfigBackup()
        loadConfigValues()

### Load variables from YAML config file
def loadConfigValues():
        global config
        global valuesLoaded
        try:
                users['op'] = config['groups']['op']
                users['mod'] = config['groups']['mod']
                users['user'] = config['groups']['user']
                cmdPerms['op'] = config['permissions']['op'] + config['permissions']['mod'] + config['permissions']['user']
                cmdPerms['mod'] = config['permissions']['mod'] + config['permissions']['user']
                cmdPerms['user'] = config['permissions']['user']
                cmdPerms['disabled'] = config['permissions']['disabled']
                caseSensitive = config['settings']['fileWatch']['caseSensitive']
                ignoreDirectories = config['settings']['fileWatch']['ignoreDirectories']
                valuesLoaded = True
                # make all variables global
                globals().update(locals())
        except KeyError:
                badConfigBackup()

#function to handle bad configs loaded online
def badConfigBackup():
        if not valuesLoaded:
                logging.critical(colour.BOLD + colour.RED + "ERROR: Incorrect or missing values in config!" + colour.END)
                exit(1)
        else:
                try:
                        os.remove(path + '/' + configFile + '.badValues')
                except FileNotFoundError:
                        pass
                os.rename(path + '/' + configFile, path + '/' + configFile + '.badValues' )
                os.rename(path + '/' + configFile + '.bak', path + '/' + configFile)
                logging.error(colour.BOLD + colour.RED + 'ERROR: Incorrect or missing values in config!' + colour.END)
                logging.error('Please check ' + colour.BOLD + configFile + '.badValues' + colour.END + ' for error')
                logging.warning('Reloading backed up config....')
                loadConfig()
                try:
                        os.remove(path + '/' + configFile + '.bak')
                except FileNotFoundError:
                        pass
                pass

##################################################################################
#                                   File-watch                                   #
##################################################################################

# Define file watcher settings for YAML
class watchFile:
        def on_created(event):
                pass
        def on_deleted(event):
                pass
        def on_modified(event):
                if debug:
                        logging.info(f"{event.src_path} has been modified, reloading")
                loadConfig()
                loadConfigValues()
                if debug:
                        logging.info(colour.GREEN + "Reload complete." + colour.END)
                pass
        def on_moved(event):
                pass

# event handler settings
regexMatch = [".+yml"]
ignore_patterns = [".+bak|.+badValues|.+swp"]
fileEventHandler = RegexMatchingEventHandler(regexMatch, ignore_patterns, ignoreDirectories, caseSensitive)
fileEventHandler.on_modified = watchFile.on_modified
goRecursively = False
my_observer = Observer()
my_observer.schedule(fileEventHandler, path, recursive=goRecursively)


##################################################################################
#               Supporting functions used by command handlers                    #
##################################################################################

# function to check if user is authorized to run cmd
def checkPerm(update, function):
    username = update.message.from_user.username
    logging.info('Checking if ' + username + ' can execute ' + function)
    if function in cmdPerms['disabled']:
        logging.info(function + ' has been disabled')
        update.message.reply_text(function + ' is currently disabled.')
        return False
    for group in users:
        if username in users[group]:
            permLevel = group
    if function in cmdPerms[permLevel]:
        logging.info('User ' + username + ' has correct privileges to execute ' + function + '. Continuing...')
        return True
    else:
        logging.info('Could not find user....')
        return False

# function to log cmd usage
def functionLogging(update, message):
    try:
        logging.info(update.message.from_user.username + ' ' + message)
        return True
    except TypeError:
        sendCreateUser(update)
        return False

# stores active Minecraft servers to mcServers
def activeServers():
    global mcServers
    mcServers = []
    bashCommand = "systemctl"
    result = subprocess.run(bashCommand, stdout=subprocess.PIPE)
    grepVal = 'minecraft'
    for process in result.stdout.decode("utf-8").split('\n'):
        if 'minecraft@' in process:
            mcServers.append(process.split('.')[0].split('@')[1])

def mcServerSelection(update):
    global mcServer
    global mcServers
    global mcServerSelected
    try:
        if update.message.text.split(' ')[1] in mcServers:
            mcServer = update.message.text.split(' ')[1]
    except:
        try:
            mcServer = mcServerSelected
        except:
            print('well poop')

def mcServerQuery(update):
    global mcPort
    global mcQueryResult
    global mcServerSelected
    global mcServer
    try:
        with open('/home/minecraft/' + mcServer + '/server.properties') as conf:
            for line in conf.readlines():
                if 'server-port' in line:
                    mcPort = int(line.split('=')[1])
    except:
        update.message.reply_text('Something went wrong. Did you give me a valid name (case-sensitive)?')
        return False
    server = MinecraftServer("127.0.0.1", mcPort)
    mcQueryResult = server.query()
    return True

# decide on what username/password to create
def sshUserGen():
    global genUnixUsername
    global genUnixPassword
    genUnixUsername = 'testlogin' # I will need to write the code to have this be randomly generated instead (user & pass)
    genUnixPassword = 'testpassword' # something like user:password = af4yt2k353:fc230g1cvg (10 char alpha-numerical)

# create the UNIX user used for SSH login
def createUnixUser(unixUsername, unixPassword):
    bashCommand = "sudo -u minecraft_bot useradd " + unixUsername
    result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)

def schedDelUnixUser(ttl):
    s.enter(ttl, 1, delUnixUser)
    s.run()

def sendMinecraftCommand(update, mcCmd, botArgs):
    botArgs = botArgs.split()
    mcServer = botArgs[1]
    mcArgs = ' '.join(botArgs[2:])
    bashCommand = "/home/minecraft/scripts/ManageMinecraftBot/sendMinecraftCMD.sh " + mcCmd + " " + mcServer + " " + mcArgs
    logging.info(bashCommand)
    result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)
    update.message.reply_text(result.stdout.decode("utf-8"))

def sendCreateUser(update):
    update.message.reply_text('Please create a Telegram username before continuing')
    logging.warning('Unknown user requested a command')

def delUnixUser(unixUsername):
    bashCommand = "sudo -u minecraft_bot userdel " + sshUsernameGen
    result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)

##################################################################################
#                         Graphical interface building                           #
##################################################################################

def serverKb(update, context):
    global mcServers
    activeServers()
    button_list = []
    for server in mcServers:
        button_list.append(InlineKeyboardButton(server, callback_data = server))
    reply_markup=InlineKeyboardMarkup(build_menu(button_list,n_cols=1))

    update.message.reply_text('Please choose server:', reply_markup=reply_markup)

def build_menu(buttons,n_cols,header_buttons=None,footer_buttons=None):
  menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
  if header_buttons:
    menu.insert(0, header_buttons)
  if footer_buttons:
    menu.append(footer_buttons)
  return menu

def button(update: Update, context: CallbackContext) -> None:
    global mcServerSelected
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()

    mcServerSelected = query.data
    print(mcServerSelected)

    query.edit_message_text(text=f"Selected option: {query.data}")

##################################################################################
# Define a few command handlers. These usually take the two arguments update and #
# context. Error handlers also receive the raised TelegramError object in error. #
##################################################################################

def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    update.message.reply_text('Hi!')

def restart_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested to restart the server'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        bashCommand = "sudo systemctl restart minecraft@JarlsWorld"
        result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)
        update.message.reply_text('Minecraft server rebooted')

def backup_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested to backup the server'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        try:
            os.remove('/home/minecraft/tmp/JarlsServer_' + DATE + '.tar.gz')
        except FileNotFoundError:
            logging.info('no file to remove, continuining')
        archiveName = "/home/minecraft/tmp/JarlsServer_" + DATE + ".tag.gz"
        bashCommand = "tar -czf " + archiveName + " /home/minecraft/JarlsServer"
        result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)
        bashCommand = "/home/minecraft/scripts/plik -t 2d " + archiveName
        result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)
        plikout = result.stdout.decode("utf-8").split('\n')
        update.message.reply_text(plikout[1])
        logging.info('Upload completed and sent to user.') # need to verify stdout of plik and tar

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('You are on your own buddy.')

def perm_command(update: Update, context: CallbackContext) -> None:
    try:
        logging.info(update.message.from_user.username + ' requested permission info')
    except TypeError:
        sendCreateUser(update)
        return
    missingUser = False
    for group in users:
        if update.message.from_user.username in users[group]:
            logging.warning('User ' + update.message.from_user.username + ' was found in group ' + group)
            update.message.reply_text('Here are your permissions:\n\nUsername: ' + update.message.from_user.username + '\nGroup: ' + group)
            update.message.reply_text('Allowed commands:\n\n' + '\n'.join(str(cmd) for cmd in cmdPerms[group]))
            missingUser = False
            break
        else:
            missingUser = True
    if missingUser:
        logging.warning('User ' + update.message.from_user.username + ' not found in permission list')
        update.message.reply_text('User not found in userlist. Fucking pleb....')

def genSSH_command(update: Update, context: CallbackContext) -> None:
    global genUnixUsername
    global genUnixPassword
    sshUserGen()
    createUnixUser(genUnixUsername, genUnixPassword)
    update.message.reply_text('New SSH login successfully created!\n\nServer: mc.atetreault.xyz\nPort: 10069')
    update.message.reply_text('Username: ' + genUnixUsername + '\nPassword: ' + genUnixPassword)
    update.message.reply_text('This user will be deactivated in 2 hours!')
    SecureString.clearmem(genUnixUsername)
    SecureString.clearmem(genUnixPassword)
    schedDelUnixUser(7200)

def op_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested to grant OP privs to ' + '\n'.join(str(user) for user in update.message.text.split(' ')[2:])
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        sendMinecraftCommand(update, 'op', update.message.text)

def deop_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested to revoke OP privs for ' + '\n'.join(str(user) for user in update.message.text.split(' ')[2:])
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        sendMinecraftCommand(update, 'deop', update.message.text)

def test_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested server performance information'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        pass

def hwinfo_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested server performance information'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        pass

def propUpdate_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested to update a setting in server.properties'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        bashCommand = "sed -i 's/" + propSetting + "=.*/" + propSetting + "=" + propVal + "/g' /home/minecraft/" + mcWorld + "/server.properties"
        result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)
        update.message.reply_text('Setting updated for ' + mcWorld + ". Please restart server to apply changes")

def propGet_command(update: Update, context: CallbackContext) -> None: # grep for single prop, but read whole file and send via TG if no prop specified
    propList = {}
    loggingMessage = 'requestet to get a prop in server.properties'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        with open('/home/minecraft/JarlsServer/server.properties') as conf:
            for prop in conf.readlines():
                if not prop.startswith('#'):
                    for propVals in prop.rstrip("\n").split('='):
                        propList[propVals[0]] = propVals[1]
                        print(propList)
        print(propList[0])
        print('hello world')
        print(propList[14])
        update.message.reply_text('\n'.join(propList))

#        bashCommand = "grep " + propSetting + " /home/minecraft/" + mcWorld + "/server.properties"
 #       result = subprocess.run(bashCommand.split(), stdout=subprocess.PIPE)
  #      update.message.reply_text('Setting updated for ' + mcWorld + ". Please restart server to apply changes")


def clone_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested to clone worlds'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        pass

def list_command(update: Update, context: CallbackContext) -> None:
    pass

def broadcast_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested to broadcast to the server'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        sendMinecraftCommand(update, 'broadcast', update.message.text)

def players_command(update: Update, context: CallbackContext) -> None:
    loggingMessage = 'requested Minecraft player info'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        global mcQueryResult
        if mcServerQuery(update):
            update.message.reply_text("The server has the following players online:\n\n{0}".format("\n".join(mcQueryResult.players.names)))

def status_command(update: Update, context: CallbackContext) -> None:
    global mcQueryResult
    global mcServer
    serverKb(update, context)
    loggingMessage = 'requested Minecraft server info'
    if functionLogging(update, loggingMessage) and checkPerm(update, sys._getframe().f_code.co_name.split('_')[0]):
        if mcServerQuery(update):
            mcPlayersOnline = str(mcQueryResult.players.online)
            mcPlayersMax = str(mcQueryResult.players.max)
            mcVersion = mcQueryResult.software.version
            mcBrand = mcQueryResult.software.brand
            mcMotd = mcQueryResult.motd
            mcPlugins = '\n    '.join(mcQueryResult.software.plugins)
            update.message.reply_text("Server info:\n\nServer name: " + mcServer + "\nMOTD: " + mcMotd + "\nVersion: " + mcVersion + "\nBrand: " + mcBrand + "\nPlayers online: " + mcPlayersOnline + "/" + mcPlayersMax + "\n\nPlugins:\n\n    " + mcPlugins)
            mcServerSelected = ''
            mcServer = ''

def echo(update: Update, context: CallbackContext) -> None:
    """Echo the user message."""
    update.message.reply_text(update.message.text)

def badCMD(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Invalid command')

def main():
    # load config and values
    loadConfig()

    # Start the file watch service
    my_observer.start()

    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("restart", restart_command))
    dispatcher.add_handler(CommandHandler("backup", backup_command))
    dispatcher.add_handler(CommandHandler("perm", perm_command))
    dispatcher.add_handler(CommandHandler("genssh", genSSH_command))
    dispatcher.add_handler(CommandHandler("list", list_command))
    dispatcher.add_handler(CommandHandler("clone", clone_command))
    dispatcher.add_handler(CommandHandler("op", op_command))
    dispatcher.add_handler(CommandHandler("deop", deop_command))
    dispatcher.add_handler(CommandHandler("hwinfo", hwinfo_command))
    dispatcher.add_handler(CommandHandler("broadcast", broadcast_command))
    dispatcher.add_handler(CommandHandler("test", test_command))
    dispatcher.add_handler(CommandHandler("players", players_command))
    dispatcher.add_handler(CommandHandler("propGet", propGet_command))
#    dispatcher.add_handler(CommandHandler("kb", kb))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))


    # on noncommand i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, badCMD))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()

