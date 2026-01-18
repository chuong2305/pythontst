from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LogoutView
from library import views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include
urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.custom_login, name='login'),
    path('', views.login_view, name='login_view'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('home-user/', views.home_page_user, name='home_page_user'),

    path("home-user/user-books-author/", views.user_books_view, name="user_books_author"),
    path("home-user/user-books-type/", views.user_books_type, name="user_books_type"),
    path("home-user/user-borrowed/", views.user_borrowed, name="user_borrowed"),
    path("home-user/borrowed-history/", views.borrowed_history, name="borrowed_history"),
    path("home-user/library-rule/", views.library_rule, name="library_rule"),
    path("home-user/library_card/", views.library_card, name="library_card"),
    path("home-user/notify/", views.notify, name="notify"),
    path("home-user/must-return-book/", views.must_return_book, name="must_return_book"),

    path('user/books/', views.user_books_view, name="user_books"),
    path('borrow/reserve/<int:book_id>/', views.reserve_book, name='reserve_book'),
    path('borrow/return/<int:borrow_id>/', views.confirm_return, name='confirm_return'),
    path('borrow/pending/cancel/<int:borrow_id>/', views.cancel_pending_borrow, name='cancel_pending_borrow'),
    path('borrow/returned/delete/<int:borrow_id>/', views.delete_returned_borrow, name='delete_returned_borrow'),

    path('admin/get-pending/', views.get_pending_requests, name='get_pending_requests'),
    path('user/get-active-borrows/', views.get_user_active_borrows, name='get_user_active_borrows'),
    path('user/get-returned-history/', views.get_user_returned_history, name='get_user_returned_history'),
    path('user/get-reserved-books/', views.get_user_reserved_books, name='get_user_reserved_books'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)