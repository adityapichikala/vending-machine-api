from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    BulkAddResponse,
    ItemBulkRequest,
    ItemCreate,
    ItemResponse,
    MessageResponse,
    SlotCreate,
    SlotFullView,
    SlotResponse,
)
from app.services import item_service, slot_service

router = APIRouter()


def _slot_404():
    raise HTTPException(status_code=404, detail="Slot not found")


@router.post("/slots", response_model=SlotResponse, status_code=201)
def create_slot(data: SlotCreate, db: Session = Depends(get_db)):
    try:
        slot = slot_service.create_slot(db, data)
        return SlotResponse(
            id=slot.id,
            code=slot.code,
            capacity=slot.capacity,
            current_item_count=slot.current_item_count,
        )
    except ValueError as e:
        if str(e) == "slot_limit_reached":
            raise HTTPException(status_code=400, detail="Slot limit reached")
        if str(e) == "slot_code_exists":
            raise HTTPException(status_code=409, detail="Slot code already exists")
        raise


@router.get("/slots", response_model=list[SlotResponse])
def list_slots(db: Session = Depends(get_db)):
    slots = slot_service.list_slots(db)
    return [
        SlotResponse(
            id=s.id,
            code=s.code,
            capacity=s.capacity,
            current_item_count=s.current_item_count,
        )
        for s in slots
    ]


@router.get("/slots/full-view", response_model=list[SlotFullView])
def full_view(db: Session = Depends(get_db)):
    return slot_service.get_full_view(db)


@router.delete("/slots/{slot_id}", response_model=MessageResponse)
def delete_slot(slot_id: str, db: Session = Depends(get_db)):
    try:
        slot_service.delete_slot(db, slot_id)
        return MessageResponse(message="Slot removed successfully")
    except ValueError as e:
        if str(e) == "slot_not_found":
            _slot_404()
        if str(e) == "slot_has_items":
            raise HTTPException(status_code=400, detail="Cannot delete slot with items")
        raise


@router.post("/slots/{slot_id}/items", response_model=ItemResponse, status_code=201)
def add_item_to_slot(slot_id: str, data: ItemCreate, db: Session = Depends(get_db)):
    try:
        item = item_service.add_item_to_slot(db, slot_id, data)
        return ItemResponse(
            id=item.id,
            name=item.name,
            price=item.price,
            quantity=item.quantity,
        )
    except ValueError as e:
        if str(e) == "slot_not_found":
            _slot_404()
        if str(e) == "capacity_exceeded":
            raise HTTPException(
                status_code=400,
                detail="Total items would exceed slot capacity",
            )
        raise


@router.post("/slots/{slot_id}/items/bulk", response_model=BulkAddResponse)
def bulk_add_items(slot_id: str, body: ItemBulkRequest, db: Session = Depends(get_db)):
    try:
        added = item_service.bulk_add_items(db, slot_id, body.items)
        return BulkAddResponse(added_count=added)
    except ValueError as e:
        if str(e) == "slot_not_found":
            _slot_404()
        if str(e) == "capacity_exceeded":
            raise HTTPException(
                status_code=400,
                detail="Total items would exceed slot capacity",
            )
        raise


@router.get("/slots/{slot_id}/items", response_model=list[ItemResponse])
def list_slot_items(slot_id: str, db: Session = Depends(get_db)):
    try:
        items = item_service.list_items_by_slot(db, slot_id)
        return [
            ItemResponse(id=i.id, name=i.name, price=i.price, quantity=i.quantity)
            for i in items
        ]
    except ValueError as e:
        if str(e) == "slot_not_found":
            _slot_404()
        raise
