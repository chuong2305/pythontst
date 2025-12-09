from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from .models import Book, Author, Category, Publisher

def home_page_user(request):
    return render(request, 'home-page-user.html')

def login_view(request):
    return render(request, 'login.html')

def welcome_view(request):
    return render(request, 'welcome.html')

# KHÔNG render trống nữa; nếu vẫn muốn giữ tên này:
def user_books_author(request):
    # gọi lại view có dữ liệu
    return user_books_view(request)

def user_books_type(request):
    return render(request, 'user-books-type.html')

def user_borrowed(request):
    return render(request, 'user-borrowed.html')

def library_rule(request):
    return render(request, 'library-rule.html')

def library_card(request):
    return render(request, 'library_card.html')

def notify(request):
    return render(request, 'notify.html')

@require_http_methods(["GET", "POST"])
def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        if username == 'admin' and password == '1':
            # đổi 'home' thành route có thật nếu cần
            return redirect('welcome_view')
        elif username == "dangpham" and password == '123':
            return redirect('home_page_user')
        else:
            return render(request, 'login.html', {'error': 'Tên đăng nhập hoặc mật khẩu không chính xác'})
    return render(request, 'login.html')

def user_books_view(request):
    # Hiển thị toàn bộ sách (chưa xử lý bộ lọc)
    books = (
        Book.objects
        .select_related("author", "publisher")
        .prefetch_related("categories")
        .all()
        .order_by("book_name")
    )

    authors = Author.objects.all().order_by("author_name")
    categories = Category.objects.all().order_by("category_name")
    publishers = Publisher.objects.all().order_by("publish_name")

    return render(request, "user-books-author.html", {
        "books": books,
        "authors": authors,
        "categories": categories,
        "publishers": publishers,
        "keyword": "",
        "selected_author": "",
        "selected_category": "",
        "selected_publisher": "",
        "selected_status": "",
        "selected_date": "",
    })