import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.models.message import MessageHistoryRead
from app.models.workflow import (
    WorkflowCreate,
    WorkflowExecuteRequest,
    WorkflowExecuteResponse,
    WorkflowRead,
    WorkflowUpdate,
)
from app.services.workflow_service import (
    create_workflow,
    execute_workflow_run,
    get_history,
    get_workflow,
    list_workflows,
    update_workflow,
)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


@router.post("/", response_model=WorkflowRead, status_code=201)
async def create_workflow_endpoint(workflow: WorkflowCreate, db: AsyncSession = Depends(get_session)):
    return await create_workflow(db, workflow)


@router.get("/", response_model=list[WorkflowRead])
async def list_workflows_endpoint(db: AsyncSession = Depends(get_session)):
    return await list_workflows(db)


@router.get("/history", response_model=list[MessageHistoryRead])
async def history_endpoint(workflow_run_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_session)):
    return await get_history(db, workflow_run_id)


@router.get("/{workflow_id}", response_model=WorkflowRead)
async def get_workflow_endpoint(workflow_id: uuid.UUID, db: AsyncSession = Depends(get_session)):
    workflow = await get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowRead)
async def update_workflow_endpoint(
    workflow_id: uuid.UUID,
    workflow: WorkflowUpdate,
    db: AsyncSession = Depends(get_session),
):
    updated = await update_workflow(db, workflow_id, workflow)
    if updated is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return updated


@router.post("/{workflow_id}/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow_endpoint(
    workflow_id: uuid.UUID,
    request: WorkflowExecuteRequest,
    db: AsyncSession = Depends(get_session),
):
    try:
        workflow = await get_workflow(db, workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")
        result = await execute_workflow_run(request.user_message, channel="api", user_id="api", db=db, workflow_id=workflow_id)
        return WorkflowExecuteResponse(
            response=result.response,
            workflow_run_id=result.workflow_run_id,
            token_count=result.token_count,
            cost_usd=result.cost_usd,
        )
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error executing workflow {workflow_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error executing workflow: {str(e)}")
