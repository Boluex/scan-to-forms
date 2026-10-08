from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet, PushDeviceView

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notification")
urlpatterns = [path("notifications/devices/", PushDeviceView.as_view())] + router.urls
