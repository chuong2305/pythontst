from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LogoutView
from library import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.custom_login, name='login'),
    path('', views.login_view, name='login_view'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path("home/welcome/", views.welcome_view, name="welcome_view"),
    path('home-user/', views.home_page_user, name='home_page_user'),

    # Dùng cùng 1 view để luôn có dữ liệu books
    path("home-user/user-books-author/", views.user_books_view, name="user_books_author"),
    path("home-user/user-books-type/", views.user_books_type, name="user_books_type"),
    path("home-user/user-borrowed/", views.user_borrowed, name="user_borrowed"),
    path("home-user/borrowed-history/", views.borrowed_history, name="borrowed_history"),
    path("home-user/library-rule/", views.library_rule, name="library_rule"),
    path("home-user/library_card/", views.library_card, name="library_card"),
    path("home-user/notify/", views.notify, name="notify"),
    path("home-user/user-account/", views.user_account, name="user_account"),

    # Alias (có thể giữ để test)
    path('user/books/', views.user_books_view, name="user_books"),
]