"""
Comprehensive test script: Validates ACTUAL API behavior vs SPEC.
Runs against a live server at http://127.0.0.1:8001
"""
import json
import urllib.request
import urllib.error
import sys

BASE = "http://127.0.0.1:8005"


def req(method, path, body=None):
    """Make an HTTP request and return (status, parsed_json)."""
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        try:
            return e.code, json.loads(body_text)
        except:
            return e.code, body_text


def test(name, expected, actual, spec_note=""):
    """Compare expected vs actual and print result."""
    passed = expected == actual
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {name}")
    if not passed:
        print(f"         EXPECTED: {expected}")
        print(f"         ACTUAL  : {actual}")
    if spec_note and not passed:
        print(f"         SPEC    : {spec_note}")
    return passed


results = {"pass": 0, "fail": 0}


def track(passed):
    if passed:
        results["pass"] += 1
    else:
        results["fail"] += 1


print("=" * 70)
print("VENDING MACHINE API -- SPEC vs ACTUAL BEHAVIOR TEST")
print("=" * 70)

# ===================================================================
# 1. POST /slots -- Create Slot
# ===================================================================
print("\n--- 1. POST /slots (Create Slot) ---")
status, data = req("POST", "/slots", {"code": "A1", "capacity": 10})
track(test("Status 201", 201, status))
track(test("Has id field", True, "id" in data))
track(test("Code matches", "A1", data.get("code")))
track(test("Capacity matches", 10, data.get("capacity")))
track(test("current_item_count is 0", 0, data.get("current_item_count")))
SLOT_A1_ID = data.get("id", "")

# Duplicate code -> expect 409
status, data = req("POST", "/slots", {"code": "A1", "capacity": 5})
track(test("Duplicate code -> 409", 409, status, "409 -> Slot code already exists"))

# Create slots up to MAX_SLOTS (default 10)
for i in range(2, 11):
    req("POST", "/slots", {"code": f"S{i}", "capacity": 5})

status, data = req("POST", "/slots", {"code": "EXTRA", "capacity": 5})
track(test("Exceeding MAX_SLOTS -> 400", 400, status, "400 -> Slot limit reached"))

# capacity <= 0 -> expect 422 (pydantic gt=0 validation)
status, data = req("POST", "/slots", {"code": "BAD", "capacity": 0})
track(test("capacity=0 -> 422 validation error", 422, status))

# ===================================================================
# 2. GET /slots -- List Slots
# ===================================================================
print("\n--- 2. GET /slots (List Slots) ---")
status, data = req("GET", "/slots")
track(test("Status 200", 200, status))
track(test("Returns list", True, isinstance(data, list)))
track(test("10 slots created", 10, len(data)))

# ===================================================================
# 3. DELETE /slots/{slot_id} -- Remove Slot (delete one of the extra ones)
# ===================================================================
print("\n--- 3. DELETE /slots/{slot_id} (Remove Slot) ---")
# Get our S2 slot to delete (it's empty)
status, slots = req("GET", "/slots")
s2 = next((s for s in slots if s["code"] == "S2"), None)
if s2:
    status, data = req("DELETE", f"/slots/{s2['id']}")
    track(test("Delete empty slot -> 200", 200, status))
    track(test("Message correct", "Slot removed successfully", data.get("message")))

# Delete non-existent slot -> 404
status, data = req("DELETE", "/slots/nonexistent-id")
track(test("Delete non-existent -> 404", 404, status))

# ===================================================================
# 4. POST /slots/{slot_id}/items -- Add Item to Slot
# ===================================================================
print("\n--- 4. POST /slots/{slot_id}/items (Add Item) ---")

# Try adding valid item (quantity=5, capacity=10)
status, data = req("POST", f"/slots/{SLOT_A1_ID}/items",
                    {"name": "Coke", "price": 40, "quantity": 5})
track(test("Add item -> 201", 201, status,
           "Spec: should return 201 with item details"))

if status == 201:
    COKE_ID = data.get("id", "")
    track(test("Item name matches", "Coke", data.get("name")))
    track(test("Item price matches", 40, data.get("price")))
    track(test("Item quantity matches", 5, data.get("quantity")))
else:
    COKE_ID = None
    print(f"  [WARN] ADD ITEM FAILED with status {status}: {data}")
    print("         This is Bug #3 -- the inverted capacity check in item_service.py")

# Try price=0 -> Spec says price > 0, should reject
status, data = req("POST", f"/slots/{SLOT_A1_ID}/items",
                    {"name": "Free", "price": 0, "quantity": 1})
track(test("price=0 -> should be rejected (422)", 422, status,
           "Spec: price > 0, but schema uses ge=0 allowing zero"))

# Non-existent slot
status, data = req("POST", "/slots/nonexistent/items",
                    {"name": "X", "price": 10, "quantity": 1})
track(test("Non-existent slot -> 404", 404, status))

# ===================================================================
# 5. POST /slots/{slot_id}/items/bulk -- Bulk Add Items
# ===================================================================
print("\n--- 5. POST /slots/{slot_id}/items/bulk (Bulk Add) ---")

# Create a fresh slot for bulk test
req("POST", "/slots", {"code": "BULK1", "capacity": 10})
status, slots = req("GET", "/slots")
bulk_slot = next((s for s in slots if s["code"] == "BULK1"), None)
BULK_SLOT_ID = bulk_slot["id"] if bulk_slot else SLOT_A1_ID

status, data = req("POST", f"/slots/{BULK_SLOT_ID}/items/bulk", {
    "items": [
        {"name": "Pepsi", "price": 35, "quantity": 5},
        {"name": "Sprite", "price": 30, "quantity": 3},
    ]
})
track(test("Bulk add -> 200", 200, status))
if status == 200:
    track(test("added_count is 2", 2, data.get("added_count")))

# Check if capacity was updated
status, slot_data = req("GET", "/slots")
bulk_slot_after = next((s for s in slot_data if s["id"] == BULK_SLOT_ID), None)
if bulk_slot_after:
    track(test("Bulk add updates current_item_count to 8", 8,
               bulk_slot_after.get("current_item_count"),
               "Spec: slot count should reflect added items; code never updates it"))

# Bulk add exceeding capacity -- spec says should fail
status, data = req("POST", f"/slots/{BULK_SLOT_ID}/items/bulk", {
    "items": [
        {"name": "Fanta", "price": 25, "quantity": 50},
    ]
})
track(test("Bulk add exceeding capacity -> 400", 400, status,
           "Spec: Total new quantity must not exceed slot capacity; code has no check"))

# ===================================================================
# 6. GET /slots/{slot_id}/items -- View Items in Slot
# ===================================================================
print("\n--- 6. GET /slots/{slot_id}/items (View Slot Items) ---")
status, data = req("GET", f"/slots/{BULK_SLOT_ID}/items")
track(test("Status 200", 200, status))
track(test("Returns list", True, isinstance(data, list)))

# ===================================================================
# 7. GET /items/{item_id} -- View Single Item
# ===================================================================
print("\n--- 7. GET /items/{item_id} (View Single Item) ---")
# Get an item_id from the bulk slot
status, items = req("GET", f"/slots/{BULK_SLOT_ID}/items")
if items and len(items) > 0:
    TEST_ITEM_ID = items[0]["id"]
    status, data = req("GET", f"/items/{TEST_ITEM_ID}")
    track(test("Status 200", 200, status))
    track(test("Has slot_id field", True, "slot_id" in data))
    track(test("slot_id matches", BULK_SLOT_ID, data.get("slot_id")))
else:
    print("  [WARN] No items to test with")

# Non-existent item
status, data = req("GET", "/items/nonexistent")
track(test("Non-existent item -> 404", 404, status))

# ===================================================================
# 8. PATCH /items/{item_id}/price -- Update Price
# ===================================================================
print("\n--- 8. PATCH /items/{item_id}/price (Update Price) ---")
if items and len(items) > 0:
    # Get item before update
    status, before = req("GET", f"/items/{TEST_ITEM_ID}")
    old_price = before.get("price")

    status, data = req("PATCH", f"/items/{TEST_ITEM_ID}/price", {"price": 45})
    track(test("Status 200", 200, status))
    track(test("Message correct", "Price updated successfully", data.get("message")))

    # Verify price actually changed
    status, after = req("GET", f"/items/{TEST_ITEM_ID}")
    track(test("Price actually updated", 45, after.get("price")))

# ===================================================================
# 9. DELETE /slots/{slot_id}/items/{item_id} -- Remove Item (Partial)
# ===================================================================
print("\n--- 9. DELETE /slots/{id}/items/{id} (Remove Item) ---")
if items and len(items) > 0:
    # Partial removal: ?quantity=2
    status, data = req("DELETE", f"/slots/{BULK_SLOT_ID}/items/{TEST_ITEM_ID}?quantity=2")
    track(test("Partial remove -> 200", 200, status))
    track(test("Message correct", "Item(s) removed successfully", data.get("message")))

    # Verify quantity decreased
    status, after = req("GET", f"/items/{TEST_ITEM_ID}")
    if status == 200:
        expected_qty = items[0]["quantity"] - 2
        track(test(f"Quantity reduced by 2", expected_qty, after.get("quantity")))

# ===================================================================
# 10. DELETE /slots/{slot_id}/items -- Bulk Remove / Empty Slot
# ===================================================================
print("\n--- 10. DELETE /slots/{id}/items (Bulk Remove / Empty) ---")
# Empty the entire bulk slot
status, data = req("DELETE", f"/slots/{BULK_SLOT_ID}/items")
track(test("Empty slot -> 200", 200, status))
track(test("Message correct", "Slot cleared successfully", data.get("message")))

# Verify slot is empty
status, items_after = req("GET", f"/slots/{BULK_SLOT_ID}/items")
track(test("Slot has 0 items after clear", 0, len(items_after) if isinstance(items_after, list) else -1))

# ===================================================================
# 11. GET /slots/full-view -- Full View
# ===================================================================
print("\n--- 11. GET /slots/full-view (Full View) ---")
status, data = req("GET", "/slots/full-view")
track(test("Status 200", 200, status))
track(test("Returns list", True, isinstance(data, list)))
if len(data) > 0:
    track(test("Has 'items' nested list", True, "items" in data[0]))

# ===================================================================
# 12. POST /purchase -- Purchase Item
# ===================================================================
print("\n--- 12. POST /purchase (Purchase Item) ---")

# Need an item to purchase. Create a fresh slot + item via bulk (since add_item is buggy)
req("POST", "/slots", {"code": "PURCH", "capacity": 10})
status, slots = req("GET", "/slots")
purch_slot = next((s for s in slots if s["code"] == "PURCH"), None)

if purch_slot:
    PURCH_SLOT_ID = purch_slot["id"]
    req("POST", f"/slots/{PURCH_SLOT_ID}/items/bulk", {
        "items": [{"name": "Water", "price": 20, "quantity": 3}]
    })
    status, purch_items = req("GET", f"/slots/{PURCH_SLOT_ID}/items")
    if purch_items and len(purch_items) > 0:
        WATER_ID = purch_items[0]["id"]

        # Successful purchase
        status, data = req("POST", "/purchase",
                           {"item_id": WATER_ID, "cash_inserted": 50})
        track(test("Purchase -> 200", 200, status))
        if status == 200:
            track(test("item name is 'Water'", "Water", data.get("item")))
            track(test("price is 20", 20, data.get("price")))
            track(test("cash_inserted is 50", 50, data.get("cash_inserted")))
            track(test("change_returned is 30", 30, data.get("change_returned")))
            track(test("remaining_quantity is 2", 2, data.get("remaining_quantity")))
            track(test("message correct", "Purchase successful", data.get("message")))

        # Insufficient cash
        status, data = req("POST", "/purchase",
                           {"item_id": WATER_ID, "cash_inserted": 10})
        track(test("Insufficient cash -> 400", 400, status))

        # Buy remaining to test out of stock
        req("POST", "/purchase", {"item_id": WATER_ID, "cash_inserted": 20})
        req("POST", "/purchase", {"item_id": WATER_ID, "cash_inserted": 20})
        status, data = req("POST", "/purchase",
                           {"item_id": WATER_ID, "cash_inserted": 20})
        track(test("Out of stock -> 400", 400, status))

        # Non-existent item
        status, data = req("POST", "/purchase",
                           {"item_id": "fake-id", "cash_inserted": 50})
        track(test("Non-existent item -> 404", 404, status))

# ===================================================================
# 13. GET /purchase/change-breakdown -- Change Breakdown
# ===================================================================
print("\n--- 13. GET /purchase/change-breakdown ---")
status, data = req("GET", "/purchase/change-breakdown?change=70")
track(test("Status 200", 200, status))
track(test("change is 70", 70, data.get("change")))

# Check denominations -- spec says [1,2,5,10,20,50,100], code uses [5,10,20,50,100]
denoms = data.get("denominations", {})
expected_denoms = {"50": 1, "20": 1}  # Spec expects this
track(test("Denominations for 70", expected_denoms, denoms,
           "With correct denoms [1,2,5,...] this should be {50:1, 20:1}"))

# Test a value that needs ₹1 and ₹2 coins
status, data = req("GET", "/purchase/change-breakdown?change=3")
denoms_3 = data.get("denominations", {})
expected_3 = {"2": 1, "1": 1}  # Spec expects ₹2 + ₹1
track(test("Denominations for 3 (needs ₹1,₹2)", expected_3, denoms_3,
           "Code is missing denominations 1 and 2, so it returns {} for change=3"))

# Test change=0
status, data = req("GET", "/purchase/change-breakdown?change=0")
track(test("change=0 -> empty denominations", {}, data.get("denominations", {})))

# ===================================================================
# SPEC vs ACTUAL: Slot deletion with items
# ===================================================================
print("\n--- EXTRA: Delete slot that has items ---")
# Create slot with items
req("POST", "/slots", {"code": "DELTEST", "capacity": 10})
status, slots = req("GET", "/slots")
del_slot = next((s for s in slots if s["code"] == "DELTEST"), None)
if del_slot:
    DEL_SLOT_ID = del_slot["id"]
    req("POST", f"/slots/{DEL_SLOT_ID}/items/bulk", {
        "items": [{"name": "Chips", "price": 25, "quantity": 3}]
    })
    # Try deleting it
    status, data = req("DELETE", f"/slots/{DEL_SLOT_ID}")
    track(test("Delete slot with items -> should be blocked (400)", 400, status,
               "Spec: Cannot delete if slot contains items; code allows it"))

# ===================================================================
# SUMMARY
# ===================================================================
print("\n" + "=" * 70)
print(f"RESULTS: {results['pass']} passed, {results['fail']} failed")
print("=" * 70)
