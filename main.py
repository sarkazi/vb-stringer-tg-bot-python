import logging
import re
import asyncio
import threading
import time
import telegram
import pymongo
import dns.resolver
import os

from os import getenv
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from pymongo import MongoClient

load_dotenv()


dns.resolver.default_resolver=dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers=['8.8.8.8']


# Define MongoDB connection detailss
mongo_host = getenv('MONGO_HOST')
mongo_user = getenv('MONGO_USER')
mongo_password = getenv('MONGO_PASSWORD')
mongo_database_name = getenv('MONGO_DATABASE_NAME')
mongo_collection_name = getenv('MONGO_COLLECTION_NAME')


# Initialize MongoDB
#mongo_client = MongoClient(f'mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}')
mongo_client = MongoClient(f'mongodb+srv://{mongo_user}:{mongo_password}@{mongo_host}/{mongo_database_name}')
db = mongo_client[mongo_database_name]
collection = db[mongo_collection_name]

mongo_client.admin.command('ping')


tg_bot_token = getenv('TELEGRAM_BOT_TOKEN')


#second collection with chat_ids !!!

# Initialize Telegram Bot
bot = Bot(token=tg_bot_token)

# Initialize Telegram Bot
updater = Updater(token=tg_bot_token, use_context=True)
#updater = Updater(bot=bot, use_context=True)
dispatcher = updater.dispatcher

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define command handlers (optional)
def start(update, context):
    update.message.reply_text('Hello! I am your ViralBear chatbot. Send me videos!')

def help_command(update, context):
    update.message.reply_text('You can send me any video, and I will save it to the database.')
    

def save_message(update, context):
    user_id = update.effective_user.id
    message_text = update.message.text

    # Check if the message contains a link
    links = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', message_text)

    if links:
        # Get the user's nickname from MongoDB !!! collection need to be changed !!!
        user_data = collection.find_one({'user_id': user_id})
        if user_data is None:
            update.message.reply_text("Sorry, your Telegram nickname wasn't found in our system.")
            return
        else:
                
            link = links[0]

            # Save link to MongoDB
            collection.insert_one({'user_id': user_id, 'link': link, 'sentCommentToStringer': False, 'comments': []})

            # Send success message
            update.message.reply_text("Success! The video was sent!")

            return
                

    # If link checking failed or something went wrong
    update.message.reply_text("Sorry, something went wrong!")




def send_direct_message(user_id, link, comments):
    try:
        message = f"This video was rejected: {link}\n\n"
        
        for i, comment in enumerate(comments, start=1):
            message += f"{i}. {comment}\n"

        bot.send_message(chat_id=user_id, text=message)

    except telegram.error.BadRequest as e:
        logger.exception(f"Error occurred: {e}")
        logger.warning(f"Failed to send message to user with id {user_id}. Chat not found.")





def scheduler():
    while True:
        try:
            # Query for documents with sentCommentToStringer=False and existing comments
            for user_data in collection.find({'sentCommentToStringer': False, 'comments': {'$exists': True, '$ne': []}}):
                user_id = user_data.get('user_id')
                link = user_data.get('link')
                comments = user_data.get('comments', [])

                send_direct_message(user_id, link, comments)

                # Update sentCommentToStringer to True
                collection.update_one({'user_id': user_id}, {'$set': {'sentCommentToStringer': True}})

            # Sleep for 12 hours
            time.sleep(12 * 60 * 60)
        except Exception as e:
            logger.exception(f"Error occurred: {e}")
            continue





# Create an error handler (optional)
def error(update: Update, context: CallbackContext) -> None:
    logger.warning(f'Update "{update}" caused error "{context.error}"')

# Start the bot
def main():
    updater.dispatcher.add_handler(CommandHandler("start", start))
    updater.dispatcher.add_handler(CommandHandler("help", help_command))
    updater.dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, save_message))

    updater.dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=scheduler)
    scheduler_thread.start()
    
    while True:
        try:
            main()
        except Exception as e:
            logger.exception(f"Error occurred: {e}")
            continue
