from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from functools import wraps
from django.db import transaction
from .models import Book, Author, Category, Publisher, Account, Borrow, BookAssociationRule
from django.core.exceptions import ValidationError
from .recommendation import RecommendationService


# --- HELPER FUNCTIONS ---

def _get_current_account(request):
    acc_id = request.session.get('account_id')
    if not acc_id:
        return None
    return Account.objects.filter(account_id=acc_id).first()


def calculate_days_left(borrow_instance):
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


def home_page_user(request):
    account = _get_current_account(request)
    notifications = []
    if account:
        notifications = Borrow.objects.filter(
            user=account,
            status__in=['borrowed', 'returned']
        ).select_related('book').order_by('-borrow_id')

    return render(request, 'home-page-user.html', {
        'notifications': notifications
    })


def login_view(request):
    return render(request, 'login.html')


def user_books_author(request):
    return user_books_view(request)


def user_books_type(request):
    return render(request, 'user-books-type.html')


def borrowed_history(request):
    return render(request, 'borrowed-history.html')


def library_rule(request):
    return render(request, 'library-rule.html')


@session_login_required
def library_card(request):
    account = _get_current_account(request)
    return render(request, 'library_card.html', {
        'account': account
    })

@session_login_required
def notify(request):
    account = _get_current_account(request)
    if not account:
        return redirect('login_view')

    notifications = Borrow.objects.filter(
        user=account,
        status__in=['borrowed', 'returned']
    ).select_related('book').order_by('-borrow_id')

    return render(request, 'notify.html', {
        'notifications': notifications
    })


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

    account = _get_current_account(request)
    if account:
        recommended_books = RecommendationService.get_recommendations_for_user(account, limit=6)
    else:
        recommended_books = []

    return render(request, "user-books-author.html", {
        "books": books,
        "recommended_books": recommended_books,
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


@require_POST
def reserve_book(request, book_id):
    account = _get_current_account(request)
    book = get_object_or_404(Book, pk=book_id)

    # Kiểm tra xem người dùng đã có trạng thái mượn/đặt với sách này chưa
    existing_borrow = Borrow.objects.filter(
        user=account,
        book=book,
        status__in=['reserved', 'borrowed', 'pending']
    ).exists()

    if existing_borrow:
        messages.error(
            request,
            "Bạn đã đặt trước hoặc đang mượn cuốn sách này."
        )
        return redirect('user_books_author')

    reserved_count = Borrow.objects.filter(
        book=book,
        status='reserved'
    ).count()

    if book.available <= reserved_count:
        messages.error(
            request,
            "Hiện đã có người dùng khác đặt trước."
        )
        return redirect('user_books_author')

    Borrow.objects.create(
        user=account,
        book=book,
        status='reserved'
    )

    messages.success(request, "Đặt trước thành công.")
    return redirect('user_books_author')


# --- USER BORROWED VIEW (TRANG QUẢN LÝ CHÍNH) ---

@session_login_required
def user_borrowed(request):
    account = _get_current_account(request)
    if not account:
        return redirect('login_view')

    current_borrowed_count = Borrow.objects.filter(user=account, status='borrowed').count()

    return render(request, 'user-borrowed.html', {
        'current_borrowed_count': current_borrowed_count,
        'limit': 5,
        'items': [],
        'returned_items': [],
        'reserved_items': [],
        'is_empty_active': False,
        'is_empty_returned': False,
        'is_empty_reserved': False,
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
        item_context = {'borrow': b, 'days_left': None}
        return render(request, 'partials/borrow_card.html', {'item': item_context})

    return HttpResponseRedirect(reverse('user_borrowed') + '?tab=returned')


@session_login_required
@require_POST
def cancel_pending_borrow(request, borrow_id):
    account = _get_current_account(request)
    b = get_object_or_404(Borrow, borrow_id=borrow_id, user=account, status__in=['reserved', 'pending'])
    b.delete()
    messages.success(request, "Đã hủy yêu cầu.")

    if request.headers.get('HX-Request'):
        return HttpResponse("")
    return redirect('user_borrowed')


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


@session_login_required
def get_user_active_borrows(request):
    account = _get_current_account(request)
    if not account:
        return HttpResponse("")

    borrows_active = (Borrow.objects
                      .select_related('book', 'book__author')
                      .filter(user=account, status__in=['pending', 'borrowed'])
                      .order_by('-borrow_date', '-borrow_id'))

    active_items = []
    for b in borrows_active:
        days_left = calculate_days_left(b)
        active_items.append({'borrow': b, 'days_left': days_left})

    return render(request, 'partials/user_active_list.html', {
        'items': active_items,
        'is_empty_active': len(active_items) == 0,
    })

@session_login_required
def get_user_returned_history(request):
    account = _get_current_account(request)
    if not account: return HttpResponse("")

    borrows_returned = (Borrow.objects
                        .select_related('book', 'book__author')
                        .filter(user=account, status__in=['await_return', 'returned'])
                        .order_by('-return_date', '-borrow_id'))

    returned_items = [{'borrow': b} for b in borrows_returned]

    return render(request, 'partials/user_returned_list.html', {
        'returned_items': returned_items,
        'is_empty_returned': len(returned_items) == 0,
    })


@session_login_required
def get_user_reserved_books(request):

    account = _get_current_account(request)
    if not account: return HttpResponse("")
    borrows_reserved = (Borrow.objects
                        .select_related('book', 'book__author')
                        .filter(user=account, status='reserved')
                        .order_by('-borrow_date'))

    reserved_items = [{'borrow': b} for b in borrows_reserved]

    return render(request, 'partials/user_reserved_list.html', {
        'reserved_items': reserved_items,
        'is_empty_reserved': len(reserved_items) == 0,
    })