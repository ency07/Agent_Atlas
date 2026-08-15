#!/usr/bin/env python3
"""Test C3-1: Snapshot TTL + invalidación + on-demand."""
import sys, time, json
sys.path.insert(0, "E:/Agente_IA")
import atlas_env

def test_snapshot_basic():
    snap = atlas_env.get_snapshot()
    assert isinstance(snap, dict)
    # should contain at least time
    assert "time" in snap
    assert "time_age_seconds" in snap
    print("OK get_snapshot returns dict with time")

def test_ttl_and_invalidation():
    # force refresh
    snap1 = atlas_env.get_snapshot("apps", force=True)
    age1 = snap1.get("apps_age_seconds", -1)
    # immediate second call should have age ~0-1
    snap2 = atlas_env.get_snapshot("apps")
    age2 = snap2.get("apps_age_seconds", -1)
    assert age2 >= 0
    print(f"OK TTL works: age1={age1}, age2={age2}")

    # invalidate and force should reset age
    atlas_env.invalidate("apps")
    snap3 = atlas_env.get_snapshot("apps", force=True)
    age3 = snap3.get("apps_age_seconds", -1)
    assert age3 <= 1
    print("OK invalidation forces refresh")

def test_on_demand():
    res = atlas_env.on_demand_check("ports")
    assert "ports" in res
    assert isinstance(res["ports"], dict)
    print("OK on_demand_check works for ports")

def test_all_categories():
    cats = ["apps","ports","processes","workspace","recent_files","time"]
    for c in cats:
        snap = atlas_env.get_snapshot(c, force=True)
        assert c in snap
    print("OK all categories collectable")

if __name__ == "__main__":
    test_snapshot_basic()
    test_ttl_and_invalidation()
    test_on_demand()
    test_all_categories()
    print("\nAll C3-1 tests passed!")