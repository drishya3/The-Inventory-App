from .models import AppSettings

def theme_settings(request):
    settings = AppSettings.objects.first()
    return {"settings": settings}
