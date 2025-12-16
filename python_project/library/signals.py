from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Borrow

BORROW_VERSION_KEY = "borrows_version"

def bump():
    v = cache.get(BORROW_VERSION_KEY)
    cache.set(BORROW_VERSION_KEY, 1 if v is None else int(v)+1)
    print("Signals bump, version=", cache.get(BORROW_VERSION_KEY))

@receiver(post_save, sender=Borrow)
def borrow_changed(sender, instance, created, **kwargs):
    bump()

@receiver(post_delete, sender=Borrow)
def borrow_deleted(sender, instance, **kwargs):
    bump()