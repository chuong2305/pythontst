from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.core.mail import send_mail # IMPORT: Thư viện gửi mail của Django
from django.conf import settings # IMPORT: Để lấy cấu hình từ settings.py
from .models import Borrow

BORROW_VERSION_KEY = "borrows_version"

def bump():
    v = cache.get(BORROW_VERSION_KEY)
    cache.set(BORROW_VERSION_KEY, 1 if v is None else int(v)+1)
    print("Signals bump, version=", cache.get(BORROW_VERSION_KEY))

@receiver(post_save, sender=Borrow)
def borrow_changed(sender, instance, created, **kwargs):
    bump()

    # --- BẮT ĐẦU LOGIC GỬI MAIL ---
    if not created:  # Chỉ gửi khi Admin CẬP NHẬT (duyệt/trả), không gửi khi User mới tạo request
        user_email = instance.user.email  # Lấy email từ model Account qua quan hệ ForeignKey
        book_name = instance.book.book_name  # Lấy tên cuốn sách đang thao tác
        user_name = instance.user.account_name  # Lấy tên người dùng để chào hỏi

        subject = ""
        message = "Admin đã cập nhật trạng thái yêu cầu mượn sách của bạn.\n\n"

        # Trường hợp Admin duyệt yêu cầu mượn (Status chuyển sang 'borrowed')
        if instance.status == 'borrowed':
            # Định dạng lại ngày tháng sang dd/mm/yyyy
            display_date = instance.due_date.strftime('%d/%m/%Y') if instance.due_date else "Chưa xác định"

            subject = f"Thông báo: Yêu cầu mượn sách '{book_name}' đã được duyệt"
            message = (f"Chào {user_name},\n\n"
                       f"Yêu cầu mượn sách của bạn đã được Admin phê duyệt.\n"
                       f"Hạn trả dự kiến: {instance.due_date}.\n"
                       f"Vui lòng đến thư viện nhận sách.")

        # Trường hợp Admin xác nhận đã trả (Status chuyển sang 'returned')
        elif instance.status == 'returned':
            subject = f"Thông báo: Xác nhận trả sách '{book_name}' thành công"
            message = (f"Chào {user_name},\n\n"
                       f"Thư viện đã nhận được sách bạn trả.\n"
                       f"Tổng tiền phạt phát sinh: {instance.fine} VNĐ.\n"
                       f"Cảm ơn bạn đã sử dụng thư viện!")

        # Thực hiện gửi mail thực tế nếu có nội dung (rơi vào 2 trường hợp trên)
        if subject:
            try:
                send_mail(
                    subject,  # Tiêu đề mail
                    message,  # Nội dung văn bản
                    settings.DEFAULT_FROM_EMAIL,  # Mail gửi đi (đã cấu hình ở settings)
                    ['23130344@st.hcmuaf.edu.vn'],  # Danh sách người nhận (email của user)
                    fail_silently=False,  # Để False để Django báo lỗi nếu cấu hình SMTP sai
                )
            except Exception as e:
                print(f"Lỗi gửi email: {e}")  # Log lỗi ra console nếu server mail từ chối kết nối
    # --- KẾT THÚC LOGIC GỬI MAIL ---

@receiver(post_delete, sender=Borrow)
def borrow_deleted(sender, instance, **kwargs):
    bump()