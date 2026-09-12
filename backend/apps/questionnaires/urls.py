from rest_framework.routers import DefaultRouter

from .views import AnswerViewSet, QuestionnaireViewSet, ResponseBatchViewSet, ResponseViewSet

router = DefaultRouter()
router.register("questionnaires", QuestionnaireViewSet, basename="questionnaire")
router.register("response-batches", ResponseBatchViewSet, basename="response-batch")
router.register("responses", ResponseViewSet, basename="response")
router.register("answers", AnswerViewSet, basename="answer")

urlpatterns = router.urls

