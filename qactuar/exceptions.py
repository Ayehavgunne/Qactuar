class QactuarException(Exception):
    pass


class HTTPError(QactuarException):
    pass


class RouteNotFoundError(QactuarException):
    pass
