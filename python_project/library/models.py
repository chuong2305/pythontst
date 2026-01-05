from django.core.exceptions import ValidationError
from django.db import models
from datetime import timedelta, date
from django.urls import reverse
from django.utils import timezone


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


class Book(models.Model):
    book_id = models.AutoField(primary_key=True)
    book_name = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    categories = models.ManyToManyField(Category, blank=True, related_name='books')
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    publishYear = models.PositiveIntegerField(null=True, blank=True)
    dateAdd = models.DateField(auto_now_add=True)
    quantity = models.PositiveIntegerField(default=5)
    available = models.PositiveIntegerField(default=5)
    price = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='books/', blank=True, null=True)

    def __str__(self):
        return self.book_name

    def reserved_count(self):
        return Borrow.objects.filter(book=self, status='reserved').count()

    def get_absolute_url(self):
        return reverse('book_detail', kwargs={'pk': self.pk})


class Borrow(models.Model):
    borrow_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    is_notified = models.BooleanField(default=False)
    borrow_date = models.DateField(default=date.today)
    due_date = models.DateField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)

    DAMAGE_CHOICES = (
        ('none', 'Không hư hại'),
        ('light', 'Hư nhẹ (20%)'),
        ('heavy', 'Hư nặng (50%)'),
        ('lost', 'Mất sách (100%)'),
    )
    damage_status = models.CharField(max_length=10, choices=DAMAGE_CHOICES, default='none')
    fine = models.PositiveIntegerField(default=0)

    STATUS_CHOICES = (
        ('reserved', 'Đã đặt trước'),
        ('borrowed', 'Đang mượn'),
        ('returned', 'Đã trả'),
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='reserved')

    @property
    def days_until_due(self):
        if self.due_date and self.status == 'borrowed':
            return (self.due_date - timezone.now().date()).days
        return None

    def calculate_fine(self):
        total_fine = 0

        if self.status == 'returned' and self.due_date and self.return_date:
            overdue_days = (self.return_date - self.due_date).days
            if overdue_days > 0:
                total_fine += overdue_days * 1000

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

        if old_status == 'borrowed' and self.status == 'returned':
            self.book.available += 1
            self.book.save(update_fields=['available'])

        if self.status == 'returned':
            if not self.return_date:
                self.return_date = timezone.now().date()
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