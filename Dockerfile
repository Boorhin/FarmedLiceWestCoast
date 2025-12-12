FROM python:3.12.3

LABEL maintainer="Dr Julien Moreau, moreau.juli1@gmail.com"

WORKDIR /usr/src/FarmedLiceWestCoast

COPY requirements.txt /
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

# Copy app folder to app folder in container
COPY ./app ./
#add time-stamp
RUN date "+%Y-%m-%dT%H:%M">assets/build-date.txt

EXPOSE 8050

# Changing to non-root user K8
#RUN useradd -m appUser
#USER appUser

# Changing to non-root user Ubuntu22
RUN useradd -m azimuth
USER azimuth

# Run locally on port 8050
CMD ["gunicorn", "--workers=4","--bind", "0.0.0.0:8050", "main:server"]


