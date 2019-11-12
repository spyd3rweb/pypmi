FROM python:3

ENV LISTEN_PORT=623
EXPOSE 623

WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ./*.py ./

#CMD [ "python", "./pypmb.py", "--port", ${LISTEN_PORT} ]
CMD python ./pypmb.py --port ${LISTEN_PORT}