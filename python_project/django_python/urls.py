"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from library import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('home-user/', views.home_page_user, name='home_page_user'),
    path('login/', views.custom_login, name='login'),
    path('login-view/', views.login_view, name='login_view'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    path('home/book-author/', views.admin_book_author, name='admin_book_author'),
    path('home/borrow/', views.admin_borrow, name='admin_borrow'),
    path("home/welcome/", views.welcome_view, name="welcome_view"),
    path("home-user/user-books-author/", views.user_books_author, name="user_books_author"),
    path("home-user/user-books-type/", views.user_books_type, name="user_books_type"),
    path("home-user/user-borrowed/", views.user_borrowed, name="user_borrowed"),
]


