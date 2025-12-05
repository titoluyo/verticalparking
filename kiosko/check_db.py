#!/usr/bin/env python3
"""
Quick script to check database state - cabins and tickets.
Run this on the Raspberry Pi to debug cabin availability issues.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "kiosko.db"

def check_database():
    """Check and display cabin and ticket states."""
    if not DB_PATH.exists():
        print(f"ERROR: Database file not found at {DB_PATH}")
        return
    
    print(f"Database location: {DB_PATH}")
    print("=" * 60)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Check all cabins
    print("\n=== CABINS ===")
    cabins = cur.execute("SELECT id, estado, minimum_distance, updated_at FROM cabinas ORDER BY id").fetchall()
    if not cabins:
        print("No cabins found in database!")
    else:
        print(f"{'Cabin ID':<15} {'Estado':<10} {'Min Distance':<15} {'Updated At'}")
        print("-" * 60)
        for cabin in cabins:
            min_dist = cabin["minimum_distance"] if cabin["minimum_distance"] else "None"
            updated = cabin["updated_at"] if cabin["updated_at"] else "Never"
            print(f"{cabin['id']:<15} {cabin['estado']:<10} {str(min_dist):<15} {updated}")
    
    # Check active tickets
    print("\n=== ACTIVE TICKETS ===")
    tickets = cur.execute(
        "SELECT id, token, cabina_id, status, entry_timestamp FROM tickets WHERE status = 'active' ORDER BY entry_timestamp DESC"
    ).fetchall()
    if not tickets:
        print("No active tickets found.")
    else:
        print(f"{'Ticket ID':<10} {'Token (first 8)':<15} {'Cabin ID':<15} {'Entry Time'}")
        print("-" * 60)
        for ticket in tickets:
            token_short = ticket["token"][:8] if ticket["token"] else "N/A"
            entry_time = ticket["entry_timestamp"] if ticket["entry_timestamp"] else "N/A"
            print(f"{ticket['id']:<10} {token_short:<15} {ticket['cabina_id']:<15} {entry_time}")
    
    # Check which cabins have active tickets
    print("\n=== CABIN TO TICKET MAPPING ===")
    for cabin in cabins:
        cabin_id = cabin["id"]
        active_tickets = cur.execute(
            "SELECT COUNT(*) as count FROM tickets WHERE cabina_id = ? AND status = 'active'",
            (cabin_id,)
        ).fetchone()
        count = active_tickets["count"] if active_tickets else 0
        estado = cabin["estado"]
        has_ticket = "YES" if count > 0 else "NO"
        match_status = "✓ MATCH" if (estado == "busy" and count > 0) or (estado == "free" and count == 0) else "✗ MISMATCH"
        print(f"{cabin_id}: estado={estado}, active_tickets={count}, has_ticket={has_ticket} {match_status}")
    
    # Summary
    print("\n=== SUMMARY ===")
    free_cabins = [c for c in cabins if c["estado"] == "free"]
    busy_cabins = [c for c in cabins if c["estado"] == "busy"]
    print(f"Total cabins: {len(cabins)}")
    print(f"Cabins marked 'free': {len(free_cabins)}")
    print(f"Cabins marked 'busy': {len(busy_cabins)}")
    print(f"Active tickets: {len(tickets)}")
    
    # Find cabins that should be free (no active tickets but marked busy)
    print("\n=== POTENTIAL ISSUES ===")
    issues = []
    for cabin in cabins:
        cabin_id = cabin["id"]
        active_tickets = cur.execute(
            "SELECT COUNT(*) as count FROM tickets WHERE cabina_id = ? AND status = 'active'",
            (cabin_id,)
        ).fetchone()
        count = active_tickets["count"] if active_tickets else 0
        if cabin["estado"] == "busy" and count == 0:
            issues.append(f"{cabin_id} is marked 'busy' but has NO active tickets (should be 'free')")
        elif cabin["estado"] == "free" and count > 0:
            issues.append(f"{cabin_id} is marked 'free' but has {count} active ticket(s) (should be 'busy')")
    
    if issues:
        for issue in issues:
            print(f"⚠ {issue}")
    else:
        print("✓ No issues found - all cabin estados match their ticket status")
    
    conn.close()

if __name__ == "__main__":
    check_database()
