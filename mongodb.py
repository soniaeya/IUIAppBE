from pymongo import MongoClient
from passlib.context import CryptContext

MONGODB_URI = "mongodb://localhost:27017"
#connection_str="mongodb+srv://<db_username>:<db_password>@cluster0.5fl3opg.mongodb.net/"

client = MongoClient(MONGODB_URI)
#client=MongoClient(connection_str)

db = client["iuiapp_db"]
users_collection = db["users"]


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
