import os

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv())

APP_SECRET = os.getenv("APP_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_ID = os.getenv("PHONE_ID")
