from rest_framework.exceptions import APIException


class PlanLimitExceeded(APIException):
    status_code = 402
    default_code = "plan_limit_exceeded"
    default_detail = "Your plan allowance has been reached. Upgrade or purchase extra OCR pages."


class FeatureNotAvailable(APIException):
    status_code = 403
    default_code = "feature_not_available"
    default_detail = "This feature is not included in your current plan."


class PaystackError(APIException):
    status_code = 502
    default_code = "payment_gateway_error"
    default_detail = "The payment gateway could not complete the request."

