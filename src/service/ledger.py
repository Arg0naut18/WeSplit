from typing import Dict, Optional, List, Union, Any
from dataclasses import dataclass
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from bson import ObjectId
from configs import MongoConfigs
from datetime import datetime
from dateutil.relativedelta import relativedelta
from src.utils.logger import logger
from src.utils.validators import validate_group_id, validate_money_amount, validate_group_members


@dataclass
class Transaction:
    paid_by: str
    paid_for: str
    amount: float


class DatabaseError(Exception):
    """Custom exception for database operations"""
    pass


class Ledger:
    def __init__(self):
        try:
            self._client = MongoClient(
                MongoConfigs.url,
                maxPoolSize=50,
                waitQueueTimeoutMS=2500,
                connectTimeoutMS=2000,
                retryWrites=True
            )
            # Test the connection
            self._client.admin.command('ping')
            logger.info("Successfully connected to MongoDB")
            
            self.db = self._client["Ledger"]
            self.collection = self.db["GroupLedger"]
            self.archive = self.db["Archives"]
            
            # Create indexes for better query performance
            self.collection.create_index("group_name")
            self.archive.create_index("group_name")
            self.archive.create_index("deleted_at", expireAfterSeconds=63072000)
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise DatabaseError("Could not connect to database") from e

    def get_group_details(self, group_id: str, archive: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get group details from either active or archived collections.
        
        Args:
            group_id: The MongoDB ObjectId as string
            archive: Whether to look in archived collections
            
        Returns:
            Dict containing group details or None if not found
            
        Raises:
            DatabaseError: If database operation fails
            ValueError: If group_id is invalid
        """
        if not validate_group_id(group_id):
            raise ValueError("Invalid group ID format")

        try:
            collection = self.collection if not archive else self.archive
            doc = collection.find_one({"_id": ObjectId(group_id)})
            
            if not doc:
                return None
                
            return {
                "name": doc.get("group_name"),
                "ledger": doc.get("ledger", []),
                "members": doc.get("members", []),
                "description": doc.get("description", ""),
                "summary": None if not archive else doc.get("summary"),
                "valid_till": None if not archive else (doc.get("deleted_at", datetime.now()) + relativedelta(years=2)).strftime("%d-%m-%Y %H:%M"),
                "is_simplified": doc.get("is_simplified", False)
            }
            
        except ConnectionFailure as e:
            logger.error(f"Database connection error while fetching group {group_id}: {str(e)}")
            raise DatabaseError("Failed to connect to database") from e
        except Exception as e:
            logger.error(f"Error fetching group {group_id}: {str(e)}")
            raise DatabaseError("Failed to fetch group details") from e

    def insert_to_ledger(
        self, 
        group_id: str, 
        by: Union[str, List[str]], 
        amount: Union[str, List[str]], 
        to: List[str], 
        description: Union[str, List[str]], 
        split_equal: bool = True
    ) -> bool:
        """
        Insert transactions into the ledger with validation and error handling.
        
        Args:
            group_id: The group's MongoDB ObjectId as string
            by: Who paid (single payer or list of payers)
            amount: Amount(s) paid
            to: List of recipients
            description: Transaction description(s)
            split_equal: Whether to split amount equally
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            ValueError: If input validation fails
            DatabaseError: If database operation fails
        """
        try:
            # Validate inputs
            if not validate_group_id(group_id):
                raise ValueError("Invalid group ID format")
                
            n = len(to)
            if n == 0:
                raise ValueError("No recipients specified")
                
            if split_equal:
                if not isinstance(by, str) or not by.strip():
                    raise ValueError("Invalid payer for equal split")
                if not isinstance(amount, (str, float)) or not validate_money_amount(amount):
                    raise ValueError("Invalid amount format")
                split = round(float(amount) / n, 2)
                by_list = [by] * n
                amount_list = [split] * n
                desc_list = [description] * n
                
            else:
                if not isinstance(by, list) or not isinstance(amount, list):
                    raise ValueError("For unequal split, 'by' and 'amount' must be lists")
                    
                if not all(validate_money_amount(amt) for amt in amount):
                    raise ValueError("Invalid amount in unequal split")
                    
                by_list = by
                amount_list = [float(amt) for amt in amount]
                desc_list = description if isinstance(description, list) else [description] * n
                
            # Create transaction records
            data = [
                {
                    "by": by_list[i],
                    "amount": amount_list[i],
                    "to": to[i],
                    "description": desc_list[i],
                    "timestamp": datetime.now()
                }
                for i in range(n) if by_list[i] != to[i]  # Skip self-payments
            ]
            
            if not data:
                logger.warning("No valid transactions to insert")
                return False
                
            # Update database
            result = self.collection.update_one(
                {"_id": ObjectId(group_id)},
                {'$push': {"ledger": {'$each': data}}}
            )
            
            if result.modified_count == 0:
                logger.warning(f"No ledger updated for group {group_id}")
                return False
                
            logger.info(f"Successfully inserted {len(data)} transactions into group {group_id}")
            return True
            
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            raise
        except ConnectionFailure as e:
            logger.error(f"Database connection error: {str(e)}")
            raise DatabaseError("Failed to connect to database") from e
        except Exception as e:
            logger.error(f"Error inserting to ledger: {str(e)}")
            raise DatabaseError("Failed to insert transactions") from e

    def create_group(self, group_name: str, group_members: List[str], description: Optional[str] = None) -> str:
        """
        Create a new group with validation.
        
        Args:
            group_name: Name of the group
            group_members: List of member names
            description: Optional group description
            
        Returns:
            str: ID of the created group
            
        Raises:
            ValueError: If validation fails
            DatabaseError: If database operation fails
        """
        try:
            # Validate inputs
            if not group_name or not isinstance(group_name, str):
                raise ValueError("Invalid group name")
                
            if not validate_group_members(group_members):
                raise ValueError("Invalid group members list")
                
            # Clean and prepare data
            clean_group_name = group_name.strip()
            clean_members = [m.strip() for m in group_members if m.strip()]
            
            if not clean_members:
                raise ValueError("No valid group members provided")
                
            description = (description if description 
                         else f"A lovely group between {', '.join(clean_members)}")
            
            # Create group document
            group_doc = {
                "group_name": clean_group_name,
                "members": clean_members,
                "ledger": [],
                "description": description.strip(),
                "timestamp": datetime.now(),
                "last_modified": datetime.now()
            }
            
            # Insert with retry logic
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    result = self.collection.insert_one(group_doc)
                    logger.info(f"Successfully created group {clean_group_name}")
                    return str(result.inserted_id)
                except ConnectionFailure as e:
                    last_error = e
                    if attempt == max_retries - 1:
                        break
                    logger.warning(f"Retry {attempt + 1} after connection failure")
            
            # If we get here, all retries failed
            logger.error(f"Database connection error while creating group: {str(last_error)}")
            raise DatabaseError("Failed to connect to database") from last_error
                    
        except Exception as e:
            logger.error(f"Error creating group: {str(e)}")
            raise DatabaseError("Failed to create group") from e

    def archive_group(self, group_id: str, summary: List[Dict[str, Any]]) -> str:
        """
        Archive a group and its transactions.
        
        Args:
            group_id: The group's MongoDB ObjectId as string
            summary: List of transaction summaries
            
        Returns:
            str: ID of the archived group
            
        Raises:
            ValueError: If group_id is invalid
            DatabaseError: If database operation fails
        """
        try:
            if not validate_group_id(group_id):
                raise ValueError("Invalid group ID format")

            # Start a session for atomic operations
            with self._client.start_session() as session:
                with session.start_transaction():
                    # Find and verify the group exists
                    doc = self.collection.find_one(
                        {"_id": ObjectId(group_id)},
                        session=session
                    )
                    
                    if not doc:
                        logger.warning(f"Group {group_id} not found")
                        return ""
                    
                    # Prepare archive document
                    archive_doc = doc.copy()
                    archive_doc["original_id"] = archive_doc.pop("_id")
                    archive_doc["deleted_at"] = datetime.now()
                    archive_doc["summary"] = summary
                    
                    # Insert into archives and delete from active collection
                    archive_result = self.archive.insert_one(
                        document=archive_doc,
                        session=session
                    )
                    
                    delete_result = self.collection.delete_one(
                        {"_id": ObjectId(group_id)},
                        session=session
                    )
                    
                    if not archive_result.inserted_id or delete_result.deleted_count == 0:
                        raise DatabaseError("Failed to archive group")
                    
                    logger.info(f"Successfully archived group {group_id}")
                    return str(archive_result.inserted_id)
                    
        except ConnectionFailure as e:
            logger.error(f"Database connection error while archiving group {group_id}: {str(e)}")
            raise DatabaseError("Failed to connect to database") from e
        except Exception as e:
            logger.error(f"Error archiving group {group_id}: {str(e)}")
            raise DatabaseError("Failed to archive group") from e

    def simplify_archive_group(self, group_id, summary) -> str:
        new_summary = { "$set": { 'summary': summary, 'is_simplified': True }}
        updated_record = self.archive.update_one({"_id": ObjectId(group_id)}, new_summary)
        return updated_record.upserted_id
