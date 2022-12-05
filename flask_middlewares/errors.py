class MiddlewareError(Exception):
    pass


class MiddlewareAppRegistrarError(MiddlewareError):
    pass


class MiddlewareRegistrarConfigError(MiddlewareAppRegistrarError):
    pass