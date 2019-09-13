import os
import json

from flask import Flask, request
import urllib3
import github_webhook
import gqlmod
from gqlmod_github.app import GithubApp
from werkzeug.local import LocalProxy

import status


CLIENT_ID = os.environ.get('github-client-id')
CLIENT_SECRET = os.environ.get('github-client-secret')

APP_ID = os.environ.get('github-application-id')
APP_PRIVATE_KEY = os.environ.get('github-private-key')


@LocalProxy
def ghapp():
    return GithubApp(APP_ID, APP_PRIVATE_KEY)


app = Flask(__name__)
webhook = github_webhook.Webhook(
    app,
    endpoint='/postreceive',
    secret=os.environ.get('github-webhook-secret'),
)

http = urllib3.PoolManager()


@app.route('/')
def hello_world():
    return "Hello, World!"


# This is part of the OAuth flow for acting as a User
@app.route('/authorization')
def authorization_callback():
    session_code = request.args.get('code')
    # This doesn't seem to be part of PyGithub
    resp = http.request(
        'POST',
        'https://github.com/login/oauth/access_token',
        fields={
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'code': session_code,
        },
    )

    respdata = json.loads(resp.data.decode('utf-8'))
    access_token = respdata['access_token']
    with gqlmod.with_provider('github', token=access_token):
        ...
        # TODO: Actually do meaningful things here.


@webhook.hook('ping')
def ping(payload):
    return "pong"


@webhook.hook('push')
def push(payload):
    with gqlmod.with_provider('github', token=ghapp.token_for_repo(
        payload['repository']['owner']['name'], payload['repository']['name'],
        repo_id=payload['repository']['id']
    )):
        resp = status.add_check_run(
            repo=payload['repository']['id'],
            sha=payload['head'],
            text="This is a test status!"
        )
        assert not resp.errors
