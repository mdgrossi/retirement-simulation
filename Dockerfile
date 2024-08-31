FROM quay.io/jupyter/base-notebook:python-3.11

WORKDIR /home

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install --upgrade pip ipython ipykernel
