import awsgi
from flask import (
    Flask,
    jsonify,
)

app = Flask(__name__)


@app.route('/')
def index():
    return jsonify(status=200, message='OK')


def main(event, context):
    print("event", event)
    rv = awsgi.response(app, event, context, base64_content_types={"image/png"})
    print("result", rv)
    return rv


def test(event, context):
    print("event", event)
    print("context", context)
    return {
        "statusCode": 200,
        "statusDescription": "200 OK",
        "isBase64Encoded": False,
        "headers": {
            "Content-Type": "text/html"
        },
        "body": "<h1>Hello from Lambda!</h1>"
    }
