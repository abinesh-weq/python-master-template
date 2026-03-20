from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PredefinedMasterCreateRequest(BaseModel):
    entity_type: str
    code: str
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = 0
    is_active: bool = True


class PredefinedMasterUpdateRequest(BaseModel):
    entity_type: Optional[str] = None
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class PredefinedMasterResponse(BaseModel):
    id: str
    entity_type: str
    code: str
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)
