from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Account, Author, Category, Publisher, Book, Borrow
from datetime import timedelta
from django.urls import path
from django.http import JsonResponse
from django.core.cache import cache


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("account_name", "account_id", "email", "username", "phone", "status", "role")
    search_fields = ("account_name", "username", "email", "phone", "account_id")
    ordering = ("account_name",)

    fieldsets = (
        (None, {
            "fields": (
                "account_id", "account_name", "email", "username", "password", "phone", "status", "role",
            )
        }),
    )

    def account_id_display(self, obj):
        return obj.pk if obj and obj.pk else "Sẽ được tạo sau khi lưu"
    account_id_display.short_description = "Account ID"

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
    readonly_fields = ("public_url_display",)

    fieldsets = (
        (None, {
            'fields': (
                'book_name', 'author', 'categories', 'publisher',
                'publishYear', 'price', 'quantity', 'available',
            )
        }),
        ('Nội dung', {
            'fields': ('description', 'image')
        }),
        ('Liên kết công khai', {
            'fields': ('public_url_display',)
        }),
    )

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

    def public_url_display(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return "Chưa có URL vì đối tượng chưa được tạo."
        try:
            url = obj.get_absolute_url()
        except Exception:
            url = f"/books/{obj.pk}/"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    public_url_display.short_description = "Public URL"


BORROW_VERSION_KEY = "borrows_version"

def get_borrows_version():
    v = cache.get(BORROW_VERSION_KEY)
    if v is None:
        cache.set(BORROW_VERSION_KEY, 1)
        v = 1
    return int(v)

def bump_borrows_version():
    if cache.get(BORROW_VERSION_KEY) is None:
        cache.set(BORROW_VERSION_KEY, 1)
    else:
        try:
            cache.incr(BORROW_VERSION_KEY)
        except ValueError:
            # một số backend không có incr
            cache.set(BORROW_VERSION_KEY, get_borrows_version() + 1)

@admin.register(Borrow)
class BorrowAdmin(admin.ModelAdmin):
    change_list_template = "partials/change_list.html"
    list_display = ("user_display", "user_id_display", "book", "borrow_date", "due_date", "status_display")
    list_filter = ("status",)
    search_fields = ("user__account_name", "book__book_name")
    actions = ["approve_borrow", "approve_return"]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["initial_version"] = get_borrows_version()
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("poll/", self.admin_site.admin_view(self.poll_view), name="library_borrow_poll"),
        ]
        return custom + urls

    def poll_view(self, request):
        # GET /admin/library/borrow/poll/
        return JsonResponse({"version": get_borrows_version(), "now": timezone.now().isoformat()})

    @admin.action(description="Duyệt yêu cầu mượn")
    def approve_borrow(self, request, queryset):
        approved = 0
        for borrow in queryset.select_related('book').filter(status='pending'):
            # kiểm tra tồn kho
            if not borrow.book or borrow.book.available <= 0:
                continue
            # cập nhật trạng thái và ngày mượn, hạn trả
            borrow.status = 'borrowed'
            borrow.borrow_date = timezone.now().date()
            borrow.due_date = borrow.borrow_date + timedelta(days=14)
            # trừ available
            borrow.book.available -= 1
            borrow.book.save()
            borrow.save()
            approved += 1
        if approved:
            bump_borrows_version()
        self.message_user(request, f"Đã chấp nhận {approved} yêu cầu mượn.")

    @admin.action(description="Xác nhận trả")
    def approve_return(self, request, queryset):
        processed = 0
        for borrow in queryset.select_related('book').filter(status__in=['await_return', 'borrowed']):
            # cộng lại tồn kho
            if borrow.book:
                borrow.book.available += 1
                borrow.book.save()
            # chuyển sang đã trả, giữ lịch sử
            borrow.status = 'returned'
            borrow.return_date = timezone.now().date()
            # nếu cần: borrow.calculate_fine()
            borrow.save()
            processed += 1
        if processed:
            bump_borrows_version()
        self.message_user(request, "Xác nhận trả thành công.")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        bump_borrows_version()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        bump_borrows_version()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        bump_borrows_version()

    def user_display(self, obj):
        return getattr(obj.user, "account_name", obj.user)
    user_display.short_description = "User"

    def user_id_display(self, obj):
        return getattr(obj.user, "account_id", None)
    user_id_display.short_description = "Account ID"
    user_id_display.admin_order_field = "user__account_id"

    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = "Trạng thái"