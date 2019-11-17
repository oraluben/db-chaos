FROM ubuntu:18.04

RUN apt-get update && apt-get install -y wget mysql-client tmux make gcc

# RUN useradd tidb -m
RUN useradd -m tidb && echo "tidb:tidb" | chpasswd && adduser tidb sudo && apt-get install sudo

USER tidb
WORKDIR /home/tidb/
RUN wget -O - http://download.pingcap.org/tidb-v3.0-linux-amd64.tar.gz | tar xzf -
RUN wget -O - https://dl.google.com/go/go1.13.4.linux-amd64.tar.gz | tar xzf -

ENV PATH=/home/tidb/tidb-v3.0-linux-amd64/bin:/home/tidb/go/bin:${PATH}