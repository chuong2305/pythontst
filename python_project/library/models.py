from django.core.exceptions import ValidationError
from django.db import models
from datetime import timedelta, date
from django.urls import reverse
from django.utils import timezone


class UserType(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name



class Account(models.Model):
    id = models.AutoField(primary_key=True)
    account_id = models.CharField("Id tài khoản",max_length=64, unique=True)
    account_name = models.CharField("Tên tài khoản",max_length=100)
    email = models.EmailField()
    username = models.CharField("Tên đăng nhập",max_length=50)
    password = models.CharField("Mật khẩu",max_length=128)
    phone = models.CharField("Số điện thoại",max_length=20)

    class Meta:
        verbose_name = "Quản lý tài khoản"
        verbose_name_plural = "Quản lý tài khoản"

    STATUS_CHOICES = (
        ('active', 'Kích hoạt'),
        ('inactive', 'Chưa kích hoạt'),
    )
    status = models.CharField("Trạng thái",max_length=10, choices=STATUS_CHOICES)

    USER_TYPE_CHOICES = [
        ('student', 'Sinh viên'),
        ('lecturer', 'Giảng viên'),
        ('staff', 'Cán bộ/Học viên/Cao học'),
        ('admin', 'Quản trị viên'),
    ]

    user_type = models.CharField("Phân quyền", max_length=20,choices=USER_TYPE_CHOICES,default='student')

    def __str__(self):
        return self.account_name


class Author(models.Model):
    author_id = models.AutoField("Id Tác giả",primary_key=True)
    author_name = models.CharField("Tên tác giả",max_length=100)

    class Meta:
        verbose_name = "Danh sách tác giả"
        verbose_name_plural = "Danh sách tác giả"

    def __str__(self):
        return self.author_name


class Category(models.Model):
    category_id = models.AutoField("Id thể loại",primary_key=True)
    category_name = models.CharField("Tên thể loại",max_length=100, unique=True)

    class Meta:
        verbose_name = "Danh sách thể loại"
        verbose_name_plural = "Danh sách thể loại"

    def __str__(self):
        return self.category_name


class Publisher(models.Model):
    publish_id = models.AutoField("Id nhà xuất bản", primary_key=True)
    publish_name = models.CharField("Tên nhà xuất bản", max_length=200, unique=True)

    class Meta:
        verbose_name = "Danh sách nhà xuất bản"
        verbose_name_plural = "Danh sách nhà xuất bản"

    def __str__(self):
        return self.publish_name


class Book(models.Model):
    book_id = models.AutoField("Id sách",primary_key=True)
    book_name = models.CharField("Tên sách",max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    categories = models.ManyToManyField(Category, blank=True, related_name='books')
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    publishYear = models.PositiveIntegerField("Năm xuất bản", null=True, blank=True)
    dateAdd = models.DateField("Ngày thêm",auto_now_add=True)
    quantity = models.PositiveIntegerField("Tồn kho", default=5)
    available = models.PositiveIntegerField("Còn lại", default=5)
    price = models.PositiveIntegerField("Giá sách", default=0)
    description = models.TextField("Mô tả sách", blank=True)
    image = models.ImageField("Ảnh minh họa", upload_to='books/', blank=True, null=True)

    class Meta:
        verbose_name = "Quản lý sách"
        verbose_name_plural = "Quản lý sách"

    def __str__(self):
        return self.book_name

    def reserved_count(self):
        return Borrow.objects.filter(book=self, status='reserved').count()

    def get_absolute_url(self):
        return reverse('book_detail', kwargs={'pk': self.pk})


def get_book_type(book):
    categories = book.categories.values_list('category_name', flat=True)

    if any("Giáo trình" in c for c in categories):
        return 'textbook'
    if any("Tài liệu" in c for c in categories):
        return 'reference'
    return 'novel'

RULES = {
    'student': {'novel': 14,'reference': 21,'textbook': 30,},
    'staff': {'novel': 30, 'reference': 60, 'textbook': 90,},
    'lecturer': {'novel': 60, 'reference': 180, 'textbook': 365,}
}

def get_max_borrow_days(user, book):
    if not user or not book:
        return 14

    book_type = get_book_type(book)
    return RULES.get(user.user_type, {}).get(book_type, 14)



class Borrow(models.Model):
    borrow_id = models.AutoField("Id mượn", primary_key=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    is_notified = models.BooleanField("Nhận thông báo", default=False)
    borrow_date = models.DateField("Ngày mượn", default=date.today)
    due_date = models.DateField("Ngày hết hạn", null=True, blank=True)
    return_date = models.DateField("Ngày trả", null=True, blank=True)

    class Meta:
        verbose_name = "Quản lý mượn/trả"
        verbose_name_plural = "Quản lý mượn/trả"

    DAMAGE_CHOICES = (
        ('none', 'Không hư hại'),
        ('light', 'Hư nhẹ (20%)'),
        ('heavy', 'Hư nặng (50%)'),
        ('lost', 'Mất sách (100%)'),
    )
    damage_status = models.CharField("Trạng thái sách", max_length=10, choices=DAMAGE_CHOICES, default='none')
    fine = models.PositiveIntegerField("Tiền phạt", default=0)

    STATUS_CHOICES = (
        ('reserved', 'Đã đặt trước'),
        ('borrowed', 'Đang mượn'),
        ('returned', 'Đã trả'),
    )
    status = models.CharField("Trạng thái", max_length=16, choices=STATUS_CHOICES, default='reserved')

    max_borrow_days = models.PositiveIntegerField(
        "Thời gian mượn tối đa (ngày)",
        editable=False,
        null=True
    )

    @property
    def days_until_due(self):
        # Fix logic: Sử dụng date.today() để đồng nhất với borrow_date
        if self.due_date and self.status == 'borrowed':
            return (self.due_date - date.today()).days
        return None

    @property
    def max_borrow_days(self):
        return get_max_borrow_days(self.user, self.book)

    def calculate_max_days(self):
        user_type = self.user.user_type
        categories = self.book.categories.all()

        rule = (
            BorrowRule.objects
            .filter(user_type=user_type, category__in=categories)
            .order_by('-max_days')
            .first()
        )

        return rule.max_days if rule else 14  # fallback an toàn

    def calculate_fine(self):
        total_fine = 0

        # Logic tính quá hạn
        if self.status == 'returned' and self.due_date and self.return_date:
            overdue_days = (self.return_date - self.due_date).days
            if overdue_days > 0:
                total_fine += overdue_days * 3000

        # Logic tính hư hại
        price = self.book.price
        if self.damage_status == 'light':
            total_fine += int(price * 0.2)
        elif self.damage_status == 'heavy':
            total_fine += int(price * 0.5)
        elif self.damage_status == 'lost':
            total_fine += int(price)

        return total_fine

    from datetime import date

    def current_fine(self):
        if self.status == 'returned' or not self.due_date:
            return 0

        today = date.today()
        total = 0

        overdue_days = (today - self.due_date).days
        if overdue_days > 0:
            total += overdue_days * 3000

        return total

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None

        if not is_new:
            try:
                old_status = Borrow.objects.get(pk=self.pk).status
            except Borrow.DoesNotExist:
                pass

        # Đảm bảo due_date luôn được gán nếu đang mượn (Fix lỗi logic khi tạo từ view thường)
        if self.status == 'borrowed' and not self.due_date:
            self.due_date = (self.borrow_date or date.today()) + timedelta(days=14)

        # Logic cập nhật số lượng sách tồn kho khi duyệt mượn
        if ((is_new and self.status == 'borrowed') or
                (old_status == 'reserved' and self.status == 'borrowed')):
            reserved_count = Borrow.objects.filter(
                book=self.book, status='reserved'
            ).exclude(pk=self.pk).count()

            if self.book.available <= reserved_count:
                raise ValidationError("Hiện đã có người dùng khác đặt trước.")

        if ((is_new and self.status == 'borrowed') or
                (old_status == 'reserved' and self.status == 'borrowed')):
            self.book.available -= 1
            self.book.save(update_fields=['available'])

        # Logic cập nhật số lượng sách tồn kho khi trả
        if old_status == 'borrowed' and self.status == 'returned':
            self.book.available += 1
            self.book.save(update_fields=['available'])

        # Logic tính phạt khi trả sách
        if self.status == 'returned':
            if not self.return_date:
                self.return_date = date.today()
            self.fine = self.calculate_fine()
        else:
            self.fine = 0

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.account_name} - {self.book.book_name}"


class BookAssociationRule(models.Model):
    rule_id = models.AutoField(primary_key=True)
    antecedent_book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='rules_as_antecedent')
    consequent_book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='rules_as_consequent')
    support = models.FloatField(default=0)
    confidence = models.FloatField(default=0)
    lift = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('antecedent_book', 'consequent_book')
        ordering = ['-lift', '-confidence']

    def __str__(self):
        return f"{self.antecedent_book.book_name} -> {self.consequent_book.book_name}"

class BorrowRule(models.Model):
    user_type = models.ForeignKey(UserType, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    max_days = models.PositiveIntegerField("Thời gian mượn tối đa (ngày)")

    class Meta:
        unique_together = ("user_type", "category")

    def __str__(self):
        return f"{self.user_type} - {self.category}: {self.max_days} ngày"

