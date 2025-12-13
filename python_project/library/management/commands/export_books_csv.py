import csv
from pathlib import Path
from django.core.management.base import BaseCommand
from library.models import Book

class Command(BaseCommand):
    help = "Export all books to a CSV file for analysis/TF-IDF."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default="books_export.csv",
            help="Output CSV path (default: books_export.csv in project root)",
        )
        parser.add_argument(
            "--bom",
            action="store_true",
            help="Write UTF-8 BOM for Excel compatibility (Windows).",
        )

    def handle(self, *args, **options):
        output = options["output"]
        bom = options["bom"]

        # Chọn encoding: utf-8-sig (có BOM) để mở bằng Excel đỡ lỗi font
        encoding = "utf-8-sig" if bom else "utf-8"

        # Bảo đảm thư mục đích tồn tại
        out_path = Path(output)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # Tối ưu truy vấn
        qs = (
            Book.objects
            .select_related("author", "publisher")
            .prefetch_related("categories")
            .all()
            .order_by("book_name")
        )

        with out_path.open("w", newline="", encoding=encoding) as f:
            writer = csv.writer(f)
            writer.writerow([
                "book_id",
                "book_name",
                "author_name",
                "categories",
                "publisher_name",
                "publishYear",
                "price",
                "quantity",
                "available",
                "dateAdd",
            ])

            count = 0
            for b in qs:
                cats = ", ".join(c.category_name for c in b.categories.all())
                writer.writerow([
                    b.book_id,
                    b.book_name,
                    b.author.author_name if b.author_id else "",
                    cats,
                    b.publisher.publish_name if b.publisher_id else "",
                    b.publishYear or "",
                    b.price or 0,
                    b.quantity or 0,
                    b.available or 0,
                    b.dateAdd.isoformat() if b.dateAdd else "",
                ])
                count += 1

        self.stdout.write(self.style.SUCCESS(f"Exported {count} books to {out_path.resolve()} (encoding={encoding})"))