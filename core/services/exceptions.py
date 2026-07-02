class ServiceError(Exception):
    pass


class NotFound(ServiceError):
    pass


class Forbidden(ServiceError):
    pass


class LimitExceeded(ServiceError):
    pass


class InvalidState(ServiceError):
    pass


class ValidationFailed(ServiceError):
    pass
