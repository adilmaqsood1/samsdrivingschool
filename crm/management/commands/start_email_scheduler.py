from apscheduler.schedulers.blocking import BlockingScheduler
from django.core.management import BaseCommand, call_command
from django.utils import timezone


class Command(BaseCommand):
    help = "Run the email scheduler"

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=str(timezone.get_current_timezone()))
        scheduler.add_job(lambda: call_command("run_email_scheduler"), "interval", minutes=1, id="scheduled_emails")
        scheduler.start()
