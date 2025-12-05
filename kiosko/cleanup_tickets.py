#!/usr/bin/env python3
"""
Script to cleanup/complete old tickets.
Can complete specific tickets or all tickets for a cabin.
Run this on the Raspberry Pi to fix stale tickets.
"""
import sqlite3
from pathlib import Path
import sys

DB_PATH = Path(__file__).resolve().parent / "kiosko.db"

def complete_ticket(ticket_id: int) -> bool:
    """Complete a specific ticket by ID."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    # Update ticket status to 'completed'
    cur.execute(
        "UPDATE tickets SET status = 'completed', exit_timestamp = CURRENT_TIMESTAMP WHERE id = ?",
        (ticket_id,)
    )
    affected = cur.rowcount
    conn.commit()
    
    # Get cabin ID before closing
    cabin_row = cur.execute("SELECT cabina_id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    cabin_id = cabin_row[0] if cabin_row else None
    
    conn.close()
    
    if affected > 0:
        print(f"✓ Completed ticket {ticket_id} for {cabin_id}")
        return True
    else:
        print(f"✗ Ticket {ticket_id} not found")
        return False

def complete_cabin_tickets(cabina_id: str) -> int:
    """Complete all active tickets for a specific cabin."""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    
    # Count active tickets first
    count_row = cur.execute(
        "SELECT COUNT(*) FROM tickets WHERE cabina_id = ? AND status = 'active'",
        (cabina_id,)
    ).fetchone()
    count = count_row[0] if count_row else 0
    
    if count == 0:
        conn.close()
        print(f"No active tickets found for {cabina_id}")
        return 0
    
    # Complete all active tickets for this cabin
    cur.execute(
        "UPDATE tickets SET status = 'completed', exit_timestamp = CURRENT_TIMESTAMP WHERE cabina_id = ? AND status = 'active'",
        (cabina_id,)
    )
    completed = cur.rowcount
    conn.commit()
    
    # Update cabin status to free
    cur.execute("UPDATE cabinas SET estado = 'free', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (cabina_id,))
    conn.commit()
    
    conn.close()
    
    print(f"✓ Completed {completed} ticket(s) for {cabina_id} and set cabin to 'free'")
    return completed

def list_active_tickets():
    """List all active tickets."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    tickets = cur.execute(
        "SELECT id, token, cabina_id, entry_timestamp FROM tickets WHERE status = 'active' ORDER BY entry_timestamp DESC"
    ).fetchall()
    
    if not tickets:
        print("No active tickets found.")
        conn.close()
        return
    
    print(f"\n{'Ticket ID':<12} {'Cabin ID':<15} {'Token (first 8)':<15} {'Entry Time'}")
    print("-" * 60)
    for ticket in tickets:
        token_short = ticket["token"][:8] if ticket["token"] else "N/A"
        print(f"{ticket['id']:<12} {ticket['cabina_id']:<15} {token_short:<15} {ticket['entry_timestamp']}")
    
    conn.close()

def main():
    """Main function with interactive menu."""
    if not DB_PATH.exists():
        print(f"ERROR: Database file not found at {DB_PATH}")
        sys.exit(1)
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "list":
            list_active_tickets()
        
        elif command == "complete-cabin" and len(sys.argv) > 2:
            cabina_id = sys.argv[2].upper()
            if not cabina_id.startswith("CABINA-"):
                cabina_id = f"CABINA-{cabina_id.zfill(2)}"
            print(f"Completing all active tickets for {cabina_id}...")
            complete_cabin_tickets(cabina_id)
        
        elif command == "complete-ticket" and len(sys.argv) > 2:
            try:
                ticket_id = int(sys.argv[2])
                print(f"Completing ticket {ticket_id}...")
                complete_ticket(ticket_id)
            except ValueError:
                print(f"ERROR: Invalid ticket ID: {sys.argv[2]}")
        
        else:
            print_usage()
    else:
        print_usage()

def print_usage():
    """Print usage instructions."""
    print("""
Usage: python cleanup_tickets.py <command> [arguments]

Commands:
  list                                    - List all active tickets
  complete-cabin <cabina_id>              - Complete all tickets for a cabin (e.g., CABINA-04 or just 04)
  complete-ticket <ticket_id>             - Complete a specific ticket by ID

Examples:
  python cleanup_tickets.py list
  python cleanup_tickets.py complete-cabin CABINA-04
  python cleanup_tickets.py complete-cabin 04
  python cleanup_tickets.py complete-ticket 5
""")

if __name__ == "__main__":
    main()
