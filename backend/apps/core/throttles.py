from rest_framework.throttling import UserRateThrottle


class WorkspaceUserThrottle(UserRateThrottle):
    """Operators reviewing hundreds of pages need a separate authenticated budget."""

    def allow_request(self, request, view):
        self.scope = (
            "operator" if request.user.is_authenticated and request.user.is_staff else "user"
        )
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)
