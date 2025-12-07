from django.contrib import admin
from .models import Book, Author, Borrow, Category, Publisher, Account


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("account_name", "email", "username", "phone", "status", "role")
    search_fields = ("account_name", "username", "email")


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("author_name",)
    search_fields = ("author_name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name",)
    search_fields = ("category_name",)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ("publish_name",)
    search_fields = ("publish_name",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "book_name",
        "get_author",
        "get_categories",
        "get_publisher",
        "publishYear",
        "dateAdd",
    )
    list_filter = ("categories", "author", "publisher", "publishYear")
    search_fields = (
        "book_name",
        "author__author_name",
        "publisher__publish_name",
        "categories__category_name",
    )
    filter_horizontal = ("categories",)
    ordering = ("book_name",)

    def get_author(self, obj):
        return obj.author.author_name
    get_author.short_description = "Author"
    get_author.admin_order_field = "author__author_name"

    def get_categories(self, obj):
        return ", ".join([c.category_name for c in obj.categories.all()])
    get_categories.short_description = "Categories"

    def get_publisher(self, obj):
        return obj.publisher.publish_name
    get_publisher.short_description = "Publisher"


@admin.register(Borrow)
class BorrowAdmin(admin.ModelAdmin):
    list_display = ("user", "book", "borrow_date", "status")
    list_filter = ("status",)
    search_fields = ("user__account_name", "book__book_name")