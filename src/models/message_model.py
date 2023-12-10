from typing import Union
from pydantic import BaseModel

# message:  texto del mensaje
# typemessage:  canal (whatsapp, webchat, etc)
# valuetype : nro telefono si es whatsapp, id conversacion si es webchat, etc
# solution:  Reclamos, Ventas, Preguntas Frecuentes, etc
# enterprise:  Empresa 


class MessageApi(BaseModel):
    message: str
    typemessage: str
    valuetype: str
    solution: str 
    enterprise: str

