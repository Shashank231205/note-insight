import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def is_valid_id(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
