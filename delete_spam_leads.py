#!/usr/bin/env python
"""
Script to delete spam leads from the database.
Usage:
    python delete_spam_leads.py
    python delete_spam_leads.py --name Michaelvieks
    python delete_spam_leads.py --dry-run
"""

import os
import sys
import argparse

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "samsdriving.settings")

import django

def delete_via_django_orm(target_name="Michaelvieks", dry_run=False):
    from crm.models import Lead, LeadNote, ScheduledEmail

    spam_leads = Lead.objects.filter(first_name__iexact=target_name)
    count = spam_leads.count()

    if count == 0:
        # Also try icontains just in case
        spam_leads = Lead.objects.filter(first_name__icontains=target_name)
        count = spam_leads.count()

    print(f"\n[INFO] Found {count} lead(s) matching first_name: '{target_name}'")

    if count == 0:
        print("[INFO] No matching spam leads found to delete.")
        return 0

    print("\nMatching Leads:")
    print("-" * 65)
    for lead in spam_leads[:20]:
        print(f"ID: {lead.id} | Name: {lead.first_name} {lead.last_name} | Email: {lead.email} | Created: {lead.created_at}")
    if count > 20:
        print(f"... and {count - 20} more.")
    print("-" * 65)

    if dry_run:
        print(f"\n[DRY RUN] Would delete {count} lead(s). No changes made.")
        return count

    # Delete related notes & scheduled emails, then delete leads
    lead_ids = list(spam_leads.values_list("id", flat=True))
    notes_deleted = LeadNote.objects.filter(lead_id__in=lead_ids).delete()[0]
    emails_deleted = ScheduledEmail.objects.filter(to_lead_id__in=lead_ids).delete()[0]
    leads_deleted = spam_leads.delete()[0]

    print(f"\n[SUCCESS] Deleted {leads_deleted} lead(s), {notes_deleted} lead note(s), and {emails_deleted} scheduled email(s).")
    return leads_deleted


def delete_via_direct_sqlite(target_name="Michaelvieks", dry_run=False):
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.sqlite3")
    if not os.path.exists(db_path):
        print(f"[ERROR] SQLite database not found at {db_path}")
        return 0

    print(f"[INFO] Connecting directly to SQLite ({db_path})...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, first_name, last_name, email, created_at FROM crm_lead WHERE LOWER(first_name) = LOWER(?) OR LOWER(first_name) LIKE LOWER(?)",
        (target_name, f"%{target_name}%"),
    )
    rows = cur.fetchall()
    count = len(rows)

    print(f"\n[INFO] Found {count} lead(s) matching '{target_name}' in SQLite")

    if count == 0:
        print("[INFO] No matching spam leads found in SQLite.")
        conn.close()
        return 0

    print("\nMatching Leads:")
    print("-" * 65)
    for row in rows[:20]:
        print(f"ID: {row[0]} | Name: {row[1]} {row[2]} | Email: {row[3]} | Created: {row[4]}")
    if count > 20:
        print(f"... and {count - 20} more.")
    print("-" * 65)

    if dry_run:
        print(f"\n[DRY RUN] Would delete {count} lead(s). No changes made.")
        conn.close()
        return count

    lead_ids = [r[0] for r in rows]
    placeholders = ",".join(["?"] * len(lead_ids))

    cur.execute(f"DELETE FROM crm_leadnote WHERE lead_id IN ({placeholders})", lead_ids)
    cur.execute(f"DELETE FROM crm_scheduledemail WHERE to_lead_id IN ({placeholders})", lead_ids)
    cur.execute(f"DELETE FROM crm_lead WHERE id IN ({placeholders})", lead_ids)
    conn.commit()
    conn.close()

    print(f"\n[SUCCESS] Deleted {count} lead(s) and associated records from SQLite.")
    return count


def main():
    parser = argparse.ArgumentParser(description="Delete spam leads by first name.")
    parser.add_argument(
        "--name",
        type=str,
        default="Michaelvieks",
        help="First name of spam leads to delete (default: Michaelvieks)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview matching leads without deleting them.",
    )
    parser.add_argument(
        "--sqlite",
        action="store_true",
        help="Force direct SQLite database deletion.",
    )

    args = parser.parse_args()

    if args.sqlite:
        delete_via_direct_sqlite(target_name=args.name, dry_run=args.dry_run)
        return

    try:
        django.setup()
        delete_via_django_orm(target_name=args.name, dry_run=args.dry_run)
    except Exception as exc:
        print(f"[NOTICE] Django DB connection error ({exc}).")
        print("[INFO] Falling back to direct SQLite database...")
        delete_via_direct_sqlite(target_name=args.name, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
