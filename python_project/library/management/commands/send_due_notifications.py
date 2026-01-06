from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from datetime import timedelta
from library.models import Borrow

class Command(BaseCommand):
    help = 'Gửi email nhắc nhở cho các sách sắp đến hạn trả (còn 1 ngày)'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        target_date = today + timedelta(days=1) # Ngày mai là hạn trả

        # Lọc các đơn mượn có hạn trả là ngày mai và đang ở trạng thái 'borrowed'
        borrows_due_soon = Borrow.objects.filter(
            status='borrowed',
            due_date=target_date
        ).select_related('user', 'book')

        count = 0
        for borrow in borrows_due_soon:
            if not borrow.user.email:
                continue

            self.send_notification_email(borrow)
            count += 1

        self.stdout.write(self.style.SUCCESS(f'Đã gửi {count} email nhắc nhở.'))

    def send_notification_email(self, instance):
        book_name = instance.book.book_name
        user_name = instance.user.account_name
        due_date_str = instance.due_date.strftime('%d/%m/%Y')
        user_email = instance.user.email

        subject = f"⏰ Nhắc nhở: Sách '{book_name}' sắp đến hạn trả"

        # Tái sử dụng style CSS giống signals.py để đồng bộ giao diện
        style_container = "font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 10px; background-color: #ffffff;"
        style_header = "color: #d97706; font-size: 24px; font-weight: 700; margin-bottom: 20px; border-bottom: 2px solid #d97706; padding-bottom: 10px;"
        style_text = "font-size: 16px; line-height: 1.6; color: #333333; margin-bottom: 15px;"
        style_highlight = "color: #1851A8; font-weight: 600;"
        style_warning = "color: #dc2626; font-weight: bold;"
        style_footer = "margin-top: 30px; font-size: 14px; color: #6b7280; border-top: 1px solid #e5e7eb; padding-top: 15px;"

        html_content = f"""
        <div style="{style_container}">
            <h1 style="{style_header}">Nhắc Nhở Hạn Trả Sách</h1>
            <p style="{style_text}">Chào <strong>{user_name}</strong>,</p>
            <p style="{style_text}">Thư viện xin nhắc bạn rằng cuốn sách dưới đây sẽ đến hạn trả vào <strong style="color: #dc2626;">ngày mai</strong>.</p>

            <div style="background-color: #fff7ed; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 5px solid #d97706;">
                <p style="{style_text} margin: 5px 0;">📖 Sách: <span style="{style_highlight}">{book_name}</span></p>
                <p style="{style_text} margin: 5px 0;">⏳ Hạn trả: <span style="{style_warning}">{due_date_str}</span> (Ngày mai)</p>
            </div>

            <p style="{style_text}">Vui lòng sắp xếp thời gian trả sách hoặc gia hạn (nếu có thể) để tránh phí phạt quá hạn.</p>

            <div style="{style_footer}">
                Trân trọng,<br>
                <strong>Đội ngũ Thư viện Education</strong>
            </div>
        </div>
        """

        try:
            send_mail(
                subject=subject,
                message=strip_tags(html_content),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user_email],
                html_message=html_content,
                fail_silently=False
            )
        except Exception as e:
            print(f"Lỗi gửi email cho {user_email}: {e}")