from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ActiveAccountJWTScheme(OpenApiAuthenticationExtension):
    target_class = "apps.accounts.authentication.ActiveAccountJWTAuthentication"
    name = "jwtAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
