# Error Priority List

Prioritized by impact on core vending machine functionality.

---

## Priority 1 -- CRITICAL (Fix First)

These bugs **break core functionality**. The vending machine cannot operate at all.

| # | Bug ID | Error | File | Why Critical |
|---|--------|-------|------|-------------|
| 1 | B1 | Inverted capacity check blocks ALL item additions | `item_service.py:15-16` | Cannot stock the machine via single-item endpoint. The `<` should be `>`. |
| 2 | C2 | Bulk add: no capacity check + count not updated | `item_service.py:30-43` | Only working way to add items, but it corrupts slot counts and allows overflow. |
| 3 | A1 | Missing denominations 1 and 2 | `config.py:7` | Change breakdown fails for any amount not divisible by 5. |

---

## Priority 2 -- MEDIUM (Fix Next)

These cause **wrong data or wrong behavior** but don't completely break the machine.

| # | Bug ID | Error | File | Why Medium |
|---|--------|-------|------|-----------|
| 4 | C1 | Price allows 0 (should be > 0) | `schemas.py:22,28` | Free items can be added to the machine. Quick one-line fix. |
| 5 | B2 | `updated_at` frozen after price update | `item_service.py:61-63` | Audit trail broken -- can't tell when prices changed. |
| 6 | C4 | Slot deletion allowed when items exist | `slot_service.py:30-35` | Items become orphaned in DB. |
| 7 | C5 | Missing cascade delete on Slot->Items | `models.py:25,34` | Orphaned items when slot deleted. Related to C4. |
| 8 | C3 | Bulk add commits per-item (not atomic) | `item_service.py:38-42` | Partial failures leave inconsistent data. |
| 9 | C6 | Intentional `time.sleep()` race conditions | `item_service.py:42`, `purchase_service.py:12` | Concurrent requests can double-sell or corrupt counts. |

---

## Priority 3 -- LOW (Fix Last)

These are **edge cases** that don't affect normal operation.

| # | Bug ID | Error | File | Why Low |
|---|--------|-------|------|---------|
| 10 | D1 | `cash_inserted` allows 0 | `schemas.py:75` | Business logic still rejects it; validation gap only. |
| 11 | D2 | No denomination validation on cash | `purchase_service.py:17` | Any integer accepted. Spec implies denomination check. |
| 12 | D3 | Stale counts can go negative | `item_service.py:77` | Side effect of C2; will be resolved when C2 is fixed. |

---

## Fix Order

```
P1: B1 -> C2 -> A1 (unblocks all item operations)
P2: C1 -> B2 -> C4+C5 -> C3 -> C6 (data integrity)
P3: D1 -> D2 -> D3 (polish)
```
