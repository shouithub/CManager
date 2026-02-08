
import os
import django
import sys

sys.path.append('d:\\sync\\Code\\CManager')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CManager.settings')
django.setup()

from clubs.models import TimeSlot
from django.utils import timezone

slots = TimeSlot.objects.filter(is_active=True).order_by('start_time')

day_start_minutes = 8 * 60
day_end_minutes = 22 * 60

if slots.exists():
    first_slot = slots.first()
    last_slot = slots.last()
    day_start_minutes = min(day_start_minutes, first_slot.start_time.hour * 60 + first_slot.start_time.minute)
    day_end_minutes = max(day_end_minutes, last_slot.end_time.hour * 60 + last_slot.end_time.minute)

total_minutes = day_end_minutes - day_start_minutes
print(f"Total Minutes: {total_minutes} (Start: {day_start_minutes}, End: {day_end_minutes})")

for slot in slots:
    slot_start_min = slot.start_time.hour * 60 + slot.start_time.minute
    slot_end_min = slot.end_time.hour * 60 + slot.end_time.minute
    
    top_percent = ((slot_start_min - day_start_minutes) / total_minutes) * 100
    height_percent = ((slot_end_min - slot_start_min) / total_minutes) * 100
    
    print(f"Slot {slot.label}: {slot.start_time}-{slot.end_time} ({slot_end_min - slot_start_min} min)")
    print(f"  Top: {top_percent:.2f}%, Height: {height_percent:.2f}%")
