from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from django.core.mail import send_mail # IMPORT: Thư viện gửi mail của Django
from django.conf import settings # IMPORT: Để lấy cấu hình từ settings.py
from django.core.exceptions import ValidationError
from .models import Borrow

BORROW_VERSION_KEY = "borrows_version"

def bump():
    v = cache.get(BORROW_VERSION_KEY)
    cache.set(BORROW_VERSION_KEY, 1 if v is None else int(v)+1)
    print("Signals bump, version=", cache.get(BORROW_VERSION_KEY))


@receiver(pre_save, sender=Borrow)
def check_duplicate_borrow(sender, instance, **kwargs):
    # Chỉ kiểm tra khi tạo mới phiếu mượn (chưa có ID)
    if not instance.pk:
        # Kiểm tra xem user này đã có phiếu nào chưa kết thúc với cuốn sách này không
        exists = Borrow.objects.filter(
            user=instance.user,
            book=instance.book,
            status__in=['pending','borrowed', 'await_return']
        ).exists()

        if exists:
            raise ValidationError(
                f"Bạn đang mượn hoặc đang chờ duyệt cuốn sách '{instance.book.book_name}' rồi, không thể mượn thêm.")

def update_book_inventory(book):
    """
    Hàm này tính toán lại số lượng sách available.
    Logic: Available = Quantity (Tổng) - Số phiếu đang mượn (Pending/Borrowed/Await_return)
    """
    # Đếm số lượng phiếu đang hoạt động (chưa trả xong)
    active_borrows = Borrow.objects.filter(
        book=book,
        status__in=['borrowed', 'await_return']
    ).count()

    # Tính lại available
    new_available = book.quantity - active_borrows

    # Đảm bảo không bị âm (đề phòng dữ liệu cũ sai lệch)
    if new_available < 0:
        new_available = 0

    book.available = new_available
    book.save()
    print(f"Cập nhật kho sách '{book.book_name}': Còn lại {book.available}/{book.quantity}")

@receiver(post_save, sender=Borrow)
def borrow_changed(sender, instance, created, **kwargs):
    bump()

    update_book_inventory(instance.book)
    # --- BẮT ĐẦU LOGIC GỬI MAIL ---
    if not created:  # Chỉ gửi khi Admin CẬP NHẬT (duyệt/trả), không gửi khi User mới tạo request
        user_email = instance.user.email  # Lấy email từ model Account qua quan hệ ForeignKey
        book_name = instance.book.book_name  # Lấy tên cuốn sách đang thao tác
        user_name = instance.user.account_name  # Lấy tên người dùng để chào hỏi

        subject = ""
        message = ""

        # Trường hợp Admin duyệt yêu cầu mượn (Status chuyển sang 'borrowed')
        if instance.status == 'borrowed':
            # Định dạng lại ngày tháng sang dd/mm/yyyy
            display_date = instance.due_date.strftime('%d/%m/%Y') if instance.due_date else "Chưa xác định"

            subject = f"Thông báo: Yêu cầu mượn sách '{book_name}' đã được duyệt"
            message = (f"Chào {user_name},\n\n"
                       f"Yêu cầu mượn sách của bạn đã được Admin phê duyệt.\n"
                       f"Hạn trả dự kiến: {display_date}.\n"
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
                    [user_email],  # Danh sách người nhận (email của user)
                    fail_silently=False,  # Để False để Django báo lỗi nếu cấu hình SMTP sai
                )
            except Exception as e:
                print(f"Lỗi gửi email: {e}")  # Log lỗi ra console nếu server mail từ chối kết nối
    # --- KẾT THÚC LOGIC GỬI MAIL ---

@receiver(post_delete, sender=Borrow)
def borrow_deleted(sender, instance, **kwargs):
    bump()

    # --- 3. GỌI HÀM CẬP NHẬT TẠI ĐÂY ---
    # Khi xóa phiếu mượn (ví dụ xóa yêu cầu), số lượng phải được cộng lại
    update_book_inventory(instance.book)
    # -----------------------------------