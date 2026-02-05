from django import template
from crm.dashboard_data import get_dashboard_data

register = template.Library()

@register.simple_tag
def get_custom_dashboard_data():
    return get_dashboard_data()
