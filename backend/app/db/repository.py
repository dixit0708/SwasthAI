from typing import Generic, TypeVar, Dict, Any, Optional, List
from bson import ObjectId
from app.db.mongodb import db_manager

T = TypeVar("T")

class BaseRepository(Generic[T]):
    def __init__(self, collection_name: str):
        self.collection_name = collection_name

    @property
    def collection(self):
        return db_manager.db[self.collection_name]

    async def get_by_id(self, id: str) -> Optional[Dict[str, Any]]:
        if not ObjectId.is_valid(id):
            return None
        return await self.collection.find_one({"_id": ObjectId(id)})

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        cursor = self.collection.find().skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def create(self, data: Dict[str, Any]) -> str:
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def update(self, id: str, data: Dict[str, Any]) -> bool:
        if not ObjectId.is_valid(id):
            return False
        result = await self.collection.update_one(
            {"_id": ObjectId(id)}, {"$set": data}
        )
        return result.modified_count > 0

    async def delete(self, id: str) -> bool:
        if not ObjectId.is_valid(id):
            return False
        result = await self.collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0
