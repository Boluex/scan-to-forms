from rest_framework.routers import DefaultRouter

from .views import BotRunViewSet

router = DefaultRouter()
router.register("bot-lab/runs", BotRunViewSet, basename="bot-run")

urlpatterns = router.urls

