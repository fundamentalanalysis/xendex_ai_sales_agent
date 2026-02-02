"""Schemas for email operations."""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class ReceivedEmail(BaseModel):
    """Schema for a received email summary."""
    id: str
    to: List[str]
    from_: str = Field(alias="from")  # 'from' is reserved
    created_at: str
    subject: str
    bcc: List[str]
    cc: List[str]
    reply_to: List[str]
    message_id: str
    attachments: List[Any]

    class Config:
        from_attributes = True
        allow_population_by_field_name = True


class ReceivedEmailList(BaseModel):
    """Schema for list of received emails."""
    object: str
    has_more: bool
    data: List[ReceivedEmail]


class ReceivedEmailDetail(BaseModel):
    """Schema for detailed received email."""
    id: str
    to: List[str]
    from_: str = Field(alias="from")
    created_at: str
    subject: str
    bcc: List[str]
    cc: List[str]
    reply_to: List[str]
    message_id: str
    attachments: List[Any]
    text_body: Optional[str] = Field(None, alias="text")
    html_body: Optional[str] = Field(None, alias="html")
    headers: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
        allow_population_by_field_name = True