import json
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def divide_by_100(value):
    try:
        return value / 100
    except (TypeError, ZeroDivisionError):
        return 0


@register.filter
def multiply(value, arg):
    try:
        return value * arg
    except (TypeError, ValueError):
        return None


@register.filter
def map_attr(iterable, attr):
    return [getattr(item, attr, None) for item in iterable]


@register.filter
def to_string(value):
    return str(value)


@register.filter
def is_regional_user(user):
    return user.role == "regional"


@register.filter
def is_place_user(user):
    return user.role == "place"


@register.filter
def show_for_role(user, role):

    return user.role == role


@register.filter
def get_item_property(queryset, property_path):

    if not queryset:
        return None

    if property_path.startswith("first."):
        item = queryset[0]
        property_name = property_path.split("first.")[1]
    elif property_path.startswith("last."):
        item = queryset[-1]
        property_name = property_path.split("last.")[1]
    else:
        return None

    return getattr(item, property_name, None)


@register.filter
def get(dictionary, key):
    return dictionary.get(key, "")


@register.filter
def get_percentage_color(percentage):

    if percentage < 40:
        return "text-red-500 font-bold"
    elif percentage < 70:
        return "text-orange-500 font-semibold"
    else:
        return "text-green-500 font-semibold"
    
@register.filter
def to_json(value):
    try:
        return mark_safe(json.dumps(value))
    except (TypeError, ValueError):
        return "null"
