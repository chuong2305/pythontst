from django.core.exceptions import ValidationError
from django.db import models
from datetime import timedelta, date
from django.urls import reverse
from django.utils import timezone

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

    def reserved_count(self):
        return Borrow.objects.filter(
            book=self,
            status='reserved'
        ).count()

    def get_absolute_url(self):
        return reverse('book_detail', kwargs={'pk': self.pk})

# -------------------------
# BORROW
# -------------------------
class Borrow(models.Model):
    borrow_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)

    # Thêm trường này để kiểm tra xem thông báo đã được hiển thị/đọc chưa
    is_notified = models.BooleanField(default=False)

    borrow_date = models.DateField(default=date.today)
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
        ('reserved', 'Đã đặt trước'),
        ('borrowed', 'Đang mượn'),
        ('returned', 'Đã trả'),
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default='reserved'
    )

    def calculate_fine(self):
        total_fine = 0
        today = timezone.now().date()

        # =====================
        # PHẠT TRỄ HẠN
        # =====================
        if self.due_date:
            # Nếu đang mượn → so với hôm nay
            if self.status == 'borrowed':
                late_days = (today - self.due_date).days
            # Nếu đã trả → so với ngày trả
            elif self.status == 'returned' and self.return_date:
                late_days = (self.return_date - self.due_date).days
            else:
                late_days = 0

            if late_days > 0:
                total_fine += late_days * 3000

        # =====================
        # PHẠT HƯ HẠI
        # =====================
        price = self.book.price

        if self.damage_status == 'light':
            total_fine += int(price * 0.2)
        elif self.damage_status == 'heavy':
            total_fine += int(price * 0.5)
        elif self.damage_status == 'lost':
            total_fine += int(price)

        return total_fine

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None

        if not is_new:
            old_status = Borrow.objects.get(pk=self.pk).status

        if (
                (is_new and self.status == 'borrowed') or
                (old_status == 'reserved' and self.status == 'borrowed')
        ):
            reserved_count = Borrow.objects.filter(
                book=self.book,
                status='reserved'
            ).exclude(pk=self.pk).count()

            if self.book.available <= reserved_count:
                raise ValidationError(
                    "Hiện đã có người dùng khác đặt trước."
                )

        super().save(*args, **kwargs)

        #  Trừ kho khi CHUYỂN SANG BORROWED
        if (
                (is_new and self.status == 'borrowed') or
                (old_status == 'reserved' and self.status == 'borrowed')
        ):
            self.book.available -= 1
            self.book.save(update_fields=['available'])

        # Trả sách
        if old_status == 'borrowed' and self.status == 'returned':
            self.book.available += 1
            self.book.save(update_fields=['available'])

        if self.status in ['borrowed', 'returned']:
            new_fine = self.calculate_fine()

            if self.fine != new_fine:
                Borrow.objects.filter(pk=self.pk).update(fine=new_fine)

    def __str__(self):
        return f"{self.user.account_name} - {self.book.book_name}"


# -------------------------
# ASSOCIATION RULES (for recommendations)
# -------------------------
class BookAssociationRule(models.Model):
    """
    Stores association rules mined from borrow history. 
    Example: If user borrows book A, recommend book B
    """
    rule_id = models.AutoField(primary_key=True)
    
    # Antecedent (if user borrows this book...)
    antecedent_book = models.ForeignKey(
        Book, 
        on_delete=models.CASCADE, 
        related_name='rules_as_antecedent'
    )
    
    # Consequent (... then recommend this book)
    consequent_book = models.ForeignKey(
        Book, 
        on_delete=models.CASCADE, 
        related_name='rules_as_consequent'
    )
    
    # Rule metrics
    support = models.FloatField(default=0)      # How often both appear together
    confidence = models.FloatField(default=0)   # P(consequent | antecedent)
    lift = models.FloatField(default=0)         # How much more likely
    
    # Timestamp for when the rule was generated
    created_at = models. DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('antecedent_book', 'consequent_book')
        ordering = ['-lift', '-confidence']
    
    def __str__(self):
        return f"{self.antecedent_book.book_name} → {self.consequent_book. book_name} (lift: {self.lift:.2f})"