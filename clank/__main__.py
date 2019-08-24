from github import Github
import os

import awsgi
from flask import (
    Flask,
)

import github_webhook


app = Flask(__name__)
webhook = github_webhook.Webhook(
    app,
    endpoint='/postreceive',
    secret=os.environ.get('secret'),
)

CHECKS = []

# First create a Github instance:
gh = Github(os.environ.get['token'])


@app.route('/')
def hello_world():
    return "Hello, World!"


@webhook.hook('ping')
def ping(payload):
    return "pong"


def main(event, context):
    rv = awsgi.response(app, event, context, base64_content_types={})
    return rv
