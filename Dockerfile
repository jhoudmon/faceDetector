FROM python:3.7-slim
WORKDIR /usr/src/app

COPY requirements.txt ./

RUN apt-get -y update
RUN apt-get install -y build-essential cmake
RUN apt-get install -y libopencv-dev
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD [ "python", "./facedetect.py" ]