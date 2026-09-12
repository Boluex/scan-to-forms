from rest_framework.routers import DefaultRouter

from .views import ResponsePageViewSet, UploadedDocumentViewSet

router = DefaultRouter()
router.register("documents", UploadedDocumentViewSet, basename="document")
router.register("response-pages", ResponsePageViewSet, basename="response-page")
urlpatterns = router.urls
