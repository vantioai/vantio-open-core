# Syslog

Passed command, after the container exists:

```sh
sudo docker start vantio-rsyslog
sudo docker exec vantio-rsyslog sh -c ': > /out/syslog.log'
```

The container is Alpine 3.20 with rsyslog. TCP is host port 5515. UDP is host port 5514.

A bound send with `syslog` set to `tcp://127.0.0.1:5515` and again to `udp://127.0.0.1:5514` wrote schema `1.0.0`, `BLOCK`, the three kinds, and no canary into `deploy/observability/rsyslog/out/syslog.log`. The OTLP side of that send was a local HTTP sink that returned 200, because the exporter sends OTLP before syslog.

The first TCP attempt against a cold start did not leave the trace. The warm repeat did. Wait until port 5515 accepts connections.
