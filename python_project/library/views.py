from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

def home(request):
    return render(request, 'home-page.html')

def home_page_user(request):
    return render(request, 'home-page-user.html')

def login_view(request):
    return render(request, 'login.html')

def admin_book_author(request):
    return render(request, 'admin-book-author.html')

def admin_borrow(request):
    return render(request, 'admin-borrow.html')

@require_http_methods(["GET", "POST"])
def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        
        # Admin: username = "admin", password = "1"
        if username == 'admin' and password == '1':
            return redirect('home')
        
        # User: any other username + password "có sẵn"
        elif username == "dangpham" and password == '123':
            return redirect('home_page_user')
        
        # Đăng nhập thất bại
        else:
            return render(request, 'login.html', {'error': 'Tên đăng nhập hoặc mật khẩu không chính xác'})
    
    return render(request, 'login.html')



