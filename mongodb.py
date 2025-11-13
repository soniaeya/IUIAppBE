from pymongo import MongoClient
from passlib.context import CryptContext

MONGODB_URI = "mongodb://localhost:27017"

client = MongoClient(MONGODB_URI)

db = client["iuiapp_db"]
users_collection = db["users"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
