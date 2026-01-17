"""
Workspaces API routes
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Workspace

router = APIRouter()


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    created_at: datetime
    sources_count: int = 0
    leads_count: int = 0

    class Config:
        from_attributes = True


@router.get("/", response_model=List[WorkspaceResponse])
def list_workspaces(db: Session = Depends(get_db)):
    """List all workspaces"""
    workspaces = db.query(Workspace).order_by(Workspace.created_at.desc()).all()
    
    result = []
    for ws in workspaces:
        result.append(WorkspaceResponse(
            id=ws.id,
            name=ws.name,
            description=ws.description,
            created_at=ws.created_at,
            sources_count=len(ws.sources),
            leads_count=len(ws.leads),
        ))
    
    return result


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(data: WorkspaceCreate, db: Session = Depends(get_db)):
    """Create a new workspace"""
    workspace = Workspace(
        name=data.name,
        description=data.description,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        sources_count=0,
        leads_count=0,
    )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: int, db: Session = Depends(get_db)):
    """Get a specific workspace"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        sources_count=len(workspace.sources),
        leads_count=len(workspace.leads),
    )


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(workspace_id: int, data: WorkspaceCreate, db: Session = Depends(get_db)):
    """Update a workspace"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    workspace.name = data.name
    workspace.description = data.description
    workspace.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(workspace)
    
    return WorkspaceResponse(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        created_at=workspace.created_at,
        sources_count=len(workspace.sources),
        leads_count=len(workspace.leads),
    )


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: int, db: Session = Depends(get_db)):
    """Delete a workspace and all related data"""
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    db.delete(workspace)
    db.commit()
