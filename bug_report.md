# Vending Machine API -- Bug Report

Spec: [api-specifications.md](api-specifications.md)

---

## Live Test Results: 34 passed, 10 failed

## Endpoint-by-Endpoint: Spec vs Actual

| # | Endpoint | Spec Says | Actual API Does | Status |
|---|----------|-----------|-----------------|--------|
| 1 | `POST /slots` | Returns 201 with slot object | Works correctly | PASS |
| 1b | `POST /slots` (duplicate code) | Returns 409 | Returns 409 | PASS |
| 1c | `POST /slots` (exceeds MAX_SLOTS) | Returns 400 | Returns 400 | PASS |
| 1d | `POST /slots` (capacity=0) | Should reject | Returns 422 (pydantic validates) | PASS |
| 2 | `GET /slots` | Returns list of all slots | Works correctly | PASS |
| 3 | `DELETE /slots/{id}` (empty slot) | Returns 200, "Slot removed" | Works correctly | PASS |
| 3b | `DELETE /slots/{id}` (has items) | Should block deletion | **Allows deletion, orphans items** | FAIL |
| 4 | `POST /slots/{id}/items` | Returns 201 with item | **Returns 400 always** (inverted check) | FAIL |
| 4b | `POST /slots/{id}/items` (price=0) | Should reject (price > 0) | **Accepts price=0** (ge=0 not gt=0) | FAIL |
| 5 | `POST /slots/{id}/items/bulk` | Adds items, checks capacity | Adds items, **no capacity check** | FAIL |
| 5b | Bulk add slot count | Should update `current_item_count` | **Count stays 0** -- never updated | FAIL |
| 5c | Bulk add atomicity | All-or-nothing | **Commits per item** (partial failure) | FAIL |
| 6 | `GET /slots/{id}/items` | Returns item list | Works correctly | PASS |
| 7 | `GET /items/{id}` | Returns item with slot_id | Works correctly | PASS |
| 8 | `PATCH /items/{id}/price` | Updates price, returns 200 | Returns 200 but **`updated_at` frozen** | FAIL |
| 9 | `DELETE /slots/{id}/items/{id}?quantity=N` | Subtracts quantity | Works correctly | PASS |
| 10 | `DELETE /slots/{id}/items` | Clears slot | Works correctly | PASS |
| 11 | `GET /slots/full-view` | Slots with nested items | Works correctly | PASS |
| 12 | `POST /purchase` | Validates, returns change | Works correctly (when items exist) | PASS |
| 13 | `GET /purchase/change-breakdown?change=70` | Greedy denomination breakdown | Works for values >= 5 | PASS |
| 13b | `GET /purchase/change-breakdown?change=3` | Returns `{"2":1, "1":1}` | **Returns `{}`** -- missing denoms 1,2 | FAIL |

---

## Categorized Bugs

### A) Syntax / Configuration Errors

| Bug | File | Line | Issue |
|-----|------|------|-------|
| A1 | `config.py` | 7 | `SUPPORTED_DENOMINATIONS` missing `1` and `2`. Has `[5,10,20,50,100]`, spec says `[1,2,5,10,20,50,100]` |

### B) Runtime Errors

| Bug | File | Lines | Issue |
|-----|------|-------|-------|
| B1 | `item_service.py` | 15-16 | **CRITICAL.** Inverted capacity check: `< MAX_ITEMS_PER_SLOT` instead of `>`. Blocks ALL valid item additions with 400 error. |
| B2 | `item_service.py` | 61-63 | Saves old `updated_at`, then forces it back after price change. Timestamp never updates. |

### C) Logical Errors

| Bug | File | Lines | Issue |
|-----|------|-------|-------|
| C1 | `schemas.py` | 22, 28 | Price validation uses `ge=0` (allows zero). Spec requires `price > 0`. |
| C2 | `item_service.py` | 30-43 | Bulk add: (1) no capacity check, (2) `current_item_count` never updated. |
| C3 | `item_service.py` | 41 | Bulk add: `db.commit()` inside loop -- not atomic. Partial failures leave committed items. |
| C4 | `slot_service.py` | 30-35 | Slot deleted even when it has items. Spec says "Cannot delete if slot contains items". |
| C5 | `models.py` | 25 | Cascade missing `delete, delete-orphan`. Combined with `ondelete="SET NULL"` on FK, items get orphaned. |
| C6 | `item_service.py` | 42 | `time.sleep(0.05)` widens race window. Also in `purchase_service.py:12`. |

### D) Edge Case Failures

| Bug | File | Line | Issue |
|-----|------|------|-------|
| D1 | `schemas.py` | 75 | `cash_inserted` allows 0 (`ge=0`). Should be `gt=0`. |
| D2 | `purchase_service.py` | 17 | No validation that `cash_inserted` is a valid denomination. |
| D3 | `item_service.py` | ~77 | Stale `current_item_count` (from C2) can cause negative slot counts during removal. |

---

## Severity Summary

| Severity | Bugs | Impact |
|----------|------|--------|
| **Critical** | B1, C2 | Can't add items to slots (machine un-stockable) |
| **Medium** | A1, B2, C1, C3, C4, C5, C6 | Wrong data, no atomicity, orphaned records |
| **Low** | D1, D2, D3 | Edge cases, no immediate crash |

**Total: 12 bugs found (2 critical, 7 medium, 3 low)**
