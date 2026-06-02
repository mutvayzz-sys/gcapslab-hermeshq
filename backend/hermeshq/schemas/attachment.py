from pydantic import BaseModel


class AttachmentUploadRead(BaseModel):
    file_id: str
    filename: str
    media_type: str
    size: int
    path: str


class AttachmentDeleteRead(BaseModel):
    status: str
    file_id: str
