FROM python:3.10

LABEL maintainer "Dr Julien Moreau, moreau.juli1@gmail.com"

WORKDIR /usr/src/FarmedLiceWestCoast

COPY requirements.txt /
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

# Copy app folder to app folder in container
COPY ./app ./

EXPOSE 8050

# Changing to non-root user
RUN useradd -m appUser
USER appUser

# Run locally on port 8080
CMD gunicorn --workers=4 --bind 0.0.0.0:8050 main:server
