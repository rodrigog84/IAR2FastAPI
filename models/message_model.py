from typing import Union
from pydantic import BaseModel

class MessageApi(BaseModel):
    message: str
    typemessage: str
    valuetype: str
    enterprise: str
