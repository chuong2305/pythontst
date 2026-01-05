from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
from .models import Borrow

BORROW_VERSION_KEY = "borrows_version"


def bump():
    try:
        v = cache.get(BORROW_VERSION_KEY)
        new_v = 1 if v is None else int(v) + 1
        cache.set(BORROW_VERSION_KEY, new_v)
        print("Signals bump, version =", new_v)
    except Exception as e:
        print("Cache bump error:", e)


@receiver(pre_save, sender=Borrow)
def check_duplicate_borrow(sender, instance, **kwargs):
    if not instance.pk:
        exists = Borrow.objects.filter(
            user=instance.user,
            book=instance.book,
            status__in=['reserved', 'borrowed']
        ).exists()

        if exists:
            raise ValidationError(
                f"Bạn đã đặt hoặc đang mượn sách '{instance.book.book_name}'.")


@receiver(pre_save, sender=Borrow)
def track_status_change(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_status = None
    else:
        try:
            instance._old_status = Borrow.objects.get(pk=instance.pk).status
        except Borrow.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=Borrow)
def borrow_changed(sender, instance, created, **kwargs):
    bump()
    # --- BẮT ĐẦU LOGIC GỬI MAIL ---
    if not created:
        user_email = instance.user.email
        if not user_email:
            return

        book_name = instance.book.book_name
        user_name = instance.user.account_name

        old_status = getattr(instance, '_old_status', None)
        new_status = instance.status

        if old_status == new_status:
            return

        subject = ""
        html_content = ""

        # CSS chung cho email
        style_container = "font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 10px; background-color: #ffffff;"
        style_header = "color: #1851A8; font-size: 24px; font-weight: 700; margin-bottom: 20px; border-bottom: 2px solid #1851A8; padding-bottom: 10px;"
        style_text = "font-size: 16px; line-height: 1.6; color: #333333; margin-bottom: 15px;"
        style_highlight = "color: #1851A8; font-weight: 600;"
        style_warning = "color: #d97706; font-weight: 600;"
        style_footer = "margin-top: 30px; font-size: 14px; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 15px;"

        # Trường hợp 1: Admin duyệt mượn (Status -> borrowed)
        if new_status == 'borrowed':
            display_date = instance.due_date.strftime('%d/%m/%Y') if instance.due_date else "Chưa xác định"
            subject = f"📚 Thông báo: Bạn đã mượn sách '{book_name}'"

            html_content = f"""
            <div style="{style_container}">
                <h1 style="{style_header}">Xác Nhận Mượn Sách</h1>
                <p style="{style_text}">Chào <strong>{user_name}</strong>,</p>
                <p style="{style_text}">Yêu cầu mượn sách của bạn đã được Admin phê duyệt thành công.</p>

                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p style="{style_text} margin: 5px 0;">📖 Sách: <span style="{style_highlight}">{book_name}</span></p>
                    <p style="{style_text} margin: 5px 0;">📅 Ngày mượn: {instance.borrow_date.strftime('%d/%m/%Y')}</p>
                    <p style="{style_text} margin: 5px 0;">⏳ Hạn trả: <span style="{style_warning}">{display_date}</span></p>
                </div>

                <p style="{style_text}">Vui lòng trả sách đúng hạn để tránh phát sinh phí phạt và bảo quản sách cẩn thận.</p>

                <div style="{style_footer}">
                    Trân trọng,<br>
                    <strong>Đội ngũ Thư viện Education</strong>
                </div>
            </div>
            """

        # Trường hợp 2: Admin xác nhận trả (Status -> returned)
        elif new_status == 'returned':
            subject = f"✅ Thông báo: Đã trả sách '{book_name}' thành công"
            fine_text = f"{instance.fine:,.0f}" if instance.fine else "0"
            damage_text = instance.get_damage_status_display()

            # Đổi màu tiêu đề nếu có phạt
            header_color = "#dc2626" if instance.fine > 0 else "#059669"
            style_header_return = f"color: {header_color}; font-size: 24px; font-weight: 700; margin-bottom: 20px; border-bottom: 2px solid {header_color}; padding-bottom: 10px;"

            html_content = f"""
            <div style="{style_container}">
                <h1 style="{style_header_return}">Xác Nhận Trả Sách</h1>
                <p style="{style_text}">Chào <strong>{user_name}</strong>,</p>
                <p style="{style_text}">Thư viện xác nhận bạn đã hoàn tất thủ tục trả sách.</p>

                <div style="background-color: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p style="{style_text} margin: 5px 0;">📖 Sách: <span style="{style_highlight}">{book_name}</span></p>
                    <p style="{style_text} margin: 5px 0;">🔍 Tình trạng sách: {damage_text}</p>
                    <p style="{style_text} margin: 5px 0;">💰 Phí phạt phát sinh: <span style="color: #dc2626; font-weight: bold;">{fine_text} VNĐ</span></p>
                </div>

                <p style="{style_text}">Cảm ơn bạn đã sử dụng dịch vụ của thư viện. Chúc bạn một ngày tốt lành!</p>

                <div style="{style_footer}">
                    Trân trọng,<br>
                    <strong>Đội ngũ Thư viện Education</strong>
                </div>
            </div>
            """

        if subject and html_content:
            try:
                # Tạo bản text thuần túy từ HTML (cho các trình mail cũ không hỗ trợ HTML)
                text_content = strip_tags(html_content)

                # Tạo EmailMultiAlternatives object
                msg = EmailMultiAlternatives(
                    subject,
                    text_content,  # Nội dung text (fallback)
                    settings.DEFAULT_FROM_EMAIL,
                    [user_email]
                )

                # Đính kèm nội dung HTML
                msg.attach_alternative(html_content, "text/html")

                # Gửi mail
                msg.send(fail_silently=False)
                print(f"HTML Email sent successfully to {user_email}")
            except Exception as e:
                print(f"Lỗi gửi email: {e}")
    # --- KẾT THÚC LOGIC GỬI MAIL ---


@receiver(post_delete, sender=Borrow)
def borrow_deleted(sender, instance, **kwargs):
    bump()