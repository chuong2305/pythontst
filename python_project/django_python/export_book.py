import csv
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_python.settings")

django.setup()

from library.models import Book

with open("books.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "title", "author", "categories", "publisher", "price", "description"])

    for book in Book.objects.all():
        categories = ", ".join([c.name for c in book.categories.all()]) if hasattr(book, "categories") else ""

        writer.writerow([
            book.id,
            book.name,
            book.author.name if book.author else "",
            categories,
            book.publisher.name if book.publisher else "",
            book.price,
            getattr(book, "description", "")
        ])

print("books.csv created successfully!")
