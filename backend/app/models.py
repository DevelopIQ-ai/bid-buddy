from pydantic import BaseModel
from typing import Optional


class Project(BaseModel):
    id: Optional[str] = None
    user_id: Optional[str] = None
    name: str
    enabled: bool = False
    drive_folder_id: Optional[str] = None
    drive_folder_name: Optional[str] = None
    is_drive_folder: bool = False


class ProjectToggle(BaseModel):
    enabled: bool
