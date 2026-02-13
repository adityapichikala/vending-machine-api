# Fix Approach -- How Each Bug Was Solved

This document tracks the approach used to fix each bug, in priority order.

---

## P1-1: B1 -- Inverted Capacity Check (CRITICAL)

**File:** `app/services/item_service.py` lines 15-16

**The Bug:**
```python
# BROKEN: This second check is inverted and wrong
if slot.current_item_count + data.quantity > slot.capacity:
    raise ValueError("capacity_exceeded")
if slot.current_item_count + data.quantity < settings.MAX_ITEMS_PER_SLOT:  # BUG
    raise ValueError("capacity_exceeded")
```

The second condition uses `<` instead of `>`, so it rejects items when count is UNDER the limit.
Also, this second check is redundant -- the first check against `slot.capacity` already handles it.

**The Fix:**
Remove the entire second check (lines 15-16). The first check on line 13 already validates
capacity correctly:
```python
if slot.current_item_count + data.quantity > slot.capacity:
    raise ValueError("capacity_exceeded")
# Line 15-16 removed entirely
```

**Why this works:** `slot.capacity` is set per-slot. `MAX_ITEMS_PER_SLOT` is a global config.
The spec says capacity is per-slot, so only the `slot.capacity` check matters.

---

## P1-2: C2 -- Bulk Add Missing Capacity Check + Count Update

**File:** `app/services/item_service.py` lines 30-43

**The Bug:**
1. No check that total items would exceed slot capacity
2. `slot.current_item_count` never incremented after bulk add
3. `db.commit()` inside loop (not atomic)

**The Fix:**
```python
def bulk_add_items(db, slot_id, entries):
    slot = db.query(Slot).filter(Slot.id == slot_id).first()
    if not slot:
        raise ValueError("slot_not_found")

    # FIX 1: Calculate total and check capacity BEFORE adding
    total_qty = sum(e.quantity for e in entries)
    if slot.current_item_count + total_qty > slot.capacity:
        raise ValueError("capacity_exceeded")

    added = 0
    for e in entries:
        if e.quantity <= 0:
            continue
        item = Item(name=e.name, price=e.price, slot_id=slot_id, quantity=e.quantity)
        db.add(item)
        # FIX 2: Update slot count
        slot.current_item_count += e.quantity
        added += 1

    # FIX 3: Single commit at the end (atomic)
    db.commit()
    return added
```

**Why:** Pre-validate total, update counts, commit once.

---

## P1-3: A1 -- Missing Denominations 1 and 2

**File:** `app/config.py` line 7

**The Bug:**
```python
SUPPORTED_DENOMINATIONS: list[int] = [5, 10, 20, 50, 100]
```

**The Fix:**
```python
SUPPORTED_DENOMINATIONS: list[int] = [1, 2, 5, 10, 20, 50, 100]
```

**Why:** Spec explicitly lists 1 and 2 as valid denominations.

---

## P2-4: C1 -- Price Allows Zero

**File:** `app/schemas.py` lines 22, 28

**The Bug:**
```python
price: int = Field(..., ge=0)  # ge=0 allows zero
```

**The Fix:**
```python
price: int = Field(..., gt=0)  # gt=0 requires positive
```

**Why:** Spec says `price > 0`. A free vending machine item makes no sense.

---

## P2-5: B2 -- updated_at Frozen After Price Update

**File:** `app/services/item_service.py` lines 61-63

**The Bug:**
```python
prev_updated = item.updated_at
item.price = price
item.updated_at = prev_updated  # Forces old timestamp back!
```

**The Fix:**
```python
item.price = price
# Remove the lines that save and restore updated_at.
# SQLAlchemy's onupdate=datetime.utcnow will handle it automatically.
```

**Why:** The `onupdate` on the model column already auto-updates the timestamp.
The code was deliberately overriding it with the old value.

---

## P2-6: C4 -- Slot Deletion Allowed With Items

**File:** `app/services/slot_service.py` lines 30-35

**The Bug:**
```python
def delete_slot(db, slot_id):
    slot = get_slot_by_id(db, slot_id)
    if not slot:
        raise ValueError("slot_not_found")
    db.delete(slot)  # No check for items!
    db.commit()
```

**The Fix:**
```python
def delete_slot(db, slot_id):
    slot = get_slot_by_id(db, slot_id)
    if not slot:
        raise ValueError("slot_not_found")
    if slot.current_item_count > 0:
        raise ValueError("slot_has_items")
    db.delete(slot)
    db.commit()
```

Also add error handler in `routers/slots.py`:
```python
if str(e) == "slot_has_items":
    raise HTTPException(status_code=400, detail="Cannot delete slot with items")
```

**Why:** Spec says "Cannot delete if slot contains items".

---

## P2-7: C5 -- Missing Cascade Delete

**File:** `app/models.py` line 25

**The Bug:**
```python
items = relationship("Item", back_populates="slot", cascade="save-update, merge")
```

**The Fix:**
```python
items = relationship("Item", back_populates="slot", cascade="all, delete-orphan")
```

Also change `ondelete="SET NULL"` to `ondelete="CASCADE"` on line 34:
```python
slot_id = Column(CHAR(36), ForeignKey("slots.id", ondelete="CASCADE"), nullable=True)
```

**Why:** When a slot is deleted (if we allow it), items should be deleted too, not orphaned.

---

## P2-8: C3 -- Bulk Add Not Atomic

**File:** `app/services/item_service.py` line 41

**The Bug:** `db.commit()` inside the for loop.

**The Fix:** Already handled in P1-2 fix -- moved `db.commit()` outside the loop.

---

## P2-9: C6 -- Remove time.sleep() Race Conditions

**Files:** `item_service.py:42`, `purchase_service.py:12`

**The Bug:**
```python
time.sleep(0.05)  # demo: widens race window
```

**The Fix:** Remove both `time.sleep()` calls and the `import time` statements.

**Why:** These are intentional sabotage, not needed for any business logic.

---

## P3-10: D1 -- cash_inserted Allows Zero

**File:** `app/schemas.py` line 75

**The Bug:**
```python
cash_inserted: int = Field(..., ge=0)
```

**The Fix:**
```python
cash_inserted: int = Field(..., gt=0)
```

---

## P3-11: D2 -- No Denomination Validation on Cash

**File:** `app/services/purchase_service.py`

**The Bug:** No check that `cash_inserted` is a sum of valid denominations.

**The Fix:** This is noted in the spec as optional. The comment on line 17 acknowledges it.
Skipping this fix as it's not strictly required.

---

## P3-12: D3 -- Stale Counts Can Go Negative

**The Bug:** Side effect of C2 (bulk add not updating counts).

**The Fix:** Already resolved by fixing C2 -- counts are now properly maintained.

---

## Status Tracker

**Test Results After Fixes: 47 passed, 0 failed**

| # | Bug | Priority | Status |
|---|-----|----------|--------|
| 1 | B1 - Inverted capacity check | P1 | FIXED |
| 2 | C2 - Bulk add issues | P1 | FIXED |
| 3 | A1 - Missing denominations | P1 | FIXED |
| 4 | C1 - Price allows 0 | P2 | FIXED |
| 5 | B2 - updated_at frozen | P2 | FIXED |
| 6 | C4 - Slot deletion with items | P2 | FIXED |
| 7 | C5 - Missing cascade | P2 | FIXED |
| 8 | C3 - Not atomic (fixed with C2) | P2 | FIXED |
| 9 | C6 - time.sleep race conditions | P2 | FIXED |
| 10 | D1 - cash_inserted allows 0 | P3 | FIXED |
| 11 | D2 - No denomination validation | P3 | SKIP |
| 12 | D3 - Stale counts (fixed with C2) | P3 | FIXED |

