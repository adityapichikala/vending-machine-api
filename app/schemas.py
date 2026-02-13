from pydantic import BaseModel, Field


# --- Slot ---
class SlotCreate(BaseModel):
    code: str
    capacity: int = Field(..., gt=0)


class SlotResponse(BaseModel):
    id: str
    code: str
    capacity: int
    current_item_count: int

    model_config = {"from_attributes": True}


# --- Item ---
class ItemCreate(BaseModel):
    name: str
    price: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class ItemBulkEntry(BaseModel):
    name: str
    price: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class ItemBulkRequest(BaseModel):
    items: list[ItemBulkEntry]


class ItemResponse(BaseModel):
    id: str
    name: str
    price: int
    quantity: int

    model_config = {"from_attributes": True}


class ItemDetailResponse(ItemResponse):
    slot_id: str


class ItemPriceUpdate(BaseModel):
    price: int = Field(..., gt=0)


# --- Slot full view ---
class SlotFullViewItem(BaseModel):
    id: str
    name: str
    price: int
    quantity: int

    model_config = {"from_attributes": True}


class SlotFullView(BaseModel):
    id: str
    code: str
    capacity: int
    items: list[SlotFullViewItem]

    model_config = {"from_attributes": True}


# --- Purchase ---
class PurchaseRequest(BaseModel):
    item_id: str
    cash_inserted: int = Field(..., gt=0)


class PurchaseResponse(BaseModel):
    item: str
    price: int
    cash_inserted: int
    change_returned: int
    remaining_quantity: int
    message: str


class InsufficientCashError(BaseModel):
    error: str = "Insufficient cash"
    required: int
    inserted: int


class OutOfStockError(BaseModel):
    error: str = "Item out of stock"


# --- Generic message responses ---
class MessageResponse(BaseModel):
    message: str


class BulkAddResponse(BaseModel):
    message: str = "Items added successfully"
    added_count: int


class BulkRemoveBody(BaseModel):
    item_ids: list[str] | None = None


# --- Change breakdown (bonus) ---
class ChangeBreakdownResponse(BaseModel):
    change: int
    denominations: dict[str, int]
