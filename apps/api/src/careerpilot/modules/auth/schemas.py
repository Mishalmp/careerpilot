import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class LoginRequest(BaseModel):
    email: EmailStr
    # Upper bound stops a huge body from turning password hashing into a CPU attack.
    password: SecretStr = Field(min_length=1, max_length=1024)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str
