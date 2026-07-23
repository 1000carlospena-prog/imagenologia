from django import template

register = template.Library()


@register.filter
def multiply(value, arg):
    return value * arg


@register.filter
def sum_two(value, arg):
    return (value or 0) + (arg or 0)


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)



