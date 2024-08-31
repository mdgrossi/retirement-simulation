FROM quay.io/jupyter/base-notebook:python-3.11

WORKDIR /home

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt
RUN pip install --upgrade pip ipython ipykernel
RUN ipython kernel install --name "python3" --user
