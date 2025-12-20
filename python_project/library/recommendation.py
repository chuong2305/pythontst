import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend. preprocessing import TransactionEncoder
from django.db import transaction
from django.db.models import Q

from library.models import Borrow, Book, BookAssociationRule, Account


class RecommendationService:
    def __init__(self, min_support=0.01, min_confidence=0.1, min_lift=1.0):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
    
    def _get_monthly_baskets(self):
        borrows = Borrow.objects.filter(
            status__in=['borrowed', 'returned', 'await_return']
        ).select_related('user', 'book').order_by('user', 'borrow_date')

        baskets = defaultdict(set)
        
        for borrow in borrows:
            year_month = borrow.borrow_date.strftime('%Y-%m')
            basket_key = f"{borrow.user.id}_{year_month}"
            baskets[basket_key].add(borrow.book.book_id)

        transactions = [
            list(books) for books in baskets.values() 
            if len(books) >= 2
        ]
        
        return transactions
    
    def _create_transaction_matrix(self, transactions):
        if not transactions:
            return None
            
        te = TransactionEncoder()
        te_array = te.fit_transform(transactions)
        df = pd.DataFrame(te_array, columns=te.columns_)
        return df
    
    def mine_association_rules(self):
        transactions = self._get_monthly_baskets()
        print(f"Found {len(transactions)} valid baskets")
        
        if len(transactions) < 5:
            print("Go get more database record")
            return 0

        df = self._create_transaction_matrix(transactions)
        if df is None: 
            return 0
        
        print(f"   Transaction matrix shape: {df.shape}")

        try:
            frequent_itemsets = apriori(
                df, 
                min_support=self.min_support, 
                use_colnames=True
            )
            
            if frequent_itemsets.empty:
                print("No frequent itemsets found.")
                return 0
            
            print(f"Found {len(frequent_itemsets)} frequent itemsets")

            rules = association_rules(
                frequent_itemsets, 
                metric="lift", 
                min_threshold=self.min_lift
            )

            rules = rules[rules['confidence'] >= self.min_confidence]
            
            print(f"Generated {len(rules)} association rules")
            
        except Exception as e:
            print(f"Error during mining: {e}")
            return 0
        
        return self._save_rules_to_db(rules)
    
    def _save_rules_to_db(self, rules_df):
        BookAssociationRule.objects.all().delete()
        
        rules_to_create = []
        
        for _, row in rules_df.iterrows():
            antecedents = list(row['antecedents'])
            consequents = list(row['consequents'])
            
            if len(antecedents) == 1 and len(consequents) == 1:
                ant_book_id = antecedents[0]
                cons_book_id = consequents[0]
                
                try:
                    rules_to_create.append(
                        BookAssociationRule(
                            antecedent_book_id=ant_book_id,
                            consequent_book_id=cons_book_id,
                            support=row['support'],
                            confidence=row['confidence'],
                            lift=row['lift']
                        )
                    )
                except Exception as e:
                    continue

        with transaction.atomic():
            BookAssociationRule.objects.bulk_create(
                rules_to_create, 
                ignore_conflicts=True
            )
        
        print(f"   ✅ Saved {len(rules_to_create)} rules to database")
        return len(rules_to_create)
    
    @staticmethod
    def get_recommendations_for_book(book_id, limit=5):
        rules = BookAssociationRule.objects.filter(
            antecedent_book_id=book_id
        ).select_related('consequent_book').order_by('-lift', '-confidence')[:limit]
        
        recommended_books = [rule.consequent_book for rule in rules]
        return recommended_books
    
    @staticmethod
    def get_recommendations_for_user(account, limit=10):
        if not account: 
            return []

        borrowed_book_ids = set(
            Borrow.objects.filter(user=account)
            .values_list('book_id', flat=True)
        )
        
        if not borrowed_book_ids: 
            return []

        rules = BookAssociationRule.objects.filter(
            antecedent_book_id__in=borrowed_book_ids
        ).exclude(
            consequent_book_id__in=borrowed_book_ids
        ).select_related(
            'consequent_book',
            'consequent_book__author',
            'consequent_book__publisher'
        ).prefetch_related(
            'consequent_book__categories'
        ).order_by('-lift', '-confidence')

        book_scores = defaultdict(lambda: {'book':  None, 'score': 0, 'count': 0})
        
        for rule in rules: 
            book_id = rule.consequent_book_id
            book_scores[book_id]['book'] = rule.consequent_book
            book_scores[book_id]['score'] += rule.lift * rule.confidence
            book_scores[book_id]['count'] += 1

        sorted_recommendations = sorted(
            book_scores.values(),
            key=lambda x: x['score'],
            reverse=True
        )[:limit]
        
        return [item['book'] for item in sorted_recommendations]
    
    @staticmethod
    def get_popular_books(limit=10):
        from django.db.models import Count
        
        popular_book_ids = (
            Borrow.objects
            .values('book_id')
            .annotate(borrow_count=Count('borrow_id'))
            .order_by('-borrow_count')[:limit]
        )
        
        book_ids = [item['book_id'] for item in popular_book_ids]
        books = Book.objects.filter(book_id__in=book_ids).select_related('author', 'publisher')

        book_dict = {book.book_id: book for book in books}
        return [book_dict[bid] for bid in book_ids if bid in book_dict]