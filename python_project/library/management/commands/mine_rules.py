# yourapp/management/commands/mine_rules.py

from django.core.management.base import BaseCommand
from library.recommendation import RecommendationService


class Command(BaseCommand):
    help = 'Mine association rules from borrow history for book recommendations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--min-support',
            type=float,
            default=0.01,
            help='Minimum support threshold (default: 0.01)'
        )
        parser.add_argument(
            '--min-confidence',
            type=float,
            default=0.1,
            help='Minimum confidence threshold (default: 0.1)'
        )
        parser.add_argument(
            '--min-lift',
            type=float,
            default=1.0,
            help='Minimum lift threshold (default: 1.0)'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style. NOTICE('Starting rule mining...'))
        
        service = RecommendationService(
            min_support=options['min_support'],
            min_confidence=options['min_confidence'],
            min_lift=options['min_lift']
        )
        
        num_rules = service.mine_association_rules()
        
        if num_rules > 0:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully generated {num_rules} association rules!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('No rules generated. You may need more borrow data or lower thresholds.')
            )