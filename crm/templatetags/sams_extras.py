"""Small template helpers for the marketing pages."""

from django import template

register = template.Library()

# Keyword -> b-roll photo for the service cards, checked in order. Falls back to
# the beginner photo, then the theme placeholder, when a course carries its own
# image the template uses that instead.
_SERVICE_IMAGES = [
    (("defensive", "ddc", "improvement", " di ", "demerit", "suspension"),
     "assets/images/sams/service-defensive.jpg"),
    (("g2", "g exit", "g road", "road test", "exit prep", "g test"),
     "assets/images/sams/service-roadtest.jpg"),
    (("beginner", "bde", "new driver", "g1", "online course"),
     "assets/images/sams/service-bde.jpg"),
]
_DEFAULT_SERVICE_IMAGE = "assets/images/sams/service-bde.jpg"


@register.filter
def service_image(title):
    """Pick a b-roll photo for a course/service by its title."""
    text = f" {(title or '').lower()} "
    for keywords, path in _SERVICE_IMAGES:
        if any(k in text for k in keywords):
            return path
    return _DEFAULT_SERVICE_IMAGE
