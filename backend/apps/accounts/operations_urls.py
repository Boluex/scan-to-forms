from django.urls import path
from rest_framework.routers import DefaultRouter

from .operations import AdminOverviewView, AdminUsersViewSet, AnnouncementView

router = DefaultRouter()
router.register("users", AdminUsersViewSet, basename="admin-user")
urlpatterns = [
    path("overview/", AdminOverviewView.as_view()),
    path("announcements/", AnnouncementView.as_view()),
] + router.urls
