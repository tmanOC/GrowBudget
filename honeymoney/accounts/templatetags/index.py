from django import template
register = template.Library()

@register.filter
def index(my_list, i):
    return my_list[int(i)]