"""Admin CRUD for dates, items and pujas: what can change freely, and what is protected once devotees pay."""

from datetime import UTC, datetime, timedelta

from tests.conftest import book, login
from tests.test_catalog_admin import _new_puja


def _at(days: float) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).replace(microsecond=0, tzinfo=None).isoformat()


async def _event_of_puja_1(client) -> int:
    return (await client.get("/v1/en/pujas/1")).json()["event"]["id"]


async def test_event_edit_and_delete_without_bookings(staff_client):
    p = await _new_puja(staff_client)
    r = await staff_client.post("/v1/admin/events", json={"puja_id": p["id"], "starts_at": _at(5)})
    assert r.status_code == 201, r.text
    ev = r.json()
    assert ev["can_edit_time"] and ev["can_delete"]

    r = await staff_client.patch(f"/v1/admin/events/{ev['id']}",
                                 json={"starts_at": _at(9), "cutoff_hours": 12, "video_sla_hours": 30})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["cutoff_hours"] == 12 and out["video_sla_hours"] == 30
    assert datetime.fromisoformat(out["starts_at"]) > datetime.now(UTC) + timedelta(days=8)

    assert (await staff_client.patch(f"/v1/admin/events/{ev['id']}", json={"starts_at": _at(-1)})).status_code == 400
    assert (await staff_client.post("/v1/admin/events", json={"puja_id": p["id"], "starts_at": _at(-1)})).status_code == 400

    r = await staff_client.delete(f"/v1/admin/events/{ev['id']}")
    assert r.json() == {"result": "deleted"}
    assert (await staff_client.get(f"/v1/admin/events/{ev['id']}")).status_code == 404


async def test_paid_event_date_is_protected_but_sla_and_cutoff_can_change(client, staff_client):
    await book(client)
    ev_id = await _event_of_puja_1(client)
    r = await staff_client.patch(f"/v1/admin/events/{ev_id}", json={"starts_at": _at(20)})
    assert r.status_code == 409 and r.json()["detail"] == "has_bookings_use_reschedule"
    r = await staff_client.patch(f"/v1/admin/events/{ev_id}", json={"video_sla_hours": 72, "cutoff_hours": 6})
    assert r.status_code == 200, r.text
    assert r.json()["video_sla_hours"] == 72 and r.json()["cutoff_hours"] == 6
    r = await staff_client.delete(f"/v1/admin/events/{ev_id}")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "has_bookings"


async def test_event_with_abandoned_draft_is_cancelled_and_cannot_be_paid(client, staff_client):
    draft = await book(client, pay=False)
    ev_id = await _event_of_puja_1(client)
    assert (await staff_client.delete(f"/v1/admin/events/{ev_id}")).json() == {"result": "cancelled"}
    assert (await staff_client.get(f"/v1/admin/events/{ev_id}")).json()["status"] == "cancelled"
    await login(client, "+919876543210")
    r = await client.post(f"/v1/drafts/{draft['draft_id']}/pay", json={
        "consent_terms": True, "expected_total_minor": draft["view"]["pricing"]["total_minor"]})
    assert r.status_code >= 400 and "event_closed" in r.text


async def test_list_filters(staff_client):
    p = await _new_puja(staff_client)
    for d in (3, 4):
        await staff_client.post("/v1/admin/events", json={"puja_id": p["id"], "starts_at": _at(d)})
    rows = (await staff_client.get(f"/v1/admin/events?puja_id={p['id']}&when=all")).json()
    assert len(rows) == 2 and all(r["puja_id"] == p["id"] for r in rows)
    assert (await staff_client.get(f"/v1/admin/events?puja_id={p['id']}&when=past")).json() == []
    assert (await staff_client.get(f"/v1/admin/events?puja_id={p['id']}&status=cancelled")).json() == []


async def test_items_and_puja_delete(client, staff_client):
    p = await _new_puja(staff_client)
    r = await staff_client.put(f"/v1/admin/pujas/{p['id']}/addons", json=[{
        "price_inr_minor": 10100, "price_usd_minor": 300, "max_qty": 3,
        "translations": {"en": {"name": "Coconut", "description": "Whole coconut offered"}}}])
    item = r.json()["addons"][0]
    assert item["translations"]["en"]["description"] == "Whole coconut offered"
    r = await staff_client.delete(f"/v1/admin/pujas/{p['id']}/addons/{item['id']}")
    assert r.status_code == 200 and r.json()["addons"] == []

    await staff_client.post("/v1/admin/events", json={"puja_id": p["id"], "starts_at": _at(5)})
    assert (await staff_client.delete(f"/v1/admin/pujas/{p['id']}")).json() == {"result": "deleted"}
    assert (await staff_client.get(f"/v1/admin/pujas/{p['id']}")).status_code == 404

    await book(client)
    r = await staff_client.delete("/v1/admin/pujas/1")
    assert r.status_code == 409 and r.json()["detail"] == "has_bookings_unpublish_instead"
