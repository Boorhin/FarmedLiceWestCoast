FROM python:3.10

LABEL maintainer "Dr Julien Moreau, moreau.juli1@gmail.com"

WORKDIR /usr/src/FarmedLiceWestCoast

COPY requirements.txt /
RUN pip install --upgrade pip
RUN pip install -r /requirements.txt

# Copy app folder to app folder in container
COPY ./app ./

#mount the NFS drive
#RUN --mount=type=bind,target=/data,source=192.168.3.62:/srv/data
#RUN --mount=type=bind,target=/tmp,source=/dev/sdc
# VOLUME /tmp:/dev/sdc
# expose the right port?
EXPOSE 8050

# Changing to non-root user
RUN useradd -m appUser
USER appUser

# Run locally on port 8080
CMD gunicorn --workers=4 --bind 0.0.0.0:8050 main:server
