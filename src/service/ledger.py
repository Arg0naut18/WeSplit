from typing import Dict, Optional, List
from dataclasses import dataclass
from pymongo import MongoClient
from bson import ObjectId
from configs import MongoConfigs
from typing import List
from datetime import datetime, date
from dateutil.relativedelta import relativedelta


@dataclass
class Transaction:
    paid_by: str
    paid_for: str
    amount: float


class Ledger:
    def __init__(self):
        self.con = MongoClient(MongoConfigs.url)
        self.db = self.con["Ledger"]
        self.collection = self.db["GroupLedger"]
        self.archive = self.db["Archives"]

    def get_group_details(self, group_id: str, archive=False) -> Optional[Dict[str, any]]:
        collection = self.collection if not archive else self.archive
        doc = collection.find_one({"_id": ObjectId(group_id)})
        if doc:
            return {"name": doc["group_name"], "ledger": doc["ledger"], "members": doc["members"], "description": doc["description"], "summary": None if not archive else doc["summary"], "valid_till": None if not archive else (doc["deleted_at"]+relativedelta(years=2)).strftime("%d-%m-%Y %H:%M")}
        else:
            return None

    def insert_to_ledger(self, group_id, by: str | List, amount: str | List, to: List, description: str | List, split_equal=True) -> bool:
        try:
            n = len(to)
            if split_equal:
                by = [by]*n
                split = float(amount)/n
                amount = [split]*n
                description = [description]*n
            data = [
                {
                    "by": by[i],
                    "amount": float(amount[i]),
                    "to": to[i],
                    "description": description[i]
                }
                for i in range(n) if by[i]!=to[i]
            ]
            print("Data: ", data)
            self.collection.update_one({"_id": ObjectId(group_id)},
            {
                '$push': {
                    "ledger": {
                        "$each": data
                    }
                }
            })
        except Exception as e:
            print(e)
            return False
        else:
            return True

    def create_group(self, group_name, group_members: List, description=None) -> str:
        description = description if description else f"A lovely group between {', '.join(group_members)}"
        obj = self.collection.insert_one(
            {"group_name": group_name, "members": group_members, "ledger": [], "description": description, "timestamp": datetime.now()})
        return str(obj.inserted_id)

    def archive_group(self, group_id: str, summary: List[Dict[str, any]]) -> str:
        doc = self.collection.find_one({"_id": ObjectId(group_id)})
        doc["id"] = doc.pop("_id")
        doc["deleted_at"] = datetime.now()
        doc["summary"] = summary
        archive = self.archive.insert_one(document=doc)
        self.collection.delete_one({"_id": ObjectId(group_id)})
        return str(archive.inserted_id)
