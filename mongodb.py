from pymongo import MongoClient
from passlib.context import CryptContext

MONGODB_URI = "mongodb://localhost:27017"

client = MongoClient(MONGODB_URI)
db = client["iuiapp_db"]

users_collection = db["users"]
ratings_collection = db["ratings"]
preferences_collection = db["preferences"]

# 🔧 Make this idempotent – let Mongo reuse the existing index
ratings_collection.create_index(
    [("user_id", 1), ("place_id", 1)],
    unique=True,  # keep unique constraint
    # no "name" here – Mongo will detect existing index and reuse it
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
