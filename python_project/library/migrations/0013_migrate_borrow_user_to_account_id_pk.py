from django.db import migrations

def forwards(apps, schema_editor):
    Account = apps.get_model('library', 'Account')
    Borrow = apps.get_model('library', 'Borrow')


    id_map = {}
    for acc in Account.objects.all():

        id_map[str(acc.account_id)] = acc.id

    updated = 0
    for b in Borrow.objects.all():
        old = str(b.user_id)
        new = id_map.get(old)
        if new and new != b.user_id:
            b.user_id = new  # gán về id nội bộ
            b.save(update_fields=['user_id'])
            updated += 1

def backwards(apps, schema_editor):
    Account = apps.get_model('library', 'Account')
    Borrow = apps.get_model('library', 'Borrow')

    id_to_code = {}
    for acc in Account.objects.all():
        id_to_code[acc.id] = str(acc.account_id)

    for b in Borrow.objects.all():
        old = b.user_id
        new = id_to_code.get(old)
        if new and new != b.user_id:
            b.user_id = new
            b.save(update_fields=['user_id'])

class Migration(migrations.Migration):
    dependencies = [
        ('library', '0012_account_id_alter_account_account_id'),
    ]
    operations = [
        migrations.RunPython(forwards, backwards),
    ]