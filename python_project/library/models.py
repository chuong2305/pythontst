from django.db import models
from datetime import timedelta, date
from django.urls import reverse

# -------------------------
# ACCOUNT
# -------------------------
class Account(models.Model):
    id = models.AutoField(primary_key=True)
    account_id = models.CharField(max_length=64, unique=True)
    account_name = models.CharField(max_length=100)
    email = models.EmailField()
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=128)
    phone = models.CharField(max_length=20)
    
    STATUS_CHOICES = (
        ('active', 'Kích hoạt'),
        ('inactive', 'Chưa kích hoạt'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('User', 'User'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return self.account_name


# -------------------------
# AUTHOR – CATEGORY – PUBLISHER
# -------------------------
class Author(models.Model):
    author_id = models.AutoField(primary_key=True)
    author_name = models.CharField(max_length=100)

    def __str__(self):
        return self.author_name


class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.category_name


class Publisher(models.Model):
    publish_id = models.AutoField(primary_key=True)
    publish_name = models.CharField(max_length=200, unique=True)

    def __str__(self):
        return self.publish_name


# -------------------------
# BOOK
# -------------------------
class Book(models.Model):
    book_id = models.AutoField(primary_key=True)
    book_name = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    categories = models.ManyToManyField(Category, blank=True, related_name='books')
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    publishYear = models.PositiveIntegerField(null=True, blank=True)
    dateAdd = models.DateField(auto_now_add=True)

    # Số lượng nhập và số còn lại
    quantity = models.PositiveIntegerField(default=5)
    available = models.PositiveIntegerField(default=5)

    # Giá sách để tính phạt theo % khi trả
    price = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)  # mô tả dài, có thể để trống
    image = models.ImageField(upload_to='books/', blank=True, null=True)

    def __str__(self):
        return self.book_name
    
    def get_absolute_url(self):
        return reverse('book_detail', kwargs={'pk': self.pk})

# -------------------------
# BORROW
# -------------------------
class Borrow(models.Model):
    borrow_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    borrow_date = models.DateField(auto_now_add=True)
    due_date = models.DateField(null=True, blank=True)

    # Giới hạn ngày trả (mặc định 14 ngày)
    def default_due_date():
     return date.today() + timedelta(days=14)

    # Ngày trả
    return_date = models.DateField(null=True, blank=True)

    # Mức độ hư hại khi trả
    DAMAGE_CHOICES = (
        ('none', 'Không hư hại'),
        ('light', 'Hư nhẹ (20%)'),
        ('heavy', 'Hư nặng (50%)'),
        ('lost', 'Mất sách (100%)'),
    )
    damage_status = models.CharField(max_length=10, choices=DAMAGE_CHOICES, default='none')

    # Tổng tiền phạt
    fine = models.PositiveIntegerField(default=0)

    STATUS_CHOICES = (
        ('pending', 'Chờ duyệt'),
        ('borrowed', 'Đang mượn'),
        ('await_return', 'Chờ xác nhận trả'),
        ('returned', 'Đã trả'),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='pending')

    # -------------------------
    # Tính tiền phạt đầy đủ
    # -------------------------
    def calculate_fine(self):
        total_fine = 0

        # --- 1. Phạt trễ hạn ---
        if self.return_date and self.return_date > self.due_date:
            late_days = (self.return_date - self.due_date).days
            total_fine += late_days * 3000   # 3000đ/ngày

        # --- 2. Phạt hư hại ---
        price = self.book.price
        if self.damage_status == "light":
            total_fine += int(price * 0.2)
        elif self.damage_status == "heavy":
            total_fine += int(price * 0.5)
        elif self.damage_status == "lost":
            total_fine += int(price)

        self.fine = total_fine
        return total_fine

    def __str__(self):
        return f"{self.user.account_name} - {self.book.book_name}"
