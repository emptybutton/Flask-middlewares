class MiddlewareError(Exception):
    pass


class MiddlewareRegistrarError(MiddlewareError):
    pass


class MiddlewareRegistrarConfigError(MiddlewareRegistrarError):
    pass