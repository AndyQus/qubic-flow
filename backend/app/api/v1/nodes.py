from fastapi import APIRouter

router = APIRouter()


@router.get("/nodes")
def list_nodes():
    return []


@router.post("/nodes")
def create_node():
    return {}


@router.put("/nodes/{node_id}")
def update_node(node_id: int):
    return {}


@router.delete("/nodes/{node_id}")
def delete_node(node_id: int):
    return {}


@router.put("/nodes/reorder")
def reorder_nodes():
    return {}
