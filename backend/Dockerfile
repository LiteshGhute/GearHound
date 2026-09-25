FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Virtual bus by default: no host CAN interface, no --network=host, no
# --privileged needed. Override CAN_BUSTYPE=socketcan (and run with
# --network=host --privileged) to talk to a real vcan0 on a Linux host,
# same as GearGoat's original container did.
ENV CAN_BUSTYPE=virtual \
    CAN_CHANNEL=gearhound \
    PORT=4000

EXPOSE 4000

CMD ["python3", "app.py"]
