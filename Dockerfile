FROM python:3.10

LABEL maintainer "Dr Julien Moreau, moreau.juli1@gmail.com"

WORKDIR /usr/src/FarmedLiceWestCoast

COPY requirements.txt /
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

# Copy app folder to app folder in container
COPY ./app ./

#mount the NFS drive
# RUN mount -t nfs 192.168.3.62:/srv /mnt/nfs/home

# Changing to non-root user
RUN useradd -m appUser
USER appUser

# Run locally on port 8080
CMD gunicorn --bind 0.0.0.0:8080 main:app
