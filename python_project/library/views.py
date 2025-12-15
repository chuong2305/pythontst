from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from datetime import date
from .models import Book, Author, Category, Publisher, Account, Borrow
from django.http import HttpResponse,HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import authenticate, login
from functools import wraps

def _get_current_account(request):
    acc_id = request.session.get('account_id')
    if not acc_id:
        return None
    return Account.objects.filter(account_id=acc_id).first()

def session_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get('account_id'):
            messages.error(request, "Bạn cần đăng nhập.")
            return redirect('login_view')
        return view_func(request, *args, **kwargs)
    return _wrapped

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

@session_login_required
def user_borrowed(request):
    account = _get_current_account(request)
    if not account:
        return redirect('login_view')
    # Tab “Đã mượn”: pending + borrowed
    borrows_active = (Borrow.objects
                      .select_related('book')
                      .filter(user=account, status__in=['pending','borrowed'])
                      .order_by('-borrow_date'))

    active_items = []
    for b in borrows_active:
        days_left = None
        if b.status == 'borrowed' and b.due_date:
            days_left = (b.due_date - date.today()).days
        active_items.append({'borrow': b, 'days_left': days_left})

    borrows_returned = (Borrow.objects
     .select_related('book')
     .filter(user=account, status__in=['await_return', 'returned'])
     .order_by('-return_date', '-borrow_date'))
    returned_items = [{'borrow': b} for b in borrows_returned]

    current_borrowed_count = Borrow.objects.filter(user=account, status='borrowed').count()
    limit = 5

    return render(request, 'user-borrowed.html', {
        'items': active_items,
        'returned_items': returned_items,
        'current_borrowed_count': current_borrowed_count,
        'limit': limit,
        'is_empty_active': len(active_items) == 0,
        'is_empty_returned': len(returned_items) == 0,
    })
def borrowed_history(request):
    return render(request, 'borrowed-history.html')

def library_rule(request):
    return render(request, 'library-rule.html')

def library_card(request):
    return render(request, 'library_card.html')

def notify(request):
    return render(request, 'notify.html')

@require_http_methods(["GET", "POST"])
def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        account = Account.objects.filter(username=username, password=password, status='active').first()
        if account:
            request.session['account_id'] = account.account_id  # Lưu ai đang đăng nhập
            return redirect('home_page_user')
        return render(request, 'login.html', {'error': 'Tên đăng nhập hoặc mật khẩu không chính xác'})
    return render(request, 'login.html')

def user_books_view(request):
    # Lấy tham số từ form GET
    keyword = request.GET.get("keyword", "").strip()
    selected_author = request.GET.get("author", "")
    selected_category = request.GET.get("category", "")
    selected_publisher = request.GET.get("publisher", "")
    selected_date = request.GET.get("date_add", "")  # format yyyy-mm-dd từ input type="date"
    selected_status = request.GET.get("status", "")  # "available" | "borrowed" | ""

    # Base queryset
    books = (
        Book.objects
        .select_related("author", "publisher")
        .prefetch_related("categories")
        .all()
        .order_by("book_name")
    )

    # Từ khoá (tên sách, tên tác giả, tên NXB)
    if keyword:
        books = books.filter(
            Q(book_name__icontains=keyword) |
            Q(author__author_name__icontains=keyword) |
            Q(publisher__publish_name__icontains=keyword)
        )

    # Lọc theo thể loại (ManyToMany)
    if selected_category:
        books = books.filter(categories__category_id=selected_category)

    # Lọc theo tác giả
    if selected_author:
        books = books.filter(author__author_id=selected_author)

    # Lọc theo NXB
    if selected_publisher:
        books = books.filter(publisher__publish_id=selected_publisher)

    # Lọc theo ngày nhập
    if selected_date:
        books = books.filter(dateAdd=selected_date)

    # Lọc theo trạng thái
    if selected_status == "available":
        books = books.filter(available__gt=0)
    elif selected_status == "borrowed":
        books = books.filter(available=0)

    # Xóa trùng do join M2M khi lọc categories
    books = books.distinct()

    # Dữ liệu cho dropdown
    authors = Author.objects.all().order_by("author_name")
    categories = Category.objects.all().order_by("category_name")
    publishers = Publisher.objects.all().order_by("publish_name")

    return render(request, "user-books-author.html", {
        "books": books,
        "authors": authors,
        "categories": categories,
        "publishers": publishers,
        "keyword": keyword,
        "selected_author": selected_author,
        "selected_category": selected_category,
        "selected_publisher": selected_publisher,
        "selected_status": selected_status,
        "selected_date": selected_date,
    })

@session_login_required
@require_POST
def request_borrow(request, book_id):
    account = _get_current_account(request)
    if not account:
        messages.error(request, "Bạn cần đăng nhập.")
        return redirect('login_view')

    book = get_object_or_404(Book, pk=book_id)

    # Kiểm tra giới hạn 5 (bao gồm pending)
    current_borrowed = Borrow.objects.filter(user=account, status='borrowed').count()
    pending_count = Borrow.objects.filter(user=account, status='pending').count()
    if current_borrowed + pending_count >= 5:
        messages.warning(request, "Bạn đã đạt giới hạn 5 cuốn (bao gồm chờ duyệt).")
        return redirect('user_books_author')

    # Tạo bản ghi pending
    Borrow.objects.create(user=account, book=book, status='pending')
    messages.success(request, f"Đã gửi yêu cầu mượn '{book.book_name}'. Vui lòng chờ admin duyệt.")
    return redirect('user_books_author')


def calculate_days_left(borrow_instance):
    """Hàm phụ trợ tính số ngày còn lại"""
    if borrow_instance.due_date and borrow_instance.status == 'borrowed':
        delta = borrow_instance.due_date - timezone.now().date()
        return delta.days
    return None


@session_login_required
@require_POST
def confirm_return(request, borrow_id):
    # Xác thực session và lấy account hiện tại
    account = _get_current_account(request)
    if not account:
        messages.error(request, "Bạn cần đăng nhập.")
        return redirect('login_view')

    # Lấy bản ghi mượn (đảm bảo thuộc về account hiện tại)
    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account)

    # Cập nhật trạng thái và ngày trả yêu cầu
    b.status = 'await_return'
    b.return_date = timezone.now().date()
    b.save()
    messages.success(request, f"Đã gửi yêu cầu trả '{b.book.book_name}'.")

    # Debug: ghi lại header HTMX (nếu cần)
    print("HTMX Header:", request.headers.get('HX-Request'))

    # Nếu request từ HTMX, trả về partial fragment để HTMX swap
    if request.headers.get('HX-Request'):
        item_context = {
            'borrow': b,
            'days_left': None
        }
        return render(request, 'partials/borrow_card.html', {'item': item_context})

    # Nếu không phải HTMX, redirect về trang quản lý
    return HttpResponseRedirect(reverse('user_borrowed') + '?tab=returned')

@session_login_required
@require_POST
def cancel_pending_borrow(request, borrow_id):
    account = _get_current_account(request)
    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account, status='pending')
    b.delete()
    messages.success(request, "Đã hủy yêu cầu mượn.")
    if request.headers.get('HX-Request'):
        return HttpResponse("")
    return redirect('user_borrowed')

@session_login_required
@require_POST
def cancel_return_request(request, borrow_id):
    account = _get_current_account(request)
    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account, status='await_return')
    
    if not b:
        messages.warning(request, "Không thể hủy: yêu cầu trả không tồn tại hoặc đã được xử lý.")
        return redirect('user_borrowed')

    b.status = 'borrowed'
    # b.return_date = None  # nếu muốn xoá ngày yêu cầu trả
    b.save()
    messages.success(request, "Đã hủy yêu cầu trả.")
    if request.headers.get('HX-Request'):
        # Tính lại ngày còn lại vì trạng thái quay về 'borrowed'
        days_left = calculate_days_left(b)
        item_context = {
            'borrow': b,
            'days_left': days_left
        }
        return render(request, 'partials/borrow_card.html', {'item': item_context})
    return HttpResponseRedirect(reverse('user_borrowed') + '?tab=return')

@session_login_required
@require_POST
def delete_returned_borrow(request, borrow_id):
    account = _get_current_account(request)
    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account, status='returned')
    b.delete()
    messages.success(request, "Đã xóa lịch sử đã trả.")
    if request.headers.get('HX-Request'):
        # Trả về rỗng để xóa card khỏi danh sách
        return HttpResponse("")
    return HttpResponseRedirect(reverse('user_borrowed') + '?tab=returned')
# ... các import cũ ...

# View tìm sách cho Admin (HTMX)
def search_book_admin(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return HttpResponse("")

    # Logic tìm kiếm an toàn hơn
    # Nếu q là số thì tìm theo ID hoặc Tên
    if q.isdigit():
        books = Book.objects.filter(
            Q(pk=q) | Q(book_name__icontains=q)
        )[:10]
    else:
        # Nếu q là chữ thì chỉ tìm theo Tên (để tránh lỗi tìm chữ trong cột ID số)
        books = Book.objects.filter(
            book_name__icontains=q
        )[:10]

    # NOTE: the actual partial file in templates uses a hyphen in its name
    # (partials/admin_search-result.html). Use that exact filename so Django
    # can find the template when HTMX requests the fragment.
    return render(request, 'partials/admin_search-result.html', {'books': books})


def get_pending_requests(request):
    # Lấy các bản ghi có status = 'pending'
    pending = Borrow.objects.filter(status='pending').select_related('user', 'book').order_by('-borrow_date')

    return render(request, 'partials/admin_pending_list.html', {
        'pending_requests': pending,
        'pending_count': pending.count()
    })