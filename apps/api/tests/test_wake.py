async def test_wake_touches_the_database_and_is_never_cached(client):
    r = await client.get("/v1/wake")
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert r.headers["cache-control"] == "no-store"
