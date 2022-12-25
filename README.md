## Flask-middlewares
Allows you to use the benefits of middlwares in Flask

### Installation
`pip install flask_middlewares`

### Example
```python
from typing import Callable, Generic

from flask import Flask, Blueprint
from flask_sqlalchemy import SQLAlchemy

from flask_middlewares import Middleware, ProxyMiddlewareAppRegistrar
from flask_middlewares.standard.error_handling import CustomHandlerErrorMiddleware, CustomJSONResponseErrorFormatter
from flask_middlewares.standard.status_code import StatusCodeRedirectorMiddleware
from flask_middlewares.standard.sql_alchemy import SQLAlchemySessionFinisherMiddleware


class MultiplierMiddleware(Middleware):
    """Custom middleware that multiplies result of the route."""

    def __init__(self, number_of_multiplies: int):
        self.number_of_multiplies = number_of_multiplies

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        return route(*args, **kwargs) * self.number_of_multiplies


class TokenAuthorizationMiddleware(Middleware):
    def __init__(self, response_headers_parser: Generic[dict] = lambda _: request.headers):
        self.response_headers_parser = response_headers_parser

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        response = route(*args, **kwargs)

        if not 'some-token' in self.response_headers_parser(response).keys():
            raise InfrastructureError("An authorization collapse has occurred")


class InfrastructureError(Exception):
    """Error class dwelling in the depths of your application."""


app = Flask(__name__)

admin_blueprint = Blueprint('admin', __name__)
api_blueprint = Blueprint('api', __name__)
crm_blueprint = Blueprint('crm', __name__)
view_blueprint = Blueprint('views', __name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'

db = SQLAlchemy()
db.init_app(app)


# Config for creating a middleware registrar for your application
# See the FlaskAppMiddlewareRegistrar.create_from_config documentation.

app.config['GLOBAL_MIDDLEWARES'] = [
    TokenAuthorizationMiddleware()
]

app.config['MIDDLEWARE_ENVIRONMENTS'] = {
    'error-presenter': {
        'MIDDLEWARE_BLUEPRINTS': BinarySet(non_included=('api', ))
        'MIDDLEWARES': (
            StatusCodeAbortingMiddleware(StatusCodeGroup.ERROR),
            CustomHandlerErrorMiddleware(
                JSONResponseTemplatedErrorFormatter(
                    status_code_resource=500,
                    is_format_type=False
                ),
            ),
        )
    }
    'page-sender': {
        'MIDDLEWARE_BLUEPRINTS': ('views', 'admin', 'crm'),
        'IS_APPLY_ROOT_VIEWS': False,
        # The composite StatusCodeGroup can be replaced by StatusCodeGroup.ERRORS
        'MIDDLEWARES': (StatusCodeAbortingMiddleware(
            StatusCodeGroup.SERVER_ERROR | StatusCodeGroup.CLIENT_ERROR),
        )
    }
    'database-worker': {
        'MIDDLEWARE_BLUEPRINTS': ('api', 'admin'),
        'IS_APPLY_ROOT_VIEWS': False,
        'MIDDLEWARES': (SQLAlchemySessionFinisherMiddleware(db), )
    }
    'api': {
        'USE_FOR_BLUEPRINT': True,
        'IS_GLOBAL_MIDDLEWARES_HIGHER': False, 
        'MIDDLEWARES': (
            CustomHandlerErrorMiddleware(
                ErrorHandlerAllower(
                    JSONResponseTemplatedErrorFormatter(
                        status_code_resource=409,
                        is_format_type=False
                    ),
                    TypeDeterminant(InfrastructureError)
                )
            ),
            MultiplierMiddleware(1024),
        )
    },
    'unrealized': {
        'MIDDLEWARE_BLUEPRINTS': ('admin', 'crm'),
        'IS_APPLY_ROOT_VIEWS': False,
        'MIDDLEWARES': (StatusCodeRedirectorMiddleware('views.index', StatusCodeGroup.ALL), )
    }
}


# Using middleware bypassing the registrar
@view_blueprint.route('/')
@StatusCodeRedirectorMiddleware('views.true_index', StatusCodeGroup.ALL).decorate
def index():
    return "Get out of here" # Middleware will automatically redirect to true_index endpoint


@view_blueprint.route('/home')
def true_index():
    return "This is true home page of the site!"


@view_blueprint.route('/error-page')
def sick_endpoint():
    # First, this error is converted to json error response, then abort is called
    # by the status code taken from the generated response.

    raise InfrastructureError("Something went wrong")


@api_blueprint.route('/users')
def user_api_endpoint():
    return "User " # Due to the api config middleware, the result will be "User " * 1024


# The bottom two are included in the "unrealized" environment and will be
# redirected to the formally main page first and then to the actual main page.

@admin_blueprint.route('/')
def admin_index():
    pass


@crm_blueprint.route('/')
def crm_index():
    pass


app.register_blueprint(admin_blueprint, url_prefix='/admin')
app.register_blueprint(api_blueprint, url_prefix='/api')
app.register_blueprint(crm_blueprint, url_prefix='/crm')
app.register_blueprint(view_blueprint)

ProxyFlaskAppMiddlewareRegistrar.create_from_config(app.config).init_app(app)

if __name__ == '__main__':
    app.run(debug=True, port='8048')
```
