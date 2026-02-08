import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CManager.settings')
django.setup()

from clubs.models import MaterialRequirement

print(f"Total Requirements: {MaterialRequirement.objects.count()}")
for req in MaterialRequirement.objects.all():
    print(f"Type: {req.request_type}, Name: {req.name}, Legacy: {req.legacy_field_name}")
