from django.http import HttpResponseNotFound
from django.shortcuts import render


def not_found(request, exception=None):
    if getattr(request, "builder", None) is None:  # No builder website on this host (e.g. the admin host).
        return HttpResponseNotFound("Not found.", content_type="text/plain")
    return render(request, "404.html", status=404)
