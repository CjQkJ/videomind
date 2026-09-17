from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RequestCodeBody(BaseModel):
    email: EmailStr
    purpose: Optional[str] = "login"  # login | register | reset_password


class VerifyCodeBody(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)


class RegisterBody(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=4, max_length=12)  # verification code


class PasswordLoginBody(BaseModel):
    email: EmailStr
    password: str


class RequestResetCodeBody(BaseModel):
    email: EmailStr


class ResetPasswordBody(BaseModel):
    email: EmailStr
    code: str = Field(min_length=4, max_length=12)
    new_password: str = Field(min_length=8, max_length=128)


class JobOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_source: Optional[bool] = True
    language: Optional[str] = "zh-CN"


class JobInput(BaseModel):
    type: str
    url: Optional[str] = None
    file_id: Optional[str] = None


class JobOutput(BaseModel):
    mode: Optional[str] = "study_note"
    formats: Optional[List[str]] = None


class CreateJobRequest(BaseModel):
    input: JobInput
    mode: Optional[str] = None  # legacy
    output: Optional[JobOutput] = None
    options: Optional[JobOptions] = None


class RerenderRequest(BaseModel):
    mode: str
    show_source: Optional[bool] = True


class ApiKeyCreate(BaseModel):
    name: str = "default"


class UserOut(BaseModel):
    id: int
    email: str
    tier: str

    class Config:
        from_attributes = True
