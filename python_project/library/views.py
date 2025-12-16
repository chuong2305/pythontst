from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from datetime import date
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from functools import wraps
from .models import Book, Author, Category, Publisher, Account, Borrow


# --- HELPER FUNCTIONS ---

def _get_current_account(request):
    acc_id = request.session.get('account_id')
    if not acc_id:
        return None
    return Account.objects.filter(account_id=acc_id).first()


def calculate_days_left(borrow_instance):
    """Hàm phụ trợ tính số ngày còn lại"""
    if borrow_instance.due_date and borrow_instance.status == 'borrowed':
        delta = borrow_instance.due_date - timezone.now().date()
        return delta.days
    return None


def session_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get('account_id'):
            messages.error(request, "Bạn cần đăng nhập.")
            return redirect('login_view')
        return view_func(request, *args, **kwargs)

    return _wrapped


# --- VIEW CƠ BẢN ---

def home_page_user(request):
    return render(request, 'home-page-user.html')


def login_view(request):
    return render(request, 'login.html')


def welcome_view(request):
    return render(request, 'welcome.html')


def user_books_author(request):
    return user_books_view(request)


def user_books_type(request):
    return render(request, 'user-books-type.html')


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
            request.session['account_id'] = account.account_id
            return redirect('home_page_user')
        return render(request, 'login.html', {'error': 'Tên đăng nhập hoặc mật khẩu không chính xác'})
    return render(request, 'login.html')


def user_books_view(request):
    keyword = request.GET.get("keyword", "").strip()
    selected_author = request.GET.get("author", "")
    selected_category = request.GET.get("category", "")
    selected_publisher = request.GET.get("publisher", "")
    selected_date = request.GET.get("date_add", "")
    selected_status = request.GET.get("status", "")

    books = (
        Book.objects
        .select_related("author", "publisher")
        .prefetch_related("categories")
        .all()
        .order_by("book_name")
    )

    if keyword:
        books = books.filter(
            Q(book_name__icontains=keyword) |
            Q(author__author_name__icontains=keyword) |
            Q(publisher__publish_name__icontains=keyword)
        )
    if selected_category:
        books = books.filter(categories__category_id=selected_category)
    if selected_author:
        books = books.filter(author__author_id=selected_author)
    if selected_publisher:
        books = books.filter(publisher__publish_id=selected_publisher)
    if selected_date:
        books = books.filter(dateAdd=selected_date)
    if selected_status == "available":
        books = books.filter(available__gt=0)
    elif selected_status == "borrowed":
        books = books.filter(available=0)

    books = books.distinct()

    return render(request, "user-books-author.html", {
        "books": books,
        "authors": Author.objects.all().order_by("author_name"),
        "categories": Category.objects.all().order_by("category_name"),
        "publishers": Publisher.objects.all().order_by("publish_name"),
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
    current_borrowed = Borrow.objects.filter(user=account, status='borrowed').count()
    pending_count = Borrow.objects.filter(user=account, status='pending').count()

    if current_borrowed + pending_count >= 5:
        messages.warning(request, "Bạn đã đạt giới hạn 5 cuốn (bao gồm chờ duyệt).")
        return redirect('user_books_author')

    Borrow.objects.create(user=account, book=book, status='pending')
    messages.success(request, f"Đã gửi yêu cầu mượn '{book.book_name}'. Vui lòng chờ admin duyệt.")
    return redirect('user_books_author')


# --- USER BORROWED VIEW (TRANG QUẢN LÝ CHÍNH) ---

@session_login_required
def user_borrowed(request):
    account = _get_current_account(request)
    if not account:
        return redirect('login_view')

    # Chỉ cần đếm số lượng để hiển thị badge trên Tab (Ví dụ: Đã mượn 3/5)
    current_borrowed_count = Borrow.objects.filter(user=account, status='borrowed').count()

    # TRẢ VỀ RỖNG các danh sách items.
    # Lý do: Bên file HTML, các thẻ div đã có hx-trigger="load"
    # nên nó sẽ tự động gọi 2 hàm dưới để lấy dữ liệu ngay lập tức.
    return render(request, 'user-borrowed.html', {
        'current_borrowed_count': current_borrowed_count,
        'limit': 5,
        'items': [],           # Để rỗng, HTMX sẽ tự điền
        'returned_items': [],  # Để rỗng, HTMX sẽ tự điền
        'is_empty_active': False,
        'is_empty_returned': False,
    })


# --- HTMX ACTIONS (KHÔNG RELOAD) ---

@session_login_required
@require_POST
def confirm_return(request, borrow_id):
    account = _get_current_account(request)
    if not account: return redirect('login_view')

    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account)

    b.status = 'await_return'
    b.return_date = timezone.now().date()
    b.save()
    messages.success(request, f"Đã gửi yêu cầu trả '{b.book.book_name}'.")

    if request.headers.get('HX-Request'):
        # Trả về partial để replace card cũ
        item_context = {'borrow': b, 'days_left': None}
        return render(request, 'partials/borrow_card.html', {'item': item_context})

    return HttpResponseRedirect(reverse('user_borrowed') + '?tab=returned')


@session_login_required
@require_POST
def cancel_pending_borrow(request, borrow_id):
    account = _get_current_account(request)
    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account, status='pending')
    b.delete()
    messages.success(request, "Đã hủy yêu cầu mượn.")

    if request.headers.get('HX-Request'):
        return HttpResponse("")  # Xóa card khỏi giao diện
    return redirect('user_borrowed')


@session_login_required
@require_POST
def cancel_return_request(request, borrow_id):
    account = _get_current_account(request)
    # get_object_or_404 sẽ tự raise 404 nếu không tìm thấy, không cần check if not b
    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account, status='await_return')

    b.status = 'borrowed'
    b.save()
    messages.success(request, "Đã hủy yêu cầu trả.")

    if request.headers.get('HX-Request'):
        days_left = calculate_days_left(b)
        item_context = {'borrow': b, 'days_left': days_left}
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
        return HttpResponse("")
    return HttpResponseRedirect(reverse('user_borrowed') + '?tab=returned')


# --- ADMIN HELPERS ---

def search_book_admin(request):
    q = request.GET.get('q', '').strip()
    if not q: return HttpResponse("")

    if q.isdigit():
        books = Book.objects.filter(Q(pk=q) | Q(book_name__icontains=q))[:10]
    else:
        books = Book.objects.filter(book_name__icontains=q)[:10]

    return render(request, 'partials/admin_search-result.html', {'books': books})


def get_pending_requests(request):
    pending = Borrow.objects.filter(status='pending').select_related('user', 'book').order_by('-borrow_date')
    return render(request, 'partials/admin_pending_list.html', {
        'pending_requests': pending,
        'pending_count': pending.count()
    })

# Trong views.py

# ... (các hàm cũ giữ nguyên) ...

@session_login_required
def get_user_active_borrows(request):
    """
    Hàm này được gọi tự động 2 giây/lần để lấy danh sách mượn mới nhất
    """
    account = _get_current_account(request)
    if not account:
        return HttpResponse("") # Trả về rỗng nếu chưa đăng nhập

    # Lấy danh sách Active (Pending + Borrowed) y hệt như view chính
    borrows_active = (Borrow.objects
                      .select_related('book', 'book__author')
                      .filter(user=account, status__in=['pending','borrowed'])
                      .order_by('-borrow_date', '-borrow_id'))

    active_items = []
    for b in borrows_active:
        # Tính lại ngày còn lại (Realtime)
        days_left = calculate_days_left(b)
        active_items.append({'borrow': b, 'days_left': days_left})

    # Trả về partial html
    return render(request, 'partials/user_active_list.html', {
        'items': active_items,
        'is_empty_active': len(active_items) == 0,
    })


# views.py

@session_login_required
def get_user_returned_history(request):
    """
    Hàm này lấy danh sách Đã trả + Chờ trả (Polling 2s/lần)
    """
    account = _get_current_account(request)
    if not account: return HttpResponse("")

    # Lấy danh sách History (Returned + Await Return)
    borrows_returned = (Borrow.objects
                        .select_related('book', 'book__author')
                        .filter(user=account, status__in=['await_return', 'returned'])
                        .order_by('-return_date', '-borrow_id'))

    # Đóng gói dữ liệu
    returned_items = [{'borrow': b} for b in borrows_returned]

    return render(request, 'partials/user_returned_list.html', {
        'returned_items': returned_items,
        'is_empty_returned': len(returned_items) == 0,
    })

