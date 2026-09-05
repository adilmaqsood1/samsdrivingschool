from django.core.management.base import BaseCommand
from crm.models import Lead, LeadNote, ScheduledEmail


class Command(BaseCommand):
    help = "Delete spam leads where first name matches Michaelvieks or a given target name."

    def add_arguments(self, parser):
        parser.add_argument(
            "--name",
            type=str,
            default="Michaelvieks",
            help="First name of spam leads to delete (default: Michaelvieks)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview leads that would be deleted without making changes.",
        )

    def handle(self, *args, **options):
        target_name = options["name"]
        dry_run = options["dry_run"]

        spam_leads = Lead.objects.filter(first_name__iexact=target_name)
        count = spam_leads.count()

        if count == 0:
            spam_leads = Lead.objects.filter(first_name__icontains=target_name)
            count = spam_leads.count()

        self.stdout.write(f"Found {count} lead(s) matching first_name '{target_name}'.")

        if count == 0:
            return

        for lead in spam_leads[:20]:
            self.stdout.write(f" - ID: {lead.id}, Name: {lead.first_name} {lead.last_name}, Email: {lead.email}")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"[DRY RUN] Would delete {count} leads."))
            return

        lead_ids = list(spam_leads.values_list("id", flat=True))
        notes_del = LeadNote.objects.filter(lead_id__in=lead_ids).delete()[0]
        emails_del = ScheduledEmail.objects.filter(to_lead_id__in=lead_ids).delete()[0]
        leads_del = spam_leads.delete()[0]

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {leads_del} lead(s), {notes_del} note(s), and {emails_del} email(s)."
            )
        )
