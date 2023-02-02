## Flask-middlewares
Allows you to use the benefits of middlwares in Flask

### Installation
`pip install flask_middlewares`

### Example
```python
from typing import Callable

from flask import Flask, Blueprint
from pyhandling.annotations import decorator

from flask_middlewares import MultipleMiddlewareRegistrar
from flask_middlewares.tools import EVERYTHING


app = Flask(__name__)

api_blueprint = Blueprint('api', __name__)
view_blueprint = Blueprint('views', __name__)


def concatenation_by(line: str) -> decorator:
    """
    Function for a decorator that concatenates the result of the decorated
    function with the input result of this function.
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> str:
            return func(*args, **kwargs) + ' ' + line

        return wrapper

    return decorator


# Config for creating a middleware registrar for your application
# See the MiddlewareRegistrar.from_config documentation.

app.config["ENVIRONMENTS"] = {
    "global": {
        "MIDDLEWARES": [concatenation_by("from global")],
        "VIEW_NAMES": EVERYTHING
    },
    'api': {
        "USE_FOR_BLUEPRINT": True,
        "MIDDLEWARES": [concatenation_by("from api")]
    }
}

@app.route('/')
def index():
    return "Real but fake home page" # Real but fake home page from global


@view_blueprint.route('/home')
def home_endpoint():
    return "Real home page" # Real home page from global


@api_blueprint.route('/users')
def user_api_endpoint():
    return "\"Some user data\"" # "Some user data" from global from api


app.register_blueprint(api_blueprint, url_prefix='/api')
app.register_blueprint(view_blueprint)

MultipleMiddlewareRegistrar.from_config(app.config, environments_only=True).init_app(app)

if __name__ == '__main__':
    app.run(debug=True, port='8048')
```
