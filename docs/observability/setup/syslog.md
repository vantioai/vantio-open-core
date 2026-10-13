# Syslog

Passed command, from the repo root:

```sh
sudo docker compose -p rsyslog -f deploy/observability/rsyslog/compose.yaml up -d
```

That build uses Alpine 3.20 and installs rsyslog in the image. TCP is host port `5515`. UDP is `5514`. The drain in this run used TCP.

Wait until `rsyslogd` is running. Docker publishes `5515` before the process inside is listening, and a connect to that port can succeed without a log line. The exporter was held until `pidof rsyslogd` succeeded, then the queued batches were flushed. The log contained that trace id 8 times. The syslog line does not include the workload id.

A paused rsyslog container made the sender time out. After it was unpaused, a new send's trace id was in the file.

The OTLP side of a syslog send is a local HTTP sink that returns 200, because the exporter sends OTLP before syslog.
