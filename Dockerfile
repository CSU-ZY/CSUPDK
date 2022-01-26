FROM jupyter/base-notebook
# FROM continuumio/miniconda3

# expose klive and jupyter notebook ports
EXPOSE 8082
EXPOSE 8083
EXPOSE 8888

USER root
RUN apt-get update --yes && \
    apt-get install --yes --no-install-recommends \
    # Common useful utilities
    git \
    neovim

USER jovyan
COPY . /home/jovyan/gdfactory
COPY docs/notebooks /home/jovyan/notebooks
RUN conda init bash

# RUN git clone https://github.com/gdsfactory/gdsfactory.git
# USER ${NB_UID}
# RUN apt update
# RUN apt install gcc
# RUN conda install -c conda-forge pymeep -y

RUN mamba install gdspy triangle -y
RUN mamba install pymeep=*=mpi_mpich_*
RUN pip install gdsfactory[full]

# COPY requirements.txt /opt/app/requirements.txt
# COPY requirements_dev.txt /opt/app/requirements_dev.txt
# WORKDIR /opt/app
# RUN pip install -r requirements.txt
# RUN pip install -r requirements_dev.txt

WORKDIR /home/jovyan
# VOLUME /home/jovyan/work
