import os

from flask import Flask
import github_webhook
from gqlmod_github.app import GithubApp
from werkzeug.local import LocalProxy

import status


CLIENT_ID = os.environ.get('github_client_id')
CLIENT_SECRET = os.environ.get('github_client_secret')

APP_ID = os.environ.get('github_application_id')
APP_PRIVATE_KEY = os.environ.get('github_private_key')


@LocalProxy
def ghapp():
    return GithubApp(APP_ID, APP_PRIVATE_KEY)


app = Flask(__name__)
webhook = github_webhook.Webhook(
    app,
    endpoint='/postreceive',
    secret=os.environ.get('github_webhook_secret'),
)


@app.route('/')
def root():
    """
    Basic status call
    """
    return "Service is running"


# This is part of the OAuth flow for acting as a User
@app.route('/authorization')
def authorization_callback():
    return 'OAuth is not used by this service', 418


@webhook.hook('push')
def push(payload):
    with ghapp.as_repo(
        payload['repository']['owner']['name'], payload['repository']['name'],
        repo_id=payload['repository']['id']
    ):
        resp = status.add_check_run(
            repo=payload['repository']['id'],
            sha=payload['head'],
            text="This is a test status!"
        )
        assert not resp.errors
        print(resp)
