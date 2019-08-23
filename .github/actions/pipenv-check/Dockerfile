FROM xonsh/xonsh

RUN pip install pipenv

COPY xonshrc.xsh /etc/xonshrc
COPY action.xsh /action.xsh

ENTRYPOINT ["/action.xsh"]
CMD []
