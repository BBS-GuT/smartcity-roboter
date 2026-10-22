"""Bounded MQTT diagnostic; synthetic, non-retained messages, no robot access."""
import argparse
import json
import os
import socket
import threading
import uuid

import paho.mqtt.client as mqtt


def check(host, port, timeout):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            print('PASS TCP connection', flush=True)
    except OSError as error:
        print('FAIL TCP:', type(error).__name__, str(error), flush=True)
        print('SKIP MQTT login and message transfer: TCP unavailable', flush=True)
        return 1

    token = uuid.uuid4().hex
    topic = 'smartcity/diagnostics/' + token + '/echo'
    payload = json.dumps({'test_id': token, 'synthetic': True}).encode()
    clients = []
    received = threading.Event()
    subscribed = threading.Event()
    failure = []

    def connect(role):
        ready = threading.Event()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id='mqtt-check-' + role + '-' + token[:12],
                             reconnect_on_failure=False)
        clients.append(client)
        client.connect_timeout = timeout
        if os.getenv('MQTT_USERNAME'):
            client.username_pw_set(os.environ['MQTT_USERNAME'], os.getenv('MQTT_PASSWORD'))

        def connected(c, u, flags, reason, properties):
            if reason.is_failure:
                failure.append('MQTT login rejected: ' + str(reason))
            ready.set()

        def disconnected(c, u, flags, reason, properties):
            if not ready.is_set():
                failure.append('Broker closed connection before MQTT CONNACK; check credentials/protocol')
                ready.set()

        client.on_connect = connected
        client.on_disconnect = disconnected
        client.connect(host, port, keepalive=15)
        client.loop_start()
        if not ready.wait(timeout):
            raise TimeoutError('MQTT CONNACK missing (' + role + ')')
        if failure:
            raise RuntimeError(failure[-1])
        print('PASS MQTT login (' + role + ', ' +
              ('credentials from environment' if os.getenv('MQTT_USERNAME') else 'anonymous') + ')',
              flush=True)
        return client

    def on_subscribe(c, u, mid, reasons, properties):
        if not reasons or any(reason.is_failure for reason in reasons):
            failure.append('MQTT subscription rejected')
        subscribed.set()

    def on_message(c, u, message):
        if message.topic == topic and message.payload == payload and not message.retain:
            received.set()

    try:
        reader = connect('reader')
        reader.on_subscribe = on_subscribe
        reader.on_message = on_message
        result, _ = reader.subscribe(topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS or not subscribed.wait(timeout):
            raise TimeoutError('MQTT SUBACK missing')
        if failure:
            raise RuntimeError(failure[-1])
        writer = connect('writer')
        result = writer.publish(topic, payload, qos=1, retain=False)
        result.wait_for_publish(timeout=timeout)
        if not result.is_published():
            raise TimeoutError('MQTT PUBACK missing')
        print('PASS QoS 1 PUBACK', flush=True)
        if not received.wait(timeout):
            raise TimeoutError('Independent receiver did not receive test payload; check topic ACL')
        print('PASS independent receiver: exact synthetic payload, non-retained, topic=' + topic,
              flush=True)
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print('FAIL MQTT:', type(error).__name__, str(error), flush=True)
        return 2
    finally:
        for client in clients:
            client.disconnect()
            client.loop_stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.getenv('MQTT_HOST', '10.0.40.100'))
    parser.add_argument('--port', type=int, default=int(os.getenv('MQTT_PORT', '1883')))
    parser.add_argument('--timeout', type=float, default=5)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 0 < args.timeout <= 60:
        parser.error('port must be 1..65535 and timeout > 0 and <= 60 seconds')
    raise SystemExit(check(args.host, args.port, args.timeout))

