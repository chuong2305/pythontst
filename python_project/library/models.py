from django.db import models

class Account(models.Model):
    account_id = models.AutoField(primary_key=True)
    account_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    phone = models.CharField(max_length=20)
    
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
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
    # Thay FK category bằng ManyToMany để 1 sách có nhiều thể loại
    categories = models.ManyToManyField(Category, blank=True, related_name='books')
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    publishYear = models.PositiveIntegerField(null=True, blank=True)
    dateAdd = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.book_name

class Borrow(models.Model):
    borrow_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(Account, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    borrow_date = models.DateField(auto_now_add=True)

    STATUS_CHOICES = (
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.user.account_name} - {self.book.book_name}"