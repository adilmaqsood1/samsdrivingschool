from django import template
from django.apps import apps
from crm.dashboard_data import get_dashboard_data

register = template.Library()

@register.simple_tag
def get_custom_dashboard_data():
    return get_dashboard_data()

@register.simple_tag
def get_model_count(app_label, model_name):
    try:
        model = apps.get_model(app_label, model_name)
        return model.objects.count()
    except Exception:
        return 0
