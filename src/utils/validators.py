from typing import List, Dict, Union, TypedDict
from decimal import Decimal, InvalidOperation
from bson import ObjectId, errors as bson_errors


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class TransactionValidation(TypedDict):
    valid: bool
    errors: Dict[str, bool]


def validate_group_id(group_id: str) -> bool:
    """Validate if a string is a valid MongoDB ObjectId"""
    try:
        ObjectId(group_id)
        return True
    except (bson_errors.InvalidId, TypeError):
        return False


def validate_money_amount(amount: Union[str, float]) -> bool:
    """Validate if a string or float is a valid money amount"""
    try:
        amount_decimal = Decimal(str(amount))
        return amount_decimal > 0
    except (InvalidOperation, ValueError, TypeError):
        return False


def validate_group_members(members: List[str]) -> bool:
    """Validate group members list"""
    if not members or not isinstance(members, list):
        return False
    return all(isinstance(m, str) and m.strip() for m in members)


def validate_transaction(paid_by: str, amount: Union[str, float], split_by: List[str], description: str) -> TransactionValidation:
    """Validate transaction details"""
    return {
        "valid": all([
            isinstance(paid_by, str) and paid_by.strip(),
            validate_money_amount(amount),
            validate_group_members(split_by),
            isinstance(description, str)
        ]),
        "errors": {
            "paid_by": not (isinstance(paid_by, str) and paid_by.strip()),
            "amount": not validate_money_amount(amount),
            "split_by": not validate_group_members(split_by),
            "description": not isinstance(description, str)
        }
    }
