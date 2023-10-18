FROM python:3.11.3

COPY . /app

WORKDIR /app

RUN pip3 install -r requirements.txt

EXPOSE 4444

CMD ["python", "./main.py"]

