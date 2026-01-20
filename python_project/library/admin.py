from django.contrib import admin
from django.contrib import messages
from django.contrib.admin import SimpleListFilter
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path
from django.http import JsonResponse
from django.core.cache import cache
from datetime import datetime, timedelta
from .models import get_max_borrow_days
from .models import Account, Author, Category, Publisher, Book, Borrow
from django.db.models import Q

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("account_name", "account_id", "email", "username", "phone", "status", "user_type")
    search_fields = ("account_name", "username", "email", "phone", "account_id")
    ordering = ("account_name",)
    fieldsets = (
        (None, {
            "fields": (
                "account_id", "account_name", "email", "username", "password", "phone", "status", "user_type",
            )
        }),
    )
    change_list_template = "partials/change_list.html"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["stats"] = [
            {"label": "Tổng người dùng", "value": Account.objects.count()},
            {"label": "Kích hoạt", "value": Account.objects.filter(status="active").count()},
            {"label": "Chưa kích hoạt", "value": Account.objects.filter(status="inactive").count()},
        ]
        return super().changelist_view(request, extra_context=extra_context)

    def account_id_display(self, obj):
        return obj.pk if obj and obj.pk else "Sẽ được tạo sau khi lưu"

    account_id_display.short_description = "ID"


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("author_name",)
    search_fields = ("author_name",)
    change_list_template = "partials/change_list.html"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        from .models import Author
        total_authors = Author.objects.count()
        authors_with_books = Author.objects.filter(book__isnull=False).distinct().count()
        authors_without_books = total_authors - authors_with_books
        extra_context["stats"] = [
            {"label": "Tổng tác giả", "value": total_authors},
            {"label": "Có sách", "value": authors_with_books},
            {"label": "Chưa có sách", "value": authors_without_books},
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name",)
    search_fields = ("category_name",)
    change_list_template = "partials/change_list.html"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        from .models import Category
        total_categories = Category.objects.count()
        categories_with_books = Category.objects.filter(books__isnull=False).distinct().count()
        categories_without_books = total_categories - categories_with_books
        extra_context["stats"] = [
            {"label": "Tổng thể loại", "value": total_categories},
            {"label": "Có sách", "value": categories_with_books},
            {"label": "Chưa có sách", "value": categories_without_books},
        ]
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ("publish_name",)
    search_fields = ("publish_name",)
    change_list_template = "partials/change_list.html"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        from .models import Publisher
        total_publishers = Publisher.objects.count()
        publishers_with_books = Publisher.objects.filter(book__isnull=False).distinct().count()
        publishers_without_books = total_publishers - publishers_with_books
        extra_context["stats"] = [
            {"label": "Tổng nhà xuất bản", "value": total_publishers},
            {"label": "Có sách", "value": publishers_with_books},
            {"label": "Chưa có sách", "value": publishers_without_books},
        ]
        return super().changelist_view(request, extra_context=extra_context)

class AddDateRangeFilter(SimpleListFilter):
    title = "Thời gian"
    parameter_name = "dateAdd"
    template = "admin/date_add_range_filter.html"

    def lookups(self, request, model_admin):
        return ()
    def has_output(self):
        return True
    def expected_parameters(self):
        return ["start_date", "end_date"]
    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset

        try:
            start, end = value.split("__")
            if start:
                queryset = queryset.filter(dateAdd__gte=start)
            if end:
                queryset = queryset.filter(dateAdd__lte=end)
        except ValueError:
            return queryset

        return queryset

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "book_name", "get_author", "get_categories", "get_publisher", "dateAdd",
    )
    list_filter = (AddDateRangeFilter,"categories", "author", "publisher", "publishYear")
    search_fields = ("book_name", "author__author_name", "publisher__publish_name", "categories__category_name",)
    filter_horizontal = ("categories",)
    ordering = ("book_name",)
    readonly_fields = ("public_url_display",)
    change_list_template = "partials/change_list.html"

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

    get_author.short_description = "Tác giả"
    get_author.admin_order_field = "author__author_name"

    def get_categories(self, obj):
        return ", ".join([c.category_name for c in obj.categories.all()])

    get_categories.short_description = "Thể loại"

    def get_publisher(self, obj):
        return obj.publisher.publish_name

    get_publisher.short_description = "Xuất bản"

    def public_url_display(self, obj):
        if not obj or not getattr(obj, 'pk', None):
            return "Chưa có URL vì đối tượng chưa được tạo."
        try:
            url = obj.get_absolute_url()
        except Exception:
            url = f"/books/{obj.pk}/"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)

    public_url_display.short_description = "Public URL"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        qs = self.get_queryset(request)

        # ---- APPLY DATE RANGE FILTER (dateAdd) ----
        date_value = request.GET.get("dateAdd", "")
        if date_value:
            try:
                start, end = date_value.split("__")
                if start:
                    qs = qs.filter(dateAdd__gte=start)
                if end:
                    qs = qs.filter(dateAdd__lte=end)
            except ValueError:
                pass

        # ---- APPLY OTHER LIST FILTERS ----
        if request.GET.get("categories"):
            qs = qs.filter(categories=request.GET.get("categories"))

        if request.GET.get("author"):
            qs = qs.filter(author=request.GET.get("author"))

        if request.GET.get("publisher"):
            qs = qs.filter(publisher=request.GET.get("publisher"))

        if request.GET.get("publishYear"):
            qs = qs.filter(publishYear=request.GET.get("publishYear"))

        # ---- STATS BASED ON FILTERED QS ----
        today = timezone.now().date()
        recent_days = today - timedelta(days=30)

        extra_context["stats"] = [
            {"label": "Tổng số sách", "value": qs.count()},
            {"label": "Sách đang có", "value": qs.filter(available__gt=0).count()},
            {"label": "Sách hết hàng", "value": qs.filter(available=0).count()},
            {"label": "Sách mới 30 ngày", "value": qs.filter(dateAdd__gte=recent_days).count()},
        ]

        return super().changelist_view(request, extra_context=extra_context)



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
            cache.set(BORROW_VERSION_KEY, get_borrows_version() + 1)

class BorrowDateRangeFilter(SimpleListFilter):
    title = "Thời gian"
    parameter_name = "borrow_date"
    template = "admin/date_borrow_range_filter.html"

    def lookups(self, request, model_admin):
        return ()
    def has_output(self):
        return True
    def expected_parameters(self):
        return ["start_date", "end_date"]
    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset

        try:
            start, end = value.split("__")
            if start:
                queryset = queryset.filter(borrow_date__gte=start)
            if end:
                queryset = queryset.filter(borrow_date__lte=end)
        except ValueError:
            return queryset

        return queryset


@admin.register(Borrow)
class BorrowAdmin(admin.ModelAdmin):
    change_list_template = "partials/change_list.html"
    list_display = ("user_display", "user_id_display", "book", "borrow_date", "due_date", "status_display",
                    "damage_status_view")
    list_filter = (BorrowDateRangeFilter,"status", "damage_status")
    search_fields = ("user__account_name", "book__book_name")

    actions = ["confirm_borrow", "cancel_reservation"]

    fieldsets = (
        ('Thông tin mượn', {
            'fields': ('user_display', 'user_type_display', 'book_display', 'book_categories', 'borrow_date', 'due_date', 'max_borrow_days_display')
        }),
        ('Cập nhật trạng thái & Chi tiết trả sách', {
            'fields': ('status', 'is_notified', 'return_date', 'damage_status', 'fine'),
            'description': 'Thay đổi trạng thái và nhập thông tin trả sách tại đây.'
        }),
    )

    readonly_fields = ('user_display', 'user_type_display', 'book_display', "fine", 'max_borrow_days_display', 'book', 'book_categories')
    def book_display(self, obj):
        return obj.book.book_name if obj.book else "-"

    book_display.short_description = "Tên sách"

    def user_type_display(self, obj):
        if not obj.user:
            return "-"
        return obj.user.get_user_type_display()

    user_type_display.short_description = "Phân quyền"

    def book_categories(self, obj):
        if not obj.book:
            return "-"
        return ", ".join(c.category_name for c in obj.book.categories.all())

    book_categories.short_description = "Thể loại"

    def max_borrow_days_display(self, obj):
        if not obj or not obj.user:
            return "-"
        return f"{obj.max_borrow_days} ngày"

    max_borrow_days_display.short_description = "Thời gian mượn tối đa"

    def damage_status_view(self, obj):
        if obj.status == 'returned':
            return obj.get_damage_status_display()
        return ""

    damage_status_view.short_description = "Hư hại"

    def save_model(self, request, obj, form, change):
        if not obj.borrow_date:
            obj.borrow_date = timezone.now().date()

        if obj.user and obj.book and obj.borrow_date and obj.due_date:
            max_days = get_max_borrow_days(obj.user, obj.book)
            max_due_date = obj.borrow_date + timedelta(days=max_days)

            if obj.due_date > max_due_date:
                request._borrow_invalid = True  # 🚩 GẮN CỜ
                form.add_error(
                    "due_date",
                    f"Ngày hết hạn mượn vượt quá {max_days} ngày theo quy định"
                )
                return

        super().save_model(request, obj, form, change)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        qs = self.get_queryset(request)
        
        # Manually apply the date range filter
        borrow_date_value = request.GET.get('borrow_date', '')
        if borrow_date_value: 
            try:
                start, end = borrow_date_value.split("__")
                if start: 
                    qs = qs.filter(borrow_date__gte=start)
                if end:
                    qs = qs.filter(borrow_date__lte=end)
            except ValueError:
                pass
        
        # Also apply status filter if present
        status_value = request.GET.get('status')
        if status_value: 
            qs = qs.filter(status=status_value)
        
        # Also apply damage_status filter if present
        damage_status_value = request.GET.get('damage_status')
        if damage_status_value: 
            qs = qs.filter(damage_status=damage_status_value)

        today = timezone.now().date()
        last_30_days = today - timedelta(days=30)

        extra_context["stats"] = [
            {"label": "Tổng lượt mượn", "value": qs.count()},
            {
                "label": "30 ngày gần đây",
                "value": qs.filter(borrow_date__gte=last_30_days).count(),
            },
            {"label": "Đang chờ duyệt", "value": qs.filter(status="reserved").count()},
            {"label": "Đang mượn", "value": qs.filter(status="borrowed").count()},
            {"label": "Đã trả", "value": qs.filter(status="returned").count()},
        ]

        extra_context["initial_version"] = get_borrows_version()
        return super().changelist_view(request, extra_context=extra_context)


    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("poll/", self.admin_site.admin_view(self.poll_view), name="library_borrow_poll"),
        ]
        return custom + urls

    def poll_view(self, request):
        return JsonResponse({"version": get_borrows_version(), "now": timezone.now().isoformat()})

    @admin.action(description="Xác nhận mượn sách (Duyệt)")
    def confirm_borrow(self, request, queryset):
        updated_count = 0
        for b in queryset.filter(status='reserved'):
            b.status = 'borrowed'
            b.borrow_date = timezone.now().date()
            b.due_date = b.borrow_date + timedelta(days=14)
            b.is_notified = False
            b.save()
            updated_count += 1
        self.message_user(request, f"Đã duyệt mượn {updated_count} sách.")
        bump_borrows_version()

    @admin.action(description="Hủy đặt trước (Từ chối)")
    def cancel_reservation(self, request, queryset):
        deleted_count, _ = queryset.filter(status='reserved').delete()
        self.message_user(request, f"Đã hủy {deleted_count} yêu cầu đặt trước.")
        bump_borrows_version()

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        bump_borrows_version()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        bump_borrows_version()

    def user_display(self, obj):
        return getattr(obj.user, "account_name", obj.user)

    user_display.short_description = "Tài khoản"

    def user_id_display(self, obj):
        return getattr(obj.user, "account_id", None)

    user_id_display.short_description = "ID"
    user_id_display.admin_order_field = "user__account_id"

    def status_display(self, obj):
        return obj.get_status_display()

    status_display.short_description = "Trạng thái"

    def message_user(self, request, message, level=messages.INFO, extra_tags='', fail_silently=False):
        if getattr(request, "_borrow_invalid", False) and level == messages.SUCCESS:
            messages.error(
                request,
                "Ngày hết hạn mượn vượt quá giới hạn quy định"
            )
            return

        super().message_user(request, message, level, extra_tags, fail_silently)





