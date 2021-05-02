# pull official base image
FROM ubuntu:20.04

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2 dependencies
RUN apt-get update && apt-get upgrade -y
RUN apt-get install libpq-dev -y
RUN apt-get install netcat -y

# install dependencies
RUN apt-get install -y python3
RUN apt-get -y install python3-pip

COPY ./requirements.txt .
RUN pip3 install -r requirements.txt

# copy project
COPY . .

# run entrypoint.sh
ENTRYPOINT [ "/usr/src/app/entrypoint.sh" ]