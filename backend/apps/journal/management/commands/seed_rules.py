from django.core.management.base import BaseCommand
from apps.journal.models import Rule

RULES = [
    'I woke up on time',
    'I checked the news, watchlist, and scanner for potential setups',
    'I game planned for 5 tickers, and then I narrowed down my list to my top three opportunities (these should be in writing and posted in the Discord)',
    'I took no more than 3 trade ideas for the day',
    'My trades that I took are from my morning game plan only (if the trade is an adhoc idea then the size must be smaller)',
    'Every trade had a defined playbook setup',
    'Every trade I confirmed my entry with order flow',
    'Every trade was taken from the proper location',
    'Every trade my stop loss was determined (on the chart) before entering',
    'Every trade my stop loss was correctly placed and actually invalidates my trade thesis',
    'Every trade I took I sized my position properly',
    'Every trade I obeyed my max trade loss',
    'Every trade I obeyed my daily loss limit',
]

class Command(BaseCommand):
    help = 'Add your initial 13 rules to an empty rulebook.'

    def handle(self, *args, **kwargs):
        if Rule.objects.exists():
            self.stdout.write('Rulebook already exists; no changes made.')

            return

        Rule.objects.bulk_create([Rule(text=text, weight=1) for text in RULES])
        self.stdout.write(self.style.SUCCESS('Added your 13 trading rules.'))
