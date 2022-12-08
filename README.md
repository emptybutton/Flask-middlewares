## Flask-middlewares
Allows you to use the benefits of middlwares in Flask

### Installation
`pip install flask_middlewares`

### Example
```python
from typing import Callable

from flask import Flask, Blueprint
from flask_sqlalchemy import SQLAlchemy

from flask_middlewares import Middleware, ProxyMiddlewareAppRegistrar
from flask_middlewares.standard.error_handling import CustomHandlerErrorMiddleware, CustomJSONResponseErrorFormatter
from flask_middlewares.standard.status_code import StatusCodeRedirectorMiddleware
from flask_middlewares.standard.sql_alchemy import SQLAlchemySessionFinisherMiddleware


class StringMultiplierMiddleware(Middleware):
    """Custom middleware that multiplies strings."""

    def __init__(self, number_of_multiplies: int):
        self.number_of_multiplies = number_of_multiplies

    def call_route(self, route: Callable, *args, **kwargs) -> any:
        result = route(*args, **kwargs)
        return result * self.number_of_multiplies if isinstance(result, str) else result


class DomainError(Exception):
    """Error class dwelling in the depths of your domain."""


app = Flask(__name__)
api_blueprint = Blueprint('api', __name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db' # SQLAlchemy settings

db = SQLAlchemy()
db.init_app(app)

# Config for creating a middleware registrar for your application
app.config['GLOBAL_MIDDLEWARES'] = [CustomHandlerErrorMiddleware(CustomJSONResponseErrorFormatter((DomainError, ), 409, is_format_type=False))] # Middlewares for all views (See MiddlewareAppRegistrar.create_from_config documentation for exceptions)
app.config['MIDDLEWARE_ENVIRONMENTS'] = {
    'api': {
        'USE_FOR_BLUEPRINT': True, # Will be applied to the views that the blueprint has with the name "api"
        'MIDDLEWARES': (
            SQLAlchemySessionFinisherMiddleware(db),
            StringMultiplierMiddleware(1024)
        )
    }
}


@app.route('/')
@StatusCodeRedirectorMiddleware('true_index').decorate  # Using middleware bypassing the registrar
def index():
    return "Get out of here", 302 # Middleware will automatically redirect to true_index endpoint


@app.route('/home')
def true_index():
    return "This is true home page of the site!"


@app.route('/error-page')
def sick_endpoint():
    # The global middleware will handle the error and return a JSON response with its the status code specified in it and the message field of this error
    raise DomainError("Something went wrong")


@api_blueprint.route('/users')
def user_api_endpoint():
    return "User " # Due to the api config middleware, the result will be "User " * 1024


app.register_blueprint(api_blueprint, url_prefix='/api')

ProxyMiddlewareAppRegistrar.create_from_config(app.config).init_app(app)

if __name__ == '__main__':
    app.run(debug=True, port='8048')
```
