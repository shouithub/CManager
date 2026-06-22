from django import template


register = template.Library()


@register.filter
def get_item(value, key):
    try:
        return value.get(key, 0)
    except Exception:
        return 0
