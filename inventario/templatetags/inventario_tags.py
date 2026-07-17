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


@register.simple_tag
def active_page(request, view_name):
    from django.urls import resolve, Resolver404
    try:
        match = resolve(request.path_info)
        if match.view_name.startswith(view_name):
            return 'active'
    except Resolver404:
        pass
    return ''
