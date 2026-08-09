"""Transactional room-booking operations."""

from django.db import transaction
from django.utils import timezone

from clubs.models import Room, RoomBooking


class BookingConflictError(ValueError):
    """Raised when an active booking overlaps the requested interval."""


class BookingValidationError(ValueError):
    """Raised when booking data violates room or calendar constraints."""


def _validate_booking(*, room, booking_date, start_time, end_time, participant_count):
    if booking_date < timezone.localdate():
        raise BookingValidationError('不能预约过去的日期')
    if start_time >= end_time:
        raise BookingValidationError('结束时间必须晚于开始时间')
    if participant_count < 1:
        raise BookingValidationError('参与人数必须大于 0')
    if participant_count > room.capacity:
        raise BookingValidationError(f'参与人数不能超过房间容量 {room.capacity} 人')


def _has_conflict(*, room_id, booking_date, start_time, end_time, exclude_id=None):
    conflicts = RoomBooking.objects.filter(
        room_id=room_id,
        booking_date=booking_date,
        status='active',
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_id is not None:
        conflicts = conflicts.exclude(pk=exclude_id)
    return conflicts.exists()


@transaction.atomic
def create_room_booking(*, room_id, user, club, booking_date, start_time, end_time,
                        purpose, participant_count, contact_phone,
                        special_requirements=''):
    """Create a booking while serializing all writes for the target room."""
    room = Room.objects.select_for_update().get(pk=room_id, status='available')
    _validate_booking(
        room=room,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        participant_count=participant_count,
    )
    if _has_conflict(
        room_id=room.pk,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
    ):
        raise BookingConflictError('该时间段已被预约，请选择其他时间')

    return RoomBooking.objects.create(
        room=room,
        user=user,
        club=club,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        purpose=purpose,
        participant_count=participant_count,
        contact_phone=contact_phone,
        special_requirements=special_requirements or '',
        status='active',
    )


@transaction.atomic
def update_room_booking(*, booking_id, room_id, club, booking_date, start_time,
                        end_time, purpose, participant_count, contact_phone,
                        special_requirements=''):
    """Update a booking while locking its row and every affected room."""
    booking = RoomBooking.objects.select_for_update().get(pk=booking_id)
    affected_room_ids = sorted({booking.room_id, int(room_id)})
    rooms = {
        room.pk: room
        for room in Room.objects.select_for_update().filter(
            pk__in=affected_room_ids,
            status='available',
        ).order_by('pk')
    }
    target_room_id = int(room_id)
    if target_room_id not in rooms:
        raise Room.DoesNotExist

    _validate_booking(
        room=rooms[target_room_id],
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        participant_count=participant_count,
    )

    if _has_conflict(
        room_id=target_room_id,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        exclude_id=booking.pk,
    ):
        raise BookingConflictError('该时间段已被预约，请选择其他时间')

    booking.room = rooms[target_room_id]
    booking.club = club
    booking.booking_date = booking_date
    booking.start_time = start_time
    booking.end_time = end_time
    booking.purpose = purpose
    booking.participant_count = participant_count
    booking.contact_phone = contact_phone
    booking.special_requirements = special_requirements or ''
    booking.save()
    return booking
