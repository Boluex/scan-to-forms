from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AppsScriptJobViewSet, AppsScriptPreviewView

router = DefaultRouter()
router.register("google-forms/scripts", AppsScriptJobViewSet, basename="apps-script-job")

urlpatterns = [path("google-forms/preview/", AppsScriptPreviewView.as_view(), name="apps-script-preview"), *router.urls]

